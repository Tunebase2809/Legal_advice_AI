import os
import sys
import json
import argparse
import requests
import re
import io
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from services.guard_service import PROVISION_TYPE_LABELS

# Đảm bảo stdout hỗ trợ UTF-8 để in tiếng Việt và emoji trên Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Tải các biến môi trường
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 1. TƯƠNG TÁC SUPABASE VECTOR DB
# ==========================================
def embed_text(text, title=None):
    """Biến đổi văn bản thành Vector bằng Gemini Embedding 2 (768 chiều) với cơ chế thử lại"""
    for attempt in range(3):
        try:
            kwargs = {
                "model": "gemini-embedding-2",
                "contents": text,
                "config": types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
            }
            if title:
                kwargs["config"].title = title
                
            result = client.models.embed_content(**kwargs)
            return result.embeddings[0].values
        except Exception as e:
            if "503" in str(e) or "overloaded" in str(e).lower():
                wait_time = (attempt + 1) * 2
                print(f"      [!] Server quá tải (503), đang thử lại sau {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Lỗi nhúng văn bản: {e}")
                return None
    return None

def insert_to_supabase(data):
    """Lưu Vector vào bảng legal_documents"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/legal_documents", headers=headers, json=data)
    if response.status_code in [200, 201]:
        print(f"  [+] Đã lưu: {data['title']} - {data['content'][:40]}...")
    else:
        print(f"  [-] Lỗi lưu DB ({response.status_code}): {response.text}")

def backfill_amended_by(chunks):
    """
    Chạy SAU KHI các chunk mới đã được insert. Với mỗi chunk có "amendments_to"
    khác rỗng, tìm (các) chunk CŨ tương ứng trong DB (khớp law_number/law_year/
    article[/section]) và ghi ngược "amended_by" vào metadata của chúng.

    Đây là bước thay thế cho việc quét/so sánh ilike + ngày tháng ở mỗi câu hỏi
    của người dùng (search_legal_documents trước đây) - quan hệ sửa đổi giờ được
    tính MỘT LẦN lúc ingest, runtime chỉ cần đọc "amended_by" có sẵn.

    LƯU Ý: hàm này chỉ xét "amendments_to" của các chunk VỪA insert (tham số
    "chunks"). Nếu văn bản sửa đổi được ingest TRƯỚC văn bản cũ mà nó sửa đổi,
    lúc chạy hàm này văn bản cũ chưa tồn tại trong DB nên sẽ không tìm thấy gì
    để ghi "amended_by" - dùng backfill_all_amended_by() bên dưới để quét lại
    toàn bộ DB và bù cho các trường hợp ingest sai thứ tự này.
    """
    _apply_amendments_backfill(chunks)
    _apply_supersedes_backfill(chunks)

def _apply_supersedes_backfill(chunks):
    """
    Với mỗi chunk có "supersedes" (văn bản này thay thế toàn bộ văn bản khác),
    ghi "superseded_by" = law_name của văn bản mới vào MỌI chunk của văn bản cũ
    đang có trong DB. "superseded_by" chỉ dùng để hiển thị cảnh báo
    "ĐÃ HẾT HIỆU LỰC", không dùng để so khớp.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    done = set()
    any_marked = False
    for item in chunks:
        meta = item.get("metadata", {}) or {}
        new_law_name = meta.get("law_name")
        for target in (meta.get("supersedes") or []):
            if not target.get("law_suffix"):
                continue
            key = (target["law_number"], target["law_year"], target["law_suffix"], new_law_name)
            if not new_law_name or key in done:
                continue
            done.add(key)

            marked = 0
            offset, page_size = 0, 1000
            while True:
                try:
                    resp = requests.get(
                        f"{SUPABASE_URL}/rest/v1/legal_documents",
                        headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + page_size - 1}"},
                        params={
                            "select": "id,metadata",
                            "metadata->>law_number": f"eq.{target['law_number']}",
                            "metadata->>law_year": f"eq.{target['law_year']}",
                            "metadata->>law_suffix": f"eq.{target['law_suffix']}",
                        },
                        timeout=30
                    )
                except Exception as e:
                    print(f"  [!] Lỗi truy vấn văn bản bị thay thế: {e}")
                    break
                if resp.status_code not in (200, 206):
                    break
                page = resp.json()
                for row in page:
                    row_meta = row.get("metadata") or {}
                    if row_meta.get("superseded_by") == new_law_name:
                        continue
                    row_meta["superseded_by"] = new_law_name
                    try:
                        patch_resp = requests.patch(
                            f"{SUPABASE_URL}/rest/v1/legal_documents",
                            headers=headers,
                            params={"id": f"eq.{row['id']}"},
                            json={"metadata": row_meta}
                        )
                        if patch_resp.status_code in (200, 204):
                            marked += 1
                    except Exception as e:
                        print(f"  [!] Lỗi ghi superseded_by: {e}")
                if len(page) < page_size:
                    break
                offset += page_size

            if marked:
                any_marked = True
                print(f"  [+] {new_law_name} thay thế toàn bộ văn bản {target['law_number']}/{target['law_year']}/{target['law_suffix']}: "
                      f"đã đánh dấu 'ĐÃ HẾT HIỆU LỰC' cho {marked} đoạn.")

    if any_marked:
        print("✅ Đã cập nhật trạng thái hết hiệu lực (superseded_by) cho các văn bản cũ liên quan.")

