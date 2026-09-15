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

    def save_message(self, session_id, role, content, user_token, file_name=None, file_type=None, tax_snapshot=None, sources=None):
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
            
        # Kết hợp tax_snapshot và sources thành đối tượng JSONB nếu cần
        tax_result_data = {}
        if tax_snapshot:
            tax_result_data["tax_snapshot"] = tax_snapshot
        if sources:
            tax_result_data["sources"] = sources
            
        if tax_result_data:
            data["tax_result_snapshot"] = tax_result_data
            
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

    def search_tax_laws(self, query_vector):
        if not self.url or not self.key or not query_vector:
            return "Thiếu cấu hình Supabase hoặc Vector.", []
        
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        # Yêu cầu RPC trả về cả trường metadata
        response = requests.post(
            f"{self.url}/rest/v1/rpc/match_tax_documents", 
            headers=headers, 
            json={'query_embedding': query_vector, 'match_threshold': 0.3, 'match_count': 50}
        )
        
        if response.status_code == 200:
            results = response.json()
            if results:
                # (1). Lọc kết quả với chiến thuật Đa dạng hóa (Round-Robin)
                from collections import defaultdict

                grouped_results = defaultdict(list)
                for r in results:
                    meta = r.get('metadata', {})
                    law_name = meta.get('law_name', r.get('title', 'Tài liệu').split(' - ')[0])
                    # Lưu trữ các đoạn vào danh sách riêng của từng văn bản
                    # (Vì DB đã ORDER BY ASC, các đoạn trong list này đã được sắp xếp từ giống nhất đến ít giống nhất)
                    grouped_results[law_name].append(r)

                filtered_results = []
                max_total_chunks = 8
                max_per_doc = 3 # Không lấy quá 3 đoạn/văn bản để tránh loãng
                
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

                # (2) & (3). Tìm văn bản mới hơn và trích xuất các đoạn sửa đổi/bổ sung
                filtered_results, amendment_docs = self._check_for_updates(filtered_results)

                # Sắp xếp đa tầng: Năm > Ngày ban hành > Số hiệu
                def get_sort_key(item):
                    meta = item.get('metadata', {})
                    law_name = meta.get('law_name', item.get('title', ''))
                    doc_id = self._parse_doc_id(law_name)
                    issue_date = item.get('issue_date') or '0000-00-00'
                    
                    if doc_id:
                        # Đưa issue_date lên trước number để fix lỗi cross-type
                        return (doc_id['year'], issue_date, doc_id['number'])
                        
                    # Fallback nếu văn bản không có chuẩn số hiệu
                    year_from_date = int(issue_date[:4]) if issue_date != '0000-00-00' else 0
                    return (year_from_date, issue_date, 0)

                filtered_results.sort(key=get_sort_key, reverse=True)

                # TUYỆT ĐỐI KHÔNG TRIM (cắt) filtered_results sau khi đã sort theo Ngày/Năm vì sẽ vô tình xóa mất các kết quả gốc chứa câu trả lời chính xác nhất.
                # Chỉ giới hạn số lượng amendment_docs để không làm loãng Context.
                max_amendments = 12
                
                # Loại bỏ các đoạn trùng lặp trong amendment_docs (nếu có)
                unique_amendments = []
                seen_amends = set()
                for am_doc in amendment_docs:
                    doc_id_str = str(am_doc.get('id', am_doc.get('content', '')[:50]))
                    if doc_id_str not in seen_amends:
                        seen_amends.add(doc_id_str)
                        unique_amendments.append(am_doc)
                
                amendment_docs = unique_amendments[:max_amendments]

                # --- XÂY DỰNG CONTEXT CHO AI ---
                context = "Dưới đây là cơ sở dữ liệu pháp luật (Ngữ cảnh pháp lý) được trích xuất từ hệ thống:\n\n"
                
                sources = []
                # Đưa các đoạn gốc vào Context
                context += "=== CÁC QUY ĐỊNH GỐC TÌM ĐƯỢC ===\n"
                for idx, row in enumerate(filtered_results):
                    meta = row.get('metadata', {})
                    law_name = meta.get('law_name', row.get('title', 'Quy định thuế'))
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
                    if row.get('amended_by'):
                        amended_info = f"\n⚠️ CẢNH BÁO: Điều/Khoản này có thể ĐÃ BỊ SỬA ĐỔI/BÃI BỎ bởi: {row['amended_by']}."
                    
                    context += f"--- [{law_name}] (Điều: {article}, Khoản: {section}) ---\nNội dung: {row.get('content', '')}{amended_info}\n\n"

                # Đưa các đoạn sửa đổi (từ bước 3) vào Context để AI so sánh
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

    def _check_for_updates(self, results):
        """
        Thực hiện Step (2) và (3):
        Tìm các văn bản mới hơn (bất kể loại văn bản), kiểm tra xem có sửa đổi/cập nhật văn bản gốc không.
        Sử dụng cơ chế Batch Query để giảm số lượng request HTTP từ O(N) xuống O(1).
        """
        if not results: return results, []
        
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        
        # 1. Trích xuất tất cả thông tin số hiệu tài liệu duy nhất từ kết quả tìm kiếm
        doc_infos = {}
        for row in results:
            meta = row.get('metadata', {})
            law_name = meta.get('law_name')
            if law_name and law_name not in doc_infos:
                doc_info = self._parse_doc_id(law_name)
                if doc_info:
                    doc_infos[law_name] = doc_info
                    
        if not doc_infos:
            return results, []
            
        # 2. Xây dựng filter query OR để kéo toàn bộ các tài liệu sửa đổi tiềm năng trong 1 request duy nhất
        or_conditions = []
        for doc_info in doc_infos.values():
            or_conditions.append(f"content.ilike.*{doc_info['full']}*")
            
        or_filter = f"({','.join(or_conditions)})"
        
        params = {
            "select": "content,metadata,issue_date",
            "or": or_filter
        }
        url = f"{self.url}/rest/v1/tax_documents"
        
        all_candidates = []
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                all_candidates = resp.json()
            else:
                logger.error(f"Error fetching amenders in batch: {resp.text}")
        except Exception as e:
            logger.error(f"Exception fetching amenders in batch: {e}")
            
        # 3. Phân tích và đối chiếu kết quả trong bộ nhớ (In-memory cross-reference)
        checked_law_names = {}
        amendment_docs = []
        keywords = ["sửa đổi", "bổ sung", "bãi bỏ", "thay thế", "áp dụng", "điều chỉnh"]
        
        for row in results:
            meta = row.get('metadata', {})
            law_name = meta.get('law_name')
            
            if not law_name: continue
            doc_info = doc_infos.get(law_name)
            if not doc_info: continue
            
            if law_name in checked_law_names:
                row['amended_by'] = checked_law_names[law_name]
                continue
                
            amender_law_name = None
            
            # Quét qua danh sách ứng viên đã fetch được
            for item in all_candidates:
                item_content = item.get('content', '')
                # Kiểm tra xem tài liệu ứng viên này có chứa số hiệu của tài liệu đang xét hay không
                if doc_info['full'] not in item_content:
                    continue
                    
                item_meta = item.get('metadata', {})
                item_law_name = item_meta.get('law_name')
                item_info = self._parse_doc_id(item_law_name)
                if not item_info: continue
                
                # LOGIC SO SÁNH THỜI GIAN ĐA DẠNG:
                is_newer = False
                
                # 1. So sánh Năm
                if item_info['year'] > doc_info['year']:
                    is_newer = True
                # 2. Nếu cùng Năm
                elif item_info['year'] == doc_info['year']:
                    item_date = item.get('issue_date', '0000-00-00')
                    doc_date = row.get('issue_date', '0000-00-00')
                    
                    if item_date != '0000-00-00' and doc_date != '0000-00-00':
                        if item_date > doc_date:
                            is_newer = True
                    elif item_info['type'] == doc_info['type'] and item_info['number'] > doc_info['number']:
                        is_newer = True
                        
                if is_newer:
                    content_lower = item_content.lower()
                    if any(kw in content_lower for kw in keywords):
                        amender_law_name = item_law_name
                        if item not in amendment_docs:
                            amendment_docs.append(item)
                            
            if amender_law_name:
                checked_law_names[law_name] = amender_law_name
                row['amended_by'] = amender_law_name
            else:
                checked_law_names[law_name] = None
                
        return results, amendment_docs



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

    def get_business_settings(self, user_token):
        if not self.url or not self.key or not user_token:
            return {"business_name": "My Business", "business_category": "ban_buon_ban_le", "declaration_type": "quy"}
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/business_settings", 
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    record = data[0]
                    # Giải mã dữ liệu (hỗ trợ fallback nếu dữ liệu cũ chưa mã hóa)
                    dec_name = self.encryption_service.decrypt_text(record["business_name"])
                    if dec_name == "[Lỗi giải mã nội dung]":
                        dec_name = record["business_name"]
                    record["business_name"] = dec_name
                    
                    dec_cat = self.encryption_service.decrypt_text(record["business_category"])
                    if dec_cat == "[Lỗi giải mã nội dung]":
                        dec_cat = record["business_category"]
                    record["business_category"] = dec_cat
                    
                    dec_type = self.encryption_service.decrypt_text(record.get("declaration_type", ""))
                    if dec_type == "[Lỗi giải mã nội dung]" or not dec_type:
                        dec_type = record.get("declaration_type", "quy")
                    record["declaration_type"] = dec_type
                    return record
                else:
                    # Tạo cấu hình mặc định (mã hóa trước khi gửi đi)
                    enc_name = self.encryption_service.encrypt_text("My Business")
                    enc_cat = self.encryption_service.encrypt_text("ban_buon_ban_le")
                    enc_type = self.encryption_service.encrypt_text("quy")
                    create_resp = requests.post(
                        f"{self.url}/rest/v1/business_settings",
                        headers={**headers, "Prefer": "return=representation"},
                        json={"business_name": enc_name, "business_category": enc_cat, "declaration_type": enc_type}
                    )
                    if create_resp.status_code in (200, 201):
                          create_data = create_resp.json()
                          if create_data and len(create_data) > 0:
                              record = create_data[0]
                              record["business_name"] = "My Business"
                              record["business_category"] = "ban_buon_ban_le"
                              record["declaration_type"] = "quy"
                              return record
            else:
                logger.error(f"Error fetching business settings: {response.text}")
        except Exception as e:
            logger.error(f"Exception fetching business settings: {e}")
        return {"business_name": "My Business", "business_category": "ban_buon_ban_le", "declaration_type": "quy"}

    def update_business_settings(self, user_token, business_name, business_category, declaration_type="quy"):
        if not self.url or not self.key or not user_token:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            # First fetch to get the record ID
            settings = self.get_business_settings(user_token)
            if not settings or "id" not in settings:
                return False
            
            settings_id = settings["id"]
            # Mã hóa dữ liệu trước khi cập nhật
            enc_name = self.encryption_service.encrypt_text(business_name)
            enc_cat = self.encryption_service.encrypt_text(business_category)
            enc_type = self.encryption_service.encrypt_text(declaration_type)
            
            current_time = datetime.now(timezone.utc).isoformat()

            # Try to update with declaration_type
            response = requests.patch(
                f"{self.url}/rest/v1/business_settings",
                headers=headers,
                params={"id": f"eq.{settings_id}"},
                json={
                    "business_name": enc_name, 
                    "business_category": enc_cat,
                    "declaration_type": enc_type,
                    "updated_at": current_time
                }
            )
            if response.status_code not in (200, 204):
                # Fallback if declaration_type column does not exist yet
                response = requests.patch(
                    f"{self.url}/rest/v1/business_settings",
                    headers=headers,
                    params={"id": f"eq.{settings_id}"},
                    json={
                        "business_name": enc_name, 
                        "business_category": enc_cat,
                        "updated_at": current_time
                    }
                )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Exception updating business settings: {e}")
        return False

    def get_transactions(self, user_token):
        if not self.url or not self.key or not user_token:
            return []
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(
                f"{self.url}/rest/v1/transactions?order=date.desc,created_at.desc", 
                headers=headers
            )
            if response.status_code == 200:
                txs = response.json()
                # Giải mã từng giao dịch (hỗ trợ fallback nếu dữ liệu cũ chưa mã hóa)
                for tx in txs:
                    if "amount" in tx and tx["amount"]:
                        dec_amount = self.encryption_service.decrypt_text(tx["amount"])
                        if dec_amount == "[Lỗi giải mã nội dung]":
                            dec_amount = tx["amount"]
                        try:
                            tx["amount"] = float(dec_amount)
                        except ValueError:
                            tx["amount"] = 0.0
                    if "description" in tx and tx["description"]:
                        dec_desc = self.encryption_service.decrypt_text(tx["description"])
                        if dec_desc == "[Lỗi giải mã nội dung]":
                            dec_desc = tx["description"]
                        tx["description"] = dec_desc
                return txs
            else:
                logger.error(f"Error fetching transactions: {response.text}")
        except Exception as e:
            logger.error(f"Exception fetching transactions: {e}")
        return []

    def add_transaction(self, user_token, date, amount, description):
        if not self.url or not self.key or not user_token:
            return None
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        # Mã hóa trước khi lưu
        enc_amount = self.encryption_service.encrypt_text(str(amount))
        enc_desc = self.encryption_service.encrypt_text(description)
        data = {
            "date": date,
            "amount": enc_amount,
            "description": enc_desc
        }
        try:
            response = requests.post(
                f"{self.url}/rest/v1/transactions", 
                headers=headers, 
                json=data
            )
            if response.status_code in (200, 201):
                res = response.json()
                if res and len(res) > 0:
                    tx = res[0]
                    tx["amount"] = amount
                    tx["description"] = description
                    return tx
            else:
                logger.error(f"Error adding transaction: {response.text}")
        except Exception as e:
            logger.error(f"Exception adding transaction: {e}")
        return None

    def update_transaction(self, user_token, transaction_id, date, amount, description):
        if not self.url or not self.key or not user_token or not transaction_id:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        # Mã hóa trước khi cập nhật
        enc_amount = self.encryption_service.encrypt_text(str(amount))
        enc_desc = self.encryption_service.encrypt_text(description)
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        data = {
            "date": date,
            "amount": enc_amount,
            "description": enc_desc,
            "updated_at": current_time
        }
        try:
            response = requests.patch(
                f"{self.url}/rest/v1/transactions",
                headers=headers,
                params={"id": f"eq.{transaction_id}"},
                json=data
            )
            if response.status_code not in (200, 204):
                # Fallback nếu cột updated_at chưa tồn tại trên database
                fallback_data = {
                    "date": date,
                    "amount": enc_amount,
                    "description": enc_desc
                }
                response = requests.patch(
                    f"{self.url}/rest/v1/transactions",
                    headers=headers,
                    params={"id": f"eq.{transaction_id}"},
                    json=fallback_data
                )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Exception updating transaction: {e}")
        return False

    def delete_transaction(self, user_token, transaction_id):
        if not self.url or not self.key or not user_token or not transaction_id:
            return False
        headers = {
            "apikey": self.key, 
            "Authorization": f"Bearer {user_token}", 
            "Content-Type": "application/json"
        }
        try:
            response = requests.delete(
                f"{self.url}/rest/v1/transactions",
                headers=headers,
                params={"id": f"eq.{transaction_id}"}
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Exception deleting transaction: {e}")
        return False

