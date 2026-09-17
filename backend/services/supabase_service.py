import os
import requests
import re
import logging
from datetime import datetime, timezone
from services.encryption_service import EncryptionService

logger = logging.getLogger("supabase_service")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [SupabaseService] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

class SupabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        self.encryption_service = EncryptionService()
        if not self.url or not self.key:
            logger.warning("SUPABASE_URL or SUPABASE_ANON_KEY is not set.")

    def create_session(self, title, user_token):
        if not self.url or not self.key or not user_token:
            return None
        
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Mã hóa tiêu đề phiên chat trước khi lưu
        encrypted_title = self.encryption_service.encrypt_text(title)
        data = {"title": encrypted_title}
        
        try:
            response = requests.post(
                f"{self.url}/rest/v1/chat_sessions", 
                headers=headers, 
                json=data
            )
            if response.status_code in (200, 201):
                result = response.json()
                if result and len(result) > 0:
                    return result[0].get('id')
            else:
                logger.error(f"Error creating session: {response.text}")
        except Exception as e:
            logger.error(f"Exception creating session: {e}")
            
        return None

    def save_message(self, session_id, role, content, user_token, file_name=None, file_type=None, sources=None, query_provision_labels=None):
        if not self.url or not self.key or not session_id or not user_token:
            return False

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }

        data = {
            "session_id": session_id,
            "role": role,
            "content": self.encryption_service.encrypt_text(content)
        }

        if file_name:
            data["file_name"] = file_name
        if file_type:
            data["file_type"] = file_type

        # result_snapshot là tên cột JSONB có sẵn trong DB (xem database/schema.sql),
        # dùng chung để lưu dữ liệu "đính kèm" theo từng tin nhắn:
        # - "sources" (nguồn tham chiếu luật) cho tin nhắn assistant.
        # - "query_provision_labels" (nhãn "Tra cứu: ...") cho tin nhắn user.
        snapshot = {}
        if sources:
            snapshot["sources"] = sources
        if query_provision_labels:
            snapshot["query_provision_labels"] = query_provision_labels
        if snapshot:
            data["result_snapshot"] = snapshot
            
        try:
            response = requests.post(
                f"{self.url}/rest/v1/chat_messages", 
                headers=headers, 
                json=data
            )
            if response.status_code in (200, 201):
                current_time = datetime.now(timezone.utc).isoformat()
                # Dùng params= thay vì nối chuỗi "id=eq.{session_id}" trực tiếp vào URL -
                # session_id đến từ client (request.form), nối chuỗi thô có thể bị lợi
                # dụng để chèn thêm điều kiện/filter PostgREST (ví dụ chứa ký tự '&').
                # params= để requests tự động percent-encode giá trị an toàn.
                requests.patch(
                    f"{self.url}/rest/v1/chat_sessions",
                    headers=headers,
                    params={"id": f"eq.{session_id}"},
                    json={"updated_at": current_time}
                )
                return True
            else:
                logger.error(f"Error saving message: {response.text}")
        except Exception as e:
            logger.error(f"Exception saving message: {e}")
            
        return False

    # Hybrid re-rank (docs/bhxh_keyphrase_spec.md mục 6.2 bước 4): điểm cộng thêm
    # cho 1 chunk khi provision_type của nó khớp với "dạng câu hỏi" đã đoán được
    # (guard_service.classify_provision_types). Giá trị nhỏ so với thang similarity
    # (0..1) để CHỈ tinh chỉnh thứ tự giữa các chunk có độ liên quan gần nhau,
    # không để 1 chunk lệch chủ đề nhưng khớp provision_type lấn át chunk tương
    # đồng ngữ nghĩa cao hơn hẳn.
    PROVISION_TYPE_BOOST = 0.05

    def search_legal_documents(self, query_vector, query_provision_types=None):
        if not self.url or not self.key or not query_vector:
            return "Thiếu cấu hình Supabase hoặc Vector.", []

        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        # Yêu cầu RPC trả về cả trường metadata
        response = requests.post(
            f"{self.url}/rest/v1/rpc/match_legal_documents",
            headers=headers,
            json={'query_embedding': query_vector, 'match_threshold': 0.3, 'match_count': 50}
        )

        if response.status_code == 200:
            results = response.json()
            if results:
                # (0) Hybrid re-rank: nếu đoán được "dạng câu hỏi" (provision_type),
                # sắp lại results theo similarity + boost provision_type khớp, TRƯỚC
                # khi gom nhóm/chọn bài - vì round-robin bên dưới chỉ lấy tối đa 3
                # đoạn đầu tiên của mỗi văn bản, nên phải ưu tiên đúng ngay từ đây.
                if query_provision_types:
                    def rerank_key(r):
                        meta = r.get('metadata', {}) or {}
                        similarity = r.get('similarity') or 0
                        boost = self.PROVISION_TYPE_BOOST if meta.get('provision_type') in query_provision_types else 0
                        return similarity + boost
                    results.sort(key=rerank_key, reverse=True)

                # (1). Lọc kết quả với chiến thuật Đa dạng hóa (Round-Robin)
                from collections import defaultdict

                grouped_results = defaultdict(list)
                for r in results:
                    meta = r.get('metadata', {})
                    law_name = meta.get('law_name', r.get('title', 'Tài liệu').split(' - ')[0])
                    # Lưu trữ các đoạn vào danh sách riêng của từng văn bản, đã sắp xếp
                    # từ giống nhất/ưu tiên nhất đến ít nhất (theo similarity, hoặc theo
                    # similarity + provision_type boost ở bước (0) nếu có)
                    grouped_results[law_name].append(r)

                filtered_results = []
                max_total_chunks = 12
                max_per_doc = 3 # Không lấy quá 3 đoạn/văn bản để tránh loãng (ở vòng round-robin đầu tiên)
                
                doc_pull_counts = defaultdict(int)

                # Bắt đầu chia bài: Lấy xoay vòng mỗi văn bản 1 đoạn tốt nhất
                while len(filtered_results) < max_total_chunks:
                    added_in_this_round = False
                    
                    # grouped_results giữ nguyên thứ tự xuất hiện ban đầu (văn bản có điểm cao nhất xếp trước)
                    for law_name, chunks in list(grouped_results.items()):
                        # Nếu văn bản này vẫn còn đoạn chưa lấy VÀ chưa lấy quá 3 đoạn
                        if chunks and doc_pull_counts[law_name] < max_per_doc:
                            filtered_results.append(chunks.pop(0))
                            doc_pull_counts[law_name] += 1
                            added_in_this_round = True
                            
                        if len(filtered_results) >= max_total_chunks:
                            break
                            
                    # Nếu đi hết 1 vòng mà không nhặt được thêm đoạn nào (hết dữ liệu), thì dừng
                    if not added_in_this_round:
                        break

                # Vòng 2 - tận dụng nốt slot còn trống: nếu sau vòng round-robin có
                # giới hạn (max_per_doc=3) mà filtered_results VẪN chưa đầy
                # max_total_chunks, nghĩa là số văn bản liên quan thực sự ít hơn dự
                # kiến (VD chỉ có 1 văn bản khớp nhưng có tới 6 Khoản liên quan) -
                # lúc này bỏ giới hạn max_per_doc, lấy tiếp các đoạn còn lại (đã ưu
                # tiên sẵn theo similarity + provision_type boost) cho đến khi đầy
                # hoặc hết dữ liệu, thay vì lãng phí slot dù dữ liệu liên quan vẫn còn.
                while len(filtered_results) < max_total_chunks:
                    added_in_this_round = False
                    for law_name, chunks in list(grouped_results.items()):
                        if chunks:
                            filtered_results.append(chunks.pop(0))
                            added_in_this_round = True
                        if len(filtered_results) >= max_total_chunks:
                            break
                    if not added_in_this_round:
                        break

                # (2) Đối chiếu quan hệ sửa đổi: "amended_by" đã được ghi sẵn vào
                # metadata của mỗi chunk lúc ingest (xem ingest_rag.py:backfill_amended_by),
                # nên ở đây chỉ cần gom các tham chiếu đó lại và fetch đúng nội dung
                # chunk đang sửa đổi bằng MỘT request duy nhất.
                amendment_docs = self._fetch_amending_chunks(filtered_results)

                # Sắp xếp đa tầng: Năm > Ngày ban hành > Số hiệu
                def get_sort_key(item):
                    meta = item.get('metadata', {})
                    law_year = meta.get('law_year')
                    law_number = meta.get('law_number')
                    issue_date = item.get('issue_date') or '0000-00-00'

                    if law_year is not None:
                        try:
                            return (int(law_year), issue_date, int(law_number) if law_number is not None else 0)
                        except (TypeError, ValueError):
                            pass

                    # Fallback cho dữ liệu cũ chưa có law_year/law_number (ingest trước khi có schema mới)
                    law_name = meta.get('law_name', item.get('title', ''))
                    doc_id = self._parse_doc_id(law_name)
                    if doc_id:
                        return (doc_id['year'], issue_date, doc_id['number'])

                    year_from_date = int(issue_date[:4]) if issue_date != '0000-00-00' else 0
                    return (year_from_date, issue_date, 0)

                filtered_results.sort(key=get_sort_key, reverse=True)

                # TUYỆT ĐỐI KHÔNG TRIM (cắt) filtered_results sau khi đã sort theo Ngày/Năm vì sẽ vô tình xóa mất các kết quả gốc chứa câu trả lời chính xác nhất.

                # --- XÂY DỰNG CONTEXT CHO AI ---
                context = "Dưới đây là cơ sở dữ liệu pháp luật (Ngữ cảnh pháp lý) được trích xuất từ hệ thống:\n\n"

                sources = []
                # Đưa các đoạn gốc vào Context
                context += "=== CÁC QUY ĐỊNH GỐC TÌM ĐƯỢC ===\n"
                for idx, row in enumerate(filtered_results):
                    meta = row.get('metadata', {})
                    law_name = meta.get('law_name', row.get('title', 'Quy định pháp luật'))
                    article = meta.get('article', 'N/A')
                    section = meta.get('section', 'N/A')

                    source_parts = []
                    if article and article != 'N/A':
                        source_parts.append(f"Điều {article}")
                    if section and section != 'N/A':
                        source_parts.append(f"Khoản {section}")

                    source_label = law_name
                    if source_parts:
                        source_label += f" ({', '.join(source_parts)})"

                    if source_label not in sources:
                        sources.append(source_label)

                    amended_info = ""
                    amended_by_refs = meta.get('amended_by') or []
                    if amended_by_refs:
                        refs_str = "; ".join(self._format_amendment_ref(ref) for ref in amended_by_refs)
                        amended_info = f"\n⚠️ CẢNH BÁO: Điều/Khoản này có thể ĐÃ BỊ SỬA ĐỔI/BÃI BỎ bởi: {refs_str}."

                    context += f"--- [{law_name}] (Điều: {article}, Khoản: {section}) ---\nNội dung: {row.get('content', '')}{amended_info}\n\n"

                # Đưa các đoạn sửa đổi vào Context để AI so sánh
                if amendment_docs:
                    context += "=== THÔNG TIN SỬA ĐỔI/BỔ SUNG (DÙNG ĐỂ ĐỐI CHIẾU) ===\n"
                    for am_doc in amendment_docs:
                        meta = am_doc.get('metadata', {})
                        law_name = meta.get('law_name', 'Văn bản mới')
                        article = meta.get('article', 'N/A')
                        section = meta.get('section', 'N/A')
                        
                        source_parts = []
                        if article and article != 'N/A':
                            source_parts.append(f"Điều {article}")
                        if section and section != 'N/A':
                            source_parts.append(f"Khoản {section}")
                        
                        source_label = law_name
                        if source_parts:
                            source_label += f" ({', '.join(source_parts)})"
                        
                        if source_label not in sources: 
                            sources.append(source_label)
                        context += f"--- [{law_name}] (Điều: {meta.get('article', 'N/A')}, Khoản: {meta.get('section', 'N/A')}) ---\n"
                        context += f"Nội dung sửa đổi: {am_doc.get('content', '')}\n\n"

                return context, sources
        
        return "Không tìm thấy dữ liệu liên quan.", []

    def _parse_doc_id(self, text):
        """Trích xuất Number, Year, Type từ chuỗi (VD: Nghị định số: 68/2026/NĐ-CP)"""
        if not text: return None
        match = re.search(r'(\d+)/(\d{4})/([\w-]+)', text)
        if match:
            return {
                'number': int(match.group(1)),
                'year': int(match.group(2)),
                'type': match.group(3),
                'full': match.group(0) # VD: 68/2026/NĐ-CP
            }
        return None

    @staticmethod
    def _ref_key(ref):
        """Khóa duy nhất cho 1 tham chiếu amended_by/amendments_to, dùng để khử trùng lặp khi duyệt BFS."""
        return (ref.get('law_number'), ref.get('law_year'), ref.get('article'), ref.get('section'))

    def _fetch_chunks_by_refs(self, refs):
        """
        Fetch đúng các chunk khớp với danh sách `refs` (mỗi ref: law_number/law_year/
        article[/section]) bằng MỘT request PostgREST duy nhất
        (or=(and(...),and(...)) khớp chính xác), thay vì "ilike" content + so sánh
        ngày tháng ở mỗi câu hỏi như cách làm cũ (_check_for_updates).
        """
        and_groups = []
        for ref in refs:
            if not ref.get('law_number') or not ref.get('law_year') or not ref.get('article'):
                continue
            conditions = [
                f"metadata->>law_number.eq.{ref['law_number']}",
                f"metadata->>law_year.eq.{ref['law_year']}",
                f"metadata->>article.eq.{ref['article']}",
            ]
            if ref.get('section'):
                conditions.append(f"metadata->>section.eq.{ref['section']}")
            and_groups.append(f"and({','.join(conditions)})")

        if not and_groups:
            return []

        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        params = {
            "select": "content,metadata,issue_date",
            "or": f"({','.join(and_groups)})"
        }
        try:
            resp = requests.get(f"{self.url}/rest/v1/legal_documents", headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Error fetching amending chunks: {resp.text}")
        except Exception as e:
            logger.error(f"Exception fetching amending chunks: {e}")
        return []

    def _fetch_amending_chunks(self, results, max_hops=5, max_total=30):
        """
        Duyệt BFS theo chuỗi "amended_by" (đã được ghi sẵn vào metadata lúc ingest
        - xem ingest_rag.py:backfill_amended_by), bắt đầu từ các chunk trong
        `results`. Nếu 1 chunk sửa đổi (VD B sửa A) lại tiếp tục bị 1 văn bản khác
        sửa đổi (C sửa B), BFS sẽ lần tiếp sang C ở tầng kế tiếp, thay vì chỉ dừng
        ở tầng 1 (A bị B sửa) như trước.

        Mỗi tầng chỉ tốn ĐÚNG 1 request HTTP (gộp toàn bộ ref của tầng đó bằng
        or=(and(...),...)), nên tổng chi phí mạng là O(số tầng), không phải
        O(số node) - giữ nguyên tinh thần tối ưu ban đầu dù duyệt nhiều tầng hơn.
        `max_hops`/`max_total` là chặn an toàn, phòng dữ liệu bất thường (vòng lặp
        tham chiếu chéo) khiến BFS chạy vô hạn hoặc context phình quá to.
        """
        all_amending_docs = []
        seen_doc_keys = set()
        seen_ref_keys = set()

        frontier = []
        for row in results:
            for ref in (row.get('metadata', {}).get('amended_by') or []):
                key = self._ref_key(ref)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key)
                    frontier.append(ref)

        hop = 0
        while frontier and hop < max_hops and len(all_amending_docs) < max_total:
            hop += 1
            docs = self._fetch_chunks_by_refs(frontier)
            next_frontier = []
            for doc in docs:
                doc_key = str(doc.get('metadata', {}).get('law_name')) + str(doc.get('content', ''))[:50]
                if doc_key not in seen_doc_keys:
                    seen_doc_keys.add(doc_key)
                    all_amending_docs.append(doc)

                # Chunk sửa đổi này có thể lại tiếp tục bị sửa đổi tiếp -> thêm vào tầng kế
                for ref in (doc.get('metadata', {}).get('amended_by') or []):
                    key = self._ref_key(ref)
                    if key not in seen_ref_keys:
                        seen_ref_keys.add(key)
                        next_frontier.append(ref)

            frontier = next_frontier

        return all_amending_docs[:max_total]

    def _format_amendment_ref(self, ref):
        """Định dạng 1 tham chiếu amended_by thành chuỗi dễ đọc, VD: '141/2026 (Điều 1, Khoản 1)'."""
        law_number = ref.get('law_number', '?')
        law_year = ref.get('law_year', '?')
        parts = [f"Điều {ref['article']}"] if ref.get('article') else []
        if ref.get('section'):
            parts.append(f"Khoản {ref['section']}")
        suffix = f" ({', '.join(parts)})" if parts else ""
        return f"{law_number}/{law_year}{suffix}"

    def get_sessions(self, user_token):
        if not self.url or not self.key or not user_token:
            return []
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/chat_sessions?order=updated_at.desc", 
                headers=headers
            )
            if response.status_code == 200:
                sessions = response.json()
                for s in sessions:
                    if "title" in s and s["title"]:
                        decrypted = self.encryption_service.decrypt_text(s["title"])
                        if decrypted == "[Lỗi giải mã nội dung]":
                            # Fallback cho các session cũ chưa được mã hóa tiêu đề
                            decrypted = s["title"]
                        s["title"] = decrypted
                return sessions
            else:
                logger.error(f"Error fetching sessions: {response.text}")
        except Exception as e:
            logger.error(f"Exception fetching sessions: {e}")
        return []

    def get_messages(self, session_id, user_token):
        if not self.url or not self.key or not session_id or not user_token:
            return []
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/chat_messages",
                headers=headers,
                params={"session_id": f"eq.{session_id}", "order": "created_at.asc"}
            )
            if response.status_code == 200:
                messages = response.json()
                for m in messages:
                    if "content" in m:
                        m["content"] = self.encryption_service.decrypt_text(m["content"])
                return messages
            else:
                logger.error(f"Error fetching messages: {response.text}")
        except Exception as e:
            logger.error(f"Exception fetching messages: {e}")
        return []

    def delete_session(self, session_id, user_token):
        if not self.url or not self.key or not session_id or not user_token:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.delete(
                f"{self.url}/rest/v1/chat_sessions",
                headers=headers,
                params={"id": f"eq.{session_id}"}
            )
            if response.status_code in (200, 204):
                return True
            else:
                logger.error(f"Error deleting session: {response.text}")
        except Exception as e:
            logger.error(f"Exception deleting session: {e}")
        return False

    def get_user_files(self, user_token):
        if not self.url or not self.key or not user_token:
            return []
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/user_files?select=file_name,file_type,created_at", 
                headers=headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error fetching user files: {response.text}")
        except Exception as e:
            logger.error(f"Exception fetching user files: {e}")
        return []

    def save_user_file(self, user_token, file_name, file_type, attached_file_url=None):
        if not self.url or not self.key or not user_token or not file_name:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        
        # Kiểm tra xem tệp tin đã được lưu trong DB chưa để tránh trùng lặp
        try:
            check_resp = requests.get(
                f"{self.url}/rest/v1/user_files",
                headers=headers,
                params={"file_name": f"eq.{file_name}"}
            )
            if check_resp.status_code == 200 and len(check_resp.json()) > 0:
                return True
        except Exception as e:
            logger.error(f"Exception checking user file: {e}")
            
        data = {
            "file_name": file_name,
            "file_type": file_type,
            "attached_file_url": attached_file_url
        }
        try:
            response = requests.post(
                f"{self.url}/rest/v1/user_files", 
                headers=headers, 
                json=data
            )
            return response.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Exception saving user file: {e}")
        return False

    def delete_user_file(self, user_token, file_name):
        if not self.url or not self.key or not user_token or not file_name:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.delete(
                f"{self.url}/rest/v1/user_files",
                headers=headers,
                params={"file_name": f"eq.{file_name}"}
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Exception deleting user file: {e}")
        return False