def backfill_all_amended_by():
    """
    Quét TOÀN BỘ bảng legal_documents (không chỉ batch vừa insert) để tìm mọi
    chunk có "amendments_to" khác rỗng rồi ghi lại "amended_by" cho văn bản cũ
    tương ứng. Dùng để sửa lại dữ liệu khi các văn bản được ingest không đúng
    thứ tự thời gian (văn bản mới ingest trước văn bản cũ mà nó sửa đổi).
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    print("🔍 Đang quét toàn bộ cơ sở dữ liệu để tìm các văn bản có khai báo sửa đổi (amendments_to)...")
    items_with_amendments = []
    page_size = 1000
    offset = 0
    while True:
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/legal_documents",
                headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + page_size - 1}"},
                params={"select": "metadata"},
                timeout=30
            )
        except Exception as e:
            print(f"  [!] Lỗi truy vấn danh sách văn bản: {e}")
            return

        if resp.status_code not in (200, 206):
            print(f"  [!] Lỗi truy vấn danh sách văn bản ({resp.status_code}): {resp.text}")
            return

        page = resp.json()
        for row in page:
            meta = row.get("metadata") or {}
            if meta.get("amendments_to") or meta.get("supersedes"):
                items_with_amendments.append({"metadata": meta})

        if len(page) < page_size:
            break
        offset += page_size

    if not items_with_amendments:
        print("Không tìm thấy văn bản nào có khai báo sửa đổi (amendments_to).")
        return

    print(f"Tìm thấy {len(items_with_amendments)} chunk có khai báo sửa đổi/thay thế. Đang đối chiếu và ghi lại amended_by/superseded_by...")
    _apply_amendments_backfill(items_with_amendments)
    _apply_supersedes_backfill(items_with_amendments)

def _apply_amendments_backfill(chunks):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    any_backfilled = False
    for item in chunks:
        meta = item.get("metadata", {}) or {}
        amendments = meta.get("amendments_to") or []
        if not amendments:
            continue

        amender_ref = {
            "law_number": meta.get("law_number"),
            "law_year": meta.get("law_year"),
            "law_suffix": meta.get("law_suffix"),
            "article": meta.get("article"),
            "section": meta.get("section") if meta.get("section") not in (None, "", "N/A") else None
        }
        if not amender_ref["law_number"] or not amender_ref["law_year"] or not amender_ref["law_suffix"]:
            continue

        for target in amendments:
            if not target.get("law_suffix"):
                continue
            params = {
                "select": "id,metadata",
                "metadata->>law_number": f"eq.{target['law_number']}",
                "metadata->>law_year": f"eq.{target['law_year']}",
                "metadata->>law_suffix": f"eq.{target['law_suffix']}",
                "metadata->>article": f"eq.{target['article']}",
            }
            if target.get("section"):
                params["metadata->>section"] = f"eq.{target['section']}"

            try:
                resp = requests.get(f"{SUPABASE_URL}/rest/v1/legal_documents", headers=headers, params=params, timeout=10)
            except Exception as e:
                print(f"  [!] Lỗi truy vấn văn bản cũ để backfill: {e}")
                continue

            if resp.status_code != 200:
                continue

            for row in resp.json():
                row_meta = row.get("metadata") or {}
                amended_by_list = row_meta.get("amended_by") or []
                if amender_ref in amended_by_list:
                    continue
                amended_by_list.append(amender_ref)
                row_meta["amended_by"] = amended_by_list
                try:
                    patch_resp = requests.patch(
                        f"{SUPABASE_URL}/rest/v1/legal_documents",
                        headers=headers,
                        params={"id": f"eq.{row['id']}"},
                        json={"metadata": row_meta}
                    )
                    if patch_resp.status_code in (200, 204):
                        any_backfilled = True
                        target_section_str = f" Khoản {target.get('section')}" if target.get("section") else ""
                        print(f"  [+] Backfill: {meta.get('law_name')} (Điều {amender_ref['article']}) sửa đổi "
                              f"Điều {target['article']}{target_section_str} của văn bản {target['law_number']}/{target['law_year']}/{target['law_suffix']}")
                except Exception as e:
                    print(f"  [!] Lỗi ghi amended_by: {e}")

    if any_backfilled:
        print("✅ Đã cập nhật quan hệ sửa đổi (amended_by) cho các văn bản cũ liên quan.")

# ==========================================
# 2. AI TRÍCH XUẤT VÀ CHIA ĐOẠN (STRUCTURAL CHUNKING)
# ==========================================

# Phân loại "dạng quy định" cho từng chunk.
# Danh sách P1-P9 lấy từ PROVISION_TYPE_LABELS trong services/guard_service.py (nguồn duy nhất),
# để tránh 2 nơi định nghĩa cùng 1 danh sách rồi lệch nhau khi sửa sau này -
# guard_service.py dùng chính danh sách đó để đoán "dạng câu hỏi" và hiển thị
# nhãn đầy đủ cho người dùng lúc tra cứu.
PROVISION_TYPE_LEGEND = "\n" + "\n".join(f"- {code}: {label}" for code, label in PROVISION_TYPE_LABELS.items()) + "\n"

AMENDMENTS_TO_INSTRUCTION = """
6. Phát hiện SỬA ĐỔI/BỔ SUNG văn bản khác: Nếu nội dung chunk này nói rõ nó đang sửa đổi/bổ sung/bãi bỏ một Điều/Khoản CỤ THỂ của một văn bản pháp luật KHÁC (có nêu rõ số hiệu văn bản kiểu "68/2026/NĐ-CP"), hãy điền trường "amendments_to" là một MẢNG liệt kê từng Điều/Khoản bị sửa, mỗi phần tử có dạng:
   {"law_number": "68", "law_year": 2026, "law_suffix": "NĐ-CP", "article": "3", "section": null}
   ("law_suffix" là phần đuôi ký hiệu văn bản đúng như trong câu, VD "68/2026/NĐ-CP" -> "NĐ-CP", "41/2024/QH15" -> "QH15", "18/2026/TT-BTC" -> "TT-BTC"; BẮT BUỘC phải có để phân biệt các văn bản trùng số/năm nhưng khác loại. Nếu câu không nêu ký hiệu thì để "law_suffix": null.
   article/section lấy đúng số được nêu trong câu; nếu câu chỉ ghi "tại Điều 3, Điều 4, khoản 1 Điều 8..." thì phải tách thành NHIỀU phần tử riêng biệt, mỗi phần tử 1 Điều/Khoản; nếu sửa cả Điều không chỉ rõ Khoản thì để "section": null).
   Nếu chunk KHÔNG sửa đổi văn bản nào khác, để "amendments_to": [].
7. Phát hiện THAY THẾ/HẾT HIỆU LỰC TOÀN BỘ văn bản khác: Nếu chunk này (thường là điều khoản thi hành/hiệu lực thi hành) nói rõ MỘT VĂN BẢN KHÁC "hết hiệu lực thi hành", "được thay thế" hoặc "bị bãi bỏ" TOÀN BỘ (không phải chỉ một Điều/Khoản - trường hợp đó thuộc "amendments_to"), hãy điền trường "supersedes" là một MẢNG, mỗi phần tử có dạng:
   {"law_number": "58", "law_year": 2014, "law_suffix": "QH13"}
   (law_number chỉ gồm phần số, không kèm năm hay ký hiệu loại văn bản, VD "58/2014/QH13" -> "58", 2014 và "QH13"; nếu câu không nêu ký hiệu thì để "law_suffix": null). Chỉ liệt kê văn bản được nêu rõ là hết hiệu lực toàn bộ; KHÔNG liệt kê các văn bản chỉ được nhắc tới với tư cách đã sửa đổi/bổ sung văn bản bị thay thế đó, trừ khi chính chúng cũng được nêu rõ là hết hiệu lực. Nếu chunk không có nội dung này, để "supersedes": [].
8. Phân loại "provision_type" cho chunk theo danh sách sau (chọn đúng 1 mã, hoặc null nếu không rõ):
""" + PROVISION_TYPE_LEGEND
def extract_metadata_with_gemini(header_text):
    """Trích xuất tên luật, ngày ban hành và loại văn bản từ phần đầu tài liệu"""
    print("⏳ Đang trích xuất thông tin chung của tài liệu (Tên văn bản, ngày ban hành)...")
    prompt = """
    Hãy đọc phần đầu của văn bản pháp luật sau và trích xuất thông tin dưới dạng JSON:
    {
      "law_name": "Tên/Số hiệu văn bản đầy đủ (ví dụ: Luật Quản lý thuế số 108/2025/QH15 hoặc Thông tư số: 18/2026/TT-BTC)",
      "issue_date": "Ngày ban hành định dạng YYYY-MM-DD",
      "type": "Loại văn bản (ví dụ: Luật, Nghị định, Thông tư, Quyết định)"
    }
    Lưu ý: Chỉ trả về JSON duy nhất, không thêm giải thích nào khác. Nếu không tìm thấy thông tin nào, hãy để null.
    """
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[header_text, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            text_resp = response.text.strip()
            text_resp = re.sub(r'```json\n|```json|```', '', text_resp).strip()
            metadata = json.loads(text_resp)
            return metadata
        except Exception as e:
            if "503" in str(e) or "overloaded" in str(e).lower():
                wait_time = (attempt + 1) * 2
                print(f"  [!] Server bận, đang thử lại trích xuất metadata sau {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"⚠️ Không thể trích xuất metadata bằng AI: {e}. Sẽ sử dụng chế độ mặc định.")
                break
    return {
        "law_name": None,
        "issue_date": None,
        "type": None
    }

def split_text_by_articles(text, max_chars=25000):
    """Chia nhỏ văn bản dựa trên ranh giới của Điều hoặc Chương để đảm bảo không bị mất đoạn và vừa vặn token"""
    lines = text.split('\n')
    sections = []
    current_section = []
    current_length = 0
    
    # Nhận diện các dòng bắt đầu bằng "Điều " hoặc "Chương "
    pattern = re.compile(r'^\s*(Điều \d+|Chương [IVXLCDM\d]+)', re.IGNORECASE)
    
    for line in lines:
        line_len = len(line) + 1  # Cộng thêm ký tự newline
        # Nếu dòng tiếp theo làm vượt quá độ dài tối đa, đẩy đoạn hiện tại đi
        if current_length + line_len > max_chars and current_section:
            sections.append('\n'.join(current_section))
            current_section = [line]
            current_length = line_len
        else:
            # Ngắt đoạn khi gặp "Điều" hoặc "Chương" và độ dài đoạn cũ đã đủ lớn (> 12000 kí tự)
            if pattern.match(line) and current_length > 12000:
                sections.append('\n'.join(current_section))
                current_section = [line]
                current_length = line_len
            else:
                current_section.append(line)
                current_length += line_len
                
    if current_section:
        sections.append('\n'.join(current_section))
        
    return sections

def _parse_doc_ref(target):
    """
    Chuẩn hóa 1 tham chiếu tới văn bản khác do AI trả về thành (law_number, law_year,
    law_suffix). AI đôi khi trả số hiệu đầy đủ ("58/2014/QH13") thay vì số trơn ("58")
    nên tách lại bằng regex. Trả về None nếu thiếu số/năm/ký hiệu: không có ký hiệu
    (QH15, NĐ-CP, TT-BTC...) thì không phân biệt được các văn bản trùng số + năm nhưng
    khác loại (VD 41/2024/QH15 và 41/2024/NĐ-CP), thà bỏ qua còn hơn ghi nhầm quan hệ.
    """
    law_number = str(target.get("law_number") or "")
    law_year = target.get("law_year")
    law_suffix = target.get("law_suffix")
    match_t = re.search(r'(\d+)/(\d{4})(?:/([\w-]+))?', law_number)
    if match_t:
        law_number, law_year = match_t.group(1), match_t.group(2)
        law_suffix = match_t.group(3) or law_suffix
    try:
        law_year = int(law_year)
    except (TypeError, ValueError):
        return None
    law_suffix = str(law_suffix or "").strip().upper()
    if not law_number.isdigit() or not law_suffix:
        return None
    return law_number, law_year, law_suffix

def normalize_amendment_metadata(meta):
    """
    Chuẩn hóa metadata liên quan tới quan hệ sửa đổi văn bản của 1 chunk, SAU KHI
    Gemini đã bóc tách xong (meta["law_name"] đã được làm sạch ở bước trước đó):
    - Tách "law_number"/"law_year"/"law_suffix" trực tiếp từ law_name bằng regex
      (đáng tin cậy hơn để AI tự trích xuất số), dùng để so khớp chính xác khi
      backfill/tra cứu thay vì phải "ilike" chuỗi con trong content. Bộ 3 này mới
      định danh duy nhất 1 văn bản: 41/2024/QH15 khác 41/2024/NĐ-CP.
    - Lọc "amendments_to"/"supersedes" chỉ giữ lại các mục đủ thông tin, ép kiểu để
      so khớp nhất quán khi query PostgREST sau này.
    - Luôn khởi tạo "amended_by": [] - trường này CHỈ được điền bởi
      backfill_amended_by() sau khi văn bản mới được insert, không phải do AI
      bóc tách tự suy ra (lúc bóc tách 1 văn bản, ta không biết văn bản nào
      trong tương lai sẽ sửa nó).
    """
    law_name = meta.get("law_name") or ""
    match_l = re.search(r'(\d+)/(\d{4})/([\w-]+)', law_name)
    if match_l:
        meta["law_number"] = match_l.group(1)
        meta["law_year"] = int(match_l.group(2))
        meta["law_suffix"] = match_l.group(3).upper()

    normalized_targets = []
    for target in (meta.get("amendments_to") or []):
        if not isinstance(target, dict):
            continue
        ref = _parse_doc_ref(target)
        article = target.get("article")
        if not ref or not article:
            continue
        section = target.get("section")
        normalized_targets.append({
            "law_number": ref[0],
            "law_year": ref[1],
            "law_suffix": ref[2],
            "article": str(article),
            "section": str(section) if section not in (None, "", "N/A") else None
        })
    meta["amendments_to"] = normalized_targets
    meta["amended_by"] = []

    normalized_supersedes = []
    for target in (meta.get("supersedes") or []):
        if not isinstance(target, dict):
            continue
        ref = _parse_doc_ref(target)
        if not ref:
            continue
        if ref == (meta.get("law_number"), meta.get("law_year"), meta.get("law_suffix")):
            continue
        entry = {"law_number": ref[0], "law_year": ref[1], "law_suffix": ref[2]}
        if entry not in normalized_supersedes:
            normalized_supersedes.append(entry)
    meta["supersedes"] = normalized_supersedes

def extract_and_chunk_with_gemini(content_parts, metadata_hint=None):
    print("\n⏳ Đang nhờ AI Gemini bóc tách tài liệu theo cấu trúc pháp luật (Điều > Khoản > Điểm)...")
    model_name = "gemini-3.1-flash-lite"

    if isinstance(content_parts, str):
        # 1. Trích xuất metadata trước từ phần đầu tiên của văn bản.
        # Nếu đã có "metadata_hint" (dò được trực tiếp bằng regex từ trang nguồn,
        # ví dụ div#divContentDoc trên thuvienphapluat.vn) thì dùng luôn, đáng tin
        # cậy hơn và đỡ tốn 1 lượt gọi AI so với việc để AI tự đoán từ nội dung dài.
        if metadata_hint and metadata_hint.get("law_name"):
            print(f"🔹 Dùng thông tin nhận diện trực tiếp từ trang nguồn (bỏ qua bước AI đoán tên văn bản).")
            metadata = metadata_hint
        else:
            metadata = extract_metadata_with_gemini(content_parts[:10000])
        law_name = metadata.get("law_name") or "Tài liệu pháp luật"
        issue_date = metadata.get("issue_date")
        law_type = metadata.get("type") or "Luật"
        # Chuẩn hóa law_name về đúng dạng "[Loại văn bản] số: [Số hiệu]"
        law_name = build_clean_law_name(law_name, doc_type_hint=law_type)
        
        print(f"🔹 Thông tin trích xuất: {law_name} | Ngày ban hành: {issue_date} | Loại: {law_type}")
        
        # 2. Phân đoạn văn bản nếu nó quá dài
        sections = split_text_by_articles(content_parts)
        print(f"📄 Văn bản được chia thành {len(sections)} phần để xử lý tránh quá tải giới hạn output token...")
        
        all_chunks = []
        for idx, section in enumerate(sections):
            print(f"⏳ Đang xử lý phần {idx+1}/{len(sections)}...")
            
            section_prompt = f"""
            Bạn là một chuyên gia Pháp luật cấp cao. Hãy đọc đoạn văn bản đính kèm thuộc văn bản pháp luật "{law_name}" và bóc tách nội dung thành các đoạn (chunks) dựa trên cấu trúc: Điều > Khoản > Điểm.
            
            THÔNG TIN VĂN BẢN:
            - Tên văn bản: {law_name}
            - Ngày ban hành: {issue_date or "Không rõ"}
            - Loại văn bản: {law_type}
            
            NHIỆM VỤ CỦA BẠN:
            1. Chia nhỏ đoạn văn bản này thành các đoạn (chunks) tương ứng với từng Điều/Khoản/Điểm cụ thể.
            2. Mỗi chunk tương ứng với một đơn vị nội dung hoàn chỉnh (thường là một Khoản hoặc một Điều nếu điều đó ngắn).
            3. Tiêu đề (title) của mỗi chunk phải ghi rõ dạng: "{law_name} - [Điều X] - [Khoản Y]" (nếu là cả Điều thì ghi "{law_name} - [Điều X]").
            4. Nội dung (content) phải giữ nguyên văn bản gốc tiếng Việt, không tóm tắt, không sửa từ ngữ, bao gồm cả bối cảnh của Điều đó nếu đoạn đó là một Khoản để người đọc hiểu được nội dung của Khoản đó nói về cái gì.
            5. Cung cấp metadata chính xác cho mỗi chunk:
               - "law_name": "{law_name}"
               - "article": số thứ tự của Điều (ví dụ: "4")
               - "section": số thứ tự của Khoản (ví dụ: "1"), nếu không có Khoản thì để null.
               - "type": "{law_type}"
            {AMENDMENTS_TO_INSTRUCTION}
            YÊU CẦU ĐỊNH DẠNG JSON:
            Trả về duy nhất một mảng JSON có cấu trúc như sau:
            [
              {{
                "title": "{law_name} - Điều X - Khoản Y",
                "content": "Nội dung đầy đủ của khoản Y...",
                "issue_date": {json.dumps(issue_date)},
                "metadata": {{
                    "law_name": "{law_name}",
                    "article": "X",
                    "section": "Y",
                    "type": "{law_type}",
                    "amendments_to": [],
                    "supersedes": [],
                    "provision_type": "P1"
                }}
              }}
            ]
            LƯU Ý: Tuyệt đối không thêm bất kỳ văn bản giải thích nào ngoài JSON. Chỉ trả về mảng JSON.
            """
            
            chunks_part = []
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[section, section_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    text_resp = response.text.strip()
                    text_resp = re.sub(r'```json\n|```json|```', '', text_resp).strip()
                    chunks_part = json.loads(text_resp)
                    break
                except Exception as e:
                    if "503" in str(e) or "overloaded" in str(e).lower():
                        wait_time = (attempt + 1) * 5
                        print(f"  [!] Server quá tải (503). Đang thử lại sau {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ Lỗi AI ở phần {idx+1}: {e}")
                        break
            
            if chunks_part:
                # Post-process to ensure clean metadata and title
                for item in chunks_part:
                    meta = item.get("metadata", {})
                    l_name = meta.get("law_name")
                    if l_name:
                        cleaned_l = build_clean_law_name(l_name, doc_type_hint=meta.get("type"))
                        meta["law_name"] = cleaned_l
                        # Update title of chunk
                        t = item.get("title")
                        if t:
                            parts = t.split(' - ')
                            if parts:
                                item["title"] = ' - '.join([cleaned_l] + parts[1:])
                    normalize_amendment_metadata(meta)
                    item["metadata"] = meta
                all_chunks.extend(chunks_part)
                print(f"  > Bóc tách thành công {len(chunks_part)} đoạn từ phần {idx+1}.")
            else:
                print(f"  > ⚠️ Cảnh báo: Không bóc tách được dữ liệu từ phần {idx+1}.")
                
        print(f"✅ Hoàn thành bóc tách! Tổng số đoạn luật: {len(all_chunks)}")
        return all_chunks

    else:
        # Fallback cho các file upload (PDF/DOCX) sử dụng File API của Google Cloud AI
        prompt = f"""
        Bạn là một chuyên gia Pháp luật cấp cao. Hãy đọc tài liệu đính kèm và bóc tách nội dung theo cấu trúc pháp luật Việt Nam.

        NHIỆM VỤ CỦA BẠN:
        1. Trích xuất chính xác ngày ban hành (issue_date) của văn bản.
        2. Chia nhỏ văn bản thành các đoạn (chunks) dựa trên cấu trúc: Điều > Khoản > Điểm.
        3. Mỗi chunk tương ứng với một đơn vị nội dung hoàn chỉnh (thường là một Khoản hoặc một Điều nếu điều đó ngắn).
        4. Tiêu đề (title) của mỗi chunk phải ghi rõ: [Tên văn bản] - [Điều X] - [Khoản Y].
        5. Nội dung (content) phải giữ nguyên văn, không tóm tắt, bao gồm cả bối cảnh của Điều đó nếu đoạn đó là một Khoản.
        {AMENDMENTS_TO_INSTRUCTION}
        YÊU CẦU ĐỊNH DẠNG JSON:
        Trả về duy nhất một mảng JSON:
        [
          {{
            "title": "Thông tư số: 18/2026/TT-BTC - Điều 4 - Khoản 1",
            "content": "Nội dung đầy đủ của khoản 1 điều 4...",
            "issue_date": "YYYY-MM-DD",
            "metadata": {{
                "law_name": "Thông tư số: 18/2026/TT-BTC",
                "article": "4",
                "section": "1",
                "type": "Thông tư",
                "amendments_to": [],
                "supersedes": [],
                "provision_type": "P1"
            }}
          }}
        ]
        LƯU Ý: Tuyệt đối không thêm văn bản ngoài JSON. Nếu không rõ ngày ban hành, để null cho issue_date.
        """
        for attempt in range(3):
            try:
                contents = content_parts if isinstance(content_parts, list) else [content_parts]
                contents.append(prompt)
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                
                # Làm sạch JSON
                text_resp = response.text.strip()
                text_resp = re.sub(r'```json\n|```json|```', '', text_resp).strip()
                    
                chunks = json.loads(text_resp)
                # Post-process to ensure clean metadata and title
                for item in chunks:
                    meta = item.get("metadata", {})
                    l_name = meta.get("law_name")
                    if l_name:
                        cleaned_l = build_clean_law_name(l_name, doc_type_hint=meta.get("type"))
                        meta["law_name"] = cleaned_l
                        t = item.get("title")
                        if t:
                            parts = t.split(' - ')
                            if parts:
                                item["title"] = ' - '.join([cleaned_l] + parts[1:])
                    normalize_amendment_metadata(meta)
                    item["metadata"] = meta
                print(f"✅ Thành công! Đã bóc tách {len(chunks)} đoạn luật.")
                return chunks
            except Exception as e:
                if "503" in str(e) or "overloaded" in str(e).lower():
                    wait_time = (attempt + 1) * 5
                    print(f"  [!] Server quá tải (503). Đang thử lại sau {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Lỗi AI: {e}")
                    break
        return []

# ==========================================
# 3. TIẾP NHẬN ĐẦU VÀO (FILE / URL)
# ==========================================
def clean_html(raw_html):
    # Loại bỏ thẻ HTML thô sơ để đưa vào Gemini (Gemini vẫn đọc tốt HTML, nhưng loại bỏ bớt sẽ nhanh hơn)
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, ' ', raw_html)
    return ' '.join(cleantext.split())

# Các loại văn bản pháp luật thường gặp, xếp cụm dài trước để khớp đúng
# ("Thông tư liên tịch" phải khớp trước "Thông tư", "Bộ luật" trước "Luật"...).
DOC_TYPE_KEYWORDS = [
    "Bộ luật", "Luật", "Pháp lệnh",
    "Nghị quyết liên tịch", "Nghị quyết",
    "Nghị định", "Quyết định", "Chỉ thị",
    "Thông tư liên tịch", "Thông tư", "Công văn",
]

# "Luật"/"Bộ luật" theo quy ước luôn được gọi bằng TÊN ĐẦY ĐỦ (VD "Luật Bảo hiểm
# xã hội số 41/2024/QH15", "Bộ luật Lao động số ...") - khác với các loại văn bản
# dưới luật (Nghị định, Thông tư, Quyết định...) chỉ cần "[Loại văn bản] số:
# [Số hiệu]" là đủ để tra cứu, không cần tên mô tả.
LAW_TYPES_KEEP_FULL_NAME = {"Luật", "Bộ luật"}

def extract_doc_header_hint(text):
    """
    Dò "Loại văn bản" (Luật/Nghị định/Thông tư...) + "Số hiệu" (vd: 12/2025/TT-BNV)
    và ngày ban hành bằng regex từ phần đầu văn bản gốc (thường lấy từ
    div#divContentDoc trên thuvienphapluat.vn). Cách này cho "law_name" chính
    xác tuyệt đối theo đúng quy chuẩn, đáng tin cậy hơn để AI tự đoán tên văn
    bản từ một đoạn nội dung dài và nhiều nhiễu.
    """
    header = text[:3000]

    so_hieu_match = re.search(r'Số:?\s*(\d+[\w\-./]*/\d{4}/[\w\-]+)', header)
    so_hieu = so_hieu_match.group(1).strip() if so_hieu_match else None

    # Chọn từ khóa khớp SỚM NHẤT trong văn bản (không theo thứ tự ưu tiên trong
    # danh sách), vì loại văn bản thật luôn nằm ở dòng tiêu đề đầu tiên - trước
    # khi tên loại văn bản khác có thể lặp lại trong tên luật được dẫn chiếu
    # (vd: "THÔNG TƯ ... quy định chi tiết Luật Bảo hiểm xã hội...").
    doc_type = None
    doc_type_pos = None
    for kw in DOC_TYPE_KEYWORDS:
        m = re.search(r'\b' + re.escape(kw) + r'\b', header, re.IGNORECASE)
        if m and (doc_type_pos is None or m.start() < doc_type_pos):
            doc_type = kw
            doc_type_pos = m.start()

    issue_date = None
    date_match = re.search(r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})', header, re.IGNORECASE)
    if date_match:
        d, m, y = date_match.groups()
        issue_date = f"{y}-{int(m):02d}-{int(d):02d}"

    if doc_type and so_hieu and doc_type not in LAW_TYPES_KEEP_FULL_NAME:
        law_name = f"{doc_type} số: {so_hieu}"
    else:
        law_name = None

    return {"law_name": law_name, "type": doc_type, "issue_date": issue_date}

def build_clean_law_name(raw_name, doc_type_hint=None):
    """
    Chuẩn hóa "law_name":
    - Với "Luật"/"Bộ luật" (LAW_TYPES_KEEP_FULL_NAME): GIỮ NGUYÊN tên đầy đủ, bao
      gồm cả tên mô tả ở giữa (VD "Luật Bảo hiểm xã hội số 41/2024/QH15"), đúng
      quy ước người dùng thực tế gọi tên luật - chỉ cắt phần THỪA nằm SAU số hiệu.
    - Với các loại văn bản còn lại (Nghị định, Thông tư, Quyết định...): rút gọn
      về đúng "[Loại văn bản] số: [Số hiệu]", bỏ phần tên mô tả mà AI (hoặc
      nguồn) hay chèn ở giữa, vì không cần tên mô tả để tra cứu các loại này.
    Áp dụng thống nhất cho MỌI nguồn nạp dữ liệu (URL, file PDF/DOCX/TXT, thư mục).
    """
    if not raw_name:
        return raw_name

    so_hieu_match = re.search(r'(\d+[\w\-./]*/\d{4}/[\w\-]+)', raw_name)
    if not so_hieu_match:
        return raw_name
    so_hieu = so_hieu_match.group(1)

    doc_type = None
    doc_type_pos = None
    for kw in DOC_TYPE_KEYWORDS:
        m = re.search(r'\b' + re.escape(kw) + r'\b', raw_name, re.IGNORECASE)
        if m and (doc_type_pos is None or m.start() < doc_type_pos):
            doc_type = kw
            doc_type_pos = m.start()
    doc_type = doc_type or doc_type_hint

    if not doc_type or doc_type in LAW_TYPES_KEEP_FULL_NAME:
        return raw_name[:so_hieu_match.end()].strip()

    return f"{doc_type} số: {so_hieu}"

def extract_law_text_from_html(html):
    """
    Từ HTML (dù tải trực tiếp qua URL hay đọc từ file .html đã lưu sẵn), lấy
    đúng nội dung văn bản gốc trong div#divContentDoc (thuvienphapluat.vn),
    bỏ qua menu/quảng cáo/văn bản liên quan; nếu không có div đó thì lấy
    toàn bộ text của trang. Trả về (text, metadata_hint) - dùng chung cho cả
    process_url() và nhánh đọc file .html/.htm trong process_file().
    """
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find(id="divContentDoc")
    if content_div:
        print("  > Phát hiện div#divContentDoc (thuvienphapluat.vn) - chỉ lấy đúng nội dung văn bản gốc, bỏ qua menu/quảng cáo.")
        raw_text = content_div.get_text(separator='\n')
    else:
        raw_text = soup.get_text(separator='\n')

    lines = (' '.join(line.split()) for line in raw_text.splitlines())
    text = '\n'.join(line for line in lines if line)

    hint = extract_doc_header_hint(text)
    if hint["law_name"]:
        date_info = f" (ban hành {hint['issue_date']})" if hint["issue_date"] else ""
        print(f"  > Nhận diện văn bản: {hint['law_name']}{date_info}")

    return text, hint

def process_url(url):
    print(f"🌐 Đang tải dữ liệu từ URL: {url}")
    try:
        # Fake User-Agent để tránh bị block bởi một số trang web
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or res.encoding
        return extract_law_text_from_html(res.text)
    except requests.exceptions.HTTPError as e:
        if res is not None and res.status_code == 403:
            print(
                f"Lỗi tải URL: {e}\n"
                "  > Trang này đang chặn truy cập tự động (Cloudflare/anti-bot), không thể tải trực tiếp.\n"
                "  > Cách khắc phục: mở link bằng trình duyệt, bấm Ctrl+S để lưu lại thành file .html, "
                "rồi nạp file đó qua lựa chọn '2. File văn bản luật' (đã hỗ trợ .html/.htm)."
            )
        else:
            print(f"Lỗi tải URL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Lỗi tải URL: {e}")
        sys.exit(1)

def process_file(file_path):
    """Trả về (content_parts, metadata_hint). metadata_hint chỉ khác None với file .html/.htm."""
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy tệp tin [{file_path}]")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()
    supported_extensions = ['.pdf', '.docx', '.doc', '.txt', '.html', '.htm']

    if ext not in supported_extensions:
        print(f"Lỗi: Định dạng file '{ext}' không được hỗ trợ. Chỉ nhận: {', '.join(supported_extensions)}")
        sys.exit(1)

    if ext in ('.html', '.htm'):
        # Dùng cho các trang bị chặn tải tự động (Cloudflare/anti-bot, xem process_url):
        # người dùng mở link bằng trình duyệt, lưu lại (Ctrl+S) rồi nạp file này.
        print(f"🌐 Đang đọc tệp HTML đã lưu [{file_path}]...")
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()
        except Exception as e:
            print(f"Lỗi đọc tệp HTML: {e}")
            sys.exit(1)
        return extract_law_text_from_html(html)

    if ext == '.txt':
        print(f"📝 Đang đọc tệp văn bản [{file_path}]...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read(), None
        except Exception as e:
            print(f"Lỗi đọc tệp văn bản: {e}")
            sys.exit(1)

    print(f"📄 Đang tải tệp tin [{file_path}] lên Google Cloud AI...")
    try:
        uploaded_file = client.files.upload(file=file_path)
        print("Đã tải lên hệ thống Gemini. Sẵn sàng xử lý!")
        return [uploaded_file], None
    except Exception as e:
        print(f"Lỗi đọc/tải tệp tin: {e}")
        sys.exit(1)

def ingest_content(content_parts, source_name, metadata_hint=None):
    # 1. AI bóc tách
    chunks = extract_and_chunk_with_gemini(content_parts, metadata_hint=metadata_hint)
    
    if not chunks:
        print(f"❌ Không có dữ liệu nào được bóc tách từ {source_name}. Bỏ qua.")
        return

    # 2. Nhúng Vector và Lưu DB
    print(f"\n🗄️ Đang lưu từng đoạn từ {source_name} vào cơ sở dữ liệu Supabase...")
    for idx, item in enumerate(chunks):
        print(f"  > Đang nhúng Vector ({idx+1}/{len(chunks)})...")
        vector = embed_text(item["content"], item.get("title"))
        if vector:
            row = {
                "title": item.get("title", f"Tài liệu {source_name}"),
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "issue_date": item.get("issue_date", None),
                "embedding": vector
            }
            insert_to_supabase(row)

    # 3. Ghi ngược quan hệ sửa đổi (amended_by) vào các văn bản cũ liên quan,
    # dựa trên "amendments_to" mà các chunk vừa insert ở trên khai báo.
    print(f"\n🔗 Đang đối chiếu quan hệ sửa đổi văn bản...")
    backfill_amended_by(chunks)

def process_directory(dir_path):
    if not os.path.exists(dir_path):
        print(f"Lỗi: Thư mục không tồn tại [{dir_path}]")
        return
        
    if not os.path.isdir(dir_path):
        print(f"Lỗi: [{dir_path}] không phải là một thư mục.")
        return
        
    print(f"📂 Đang quét thư mục [{dir_path}]...")
    supported_extensions = ['.pdf', '.docx', '.doc', '.txt', '.html', '.htm']
    files_to_ingest = []

    for root, dirs, files in os.walk(dir_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                files_to_ingest.append(os.path.join(root, f))

    if not files_to_ingest:
        print("Không tìm thấy file nào có định dạng được hỗ trợ (.pdf, .docx, .doc, .txt, .html, .htm) trong thư mục.")
        return

    print(f"Tìm thấy {len(files_to_ingest)} file phù hợp. Bắt đầu nạp dữ liệu...")
    for idx, file_path in enumerate(files_to_ingest):
        print(f"\n[{idx+1}/{len(files_to_ingest)}] Đang xử lý file: {os.path.basename(file_path)}")
        content_parts, metadata_hint = process_file(file_path)
        ingest_content(content_parts, os.path.basename(file_path), metadata_hint=metadata_hint)

def main():
    print("="*60)
    print("🚀 LEGAL AI - HỆ THỐNG NẠP CƠ SỞ TRI THỨC (AUTO-RAG)")
    print("="*60)
    
    parser = argparse.ArgumentParser(description="Công cụ nhúng dữ liệu vào Supabase bằng AI")
    parser.add_argument('--url', type=str, help='Link bài viết website')
    parser.add_argument('--pdf', type=str, help='Đường dẫn file PDF (Đã cũ, khuyên dùng --file)')
    parser.add_argument('--file', type=str, help='Đường dẫn file hoặc thư mục tài liệu (.pdf, .docx, .doc, .txt, .html, .htm)')
    parser.add_argument('--text', type=str, help='Câu text trực tiếp')
    parser.add_argument('--fix-amended-by', action='store_true',
                         help='Quét lại toàn bộ DB để bù amended_by cho các văn bản ingest sai thứ tự (không ingest gì mới)')
    args = parser.parse_args()

    if not GEMINI_API_KEY or not SUPABASE_URL:
        print("Lỗi: Thiếu cấu hình GEMINI_API_KEY hoặc SUPABASE_URL trong .env")
        return

    if args.fix_amended_by:
        backfill_all_amended_by()
        print("\n🎉 HOÀN TẤT ĐỐI CHIẾU LẠI QUAN HỆ SỬA ĐỔI (amended_by)!")
        return

    # Nếu chạy không đối số thì kích hoạt giao diện tương tác
    if not (args.url or args.file or args.pdf or args.text):
        print("Vui lòng chọn nguồn dữ liệu nạp tri thức:")
        print("1. Đường dẫn website")
        print("2. File văn bản luật (.pdf, .docx, .doc, .txt, .html, .htm)")
        print("3. Thư mục chứa văn bản luật")
        print("4. Quét lại toàn bộ DB để bù amended_by (sửa dữ liệu ingest sai thứ tự)")

        try:
            choice = input("Nhập lựa chọn của bạn (1-4): ").strip()
            
            if choice == '1':
                url = input("Vui lòng nhập đường dẫn tới website: ").strip()
                url = url.strip('\'"')
                if not url:
                    print("Lỗi: Đường dẫn không được để trống.")
                    return
                content_parts, metadata_hint = process_url(url)
                ingest_content(content_parts, url, metadata_hint=metadata_hint)
                
            elif choice == '2':
                file_path = input("Vui lòng nhập đường dẫn file: ").strip()
                file_path = file_path.strip('\'"')  # Hỗ trợ kéo thả tệp tin trên Windows
                if not file_path:
                    print("Lỗi: Đường dẫn file không được để trống.")
                    return
                content_parts, metadata_hint = process_file(file_path)
                ingest_content(content_parts, os.path.basename(file_path), metadata_hint=metadata_hint)

            elif choice == '3':
                dir_path = input("Vui lòng nhập đường dẫn thư mục: ").strip()
                dir_path = dir_path.strip('\'"')  # Hỗ trợ kéo thả thư mục trên Windows
                if not dir_path:
                    print("Lỗi: Đường dẫn thư mục không được để trống.")
                    return
                process_directory(dir_path)

            elif choice == '4':
                backfill_all_amended_by()
                print("\n🎉 HOÀN TẤT ĐỐI CHIẾU LẠI QUAN HỆ SỬA ĐỔI (amended_by)!")
                return

            else:
                print("Lỗi: Lựa chọn không hợp lệ.")
                return

        except KeyboardInterrupt:
            print("\nĐã hủy quá trình bởi người dùng.")
            return

        print("\n🎉 HOÀN TẤT NẠP TÀI LIỆU VÀO CƠ SỞ TRI THỨC!")
        return

    # Nếu chạy qua Command Line đối số
    if args.url:
        content_parts, metadata_hint = process_url(args.url)
        ingest_content(content_parts, args.url, metadata_hint=metadata_hint)
    elif args.text:
        ingest_content(args.text, "Văn bản trực tiếp")
    elif args.file or args.pdf:
        path_to_process = args.file or args.pdf
        if not os.path.exists(path_to_process):
            print(f"Lỗi: Đường dẫn không tồn tại [{path_to_process}]")
            return
            
        if os.path.isdir(path_to_process):
            process_directory(path_to_process)
        else:
            content_parts, metadata_hint = process_file(path_to_process)
            ingest_content(content_parts, os.path.basename(path_to_process), metadata_hint=metadata_hint)

    print("\n🎉 HOÀN TẤT NẠP TÀI LIỆU VÀO CƠ SỞ TRI THỨC!")

if __name__ == "__main__":
    main()
