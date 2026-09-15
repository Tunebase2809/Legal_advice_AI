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
    """Lưu Vector vào bảng tax_documents"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/tax_documents", headers=headers, json=data)
    if response.status_code in [200, 201]:
        print(f"  [+] Đã lưu: {data['title']} - {data['content'][:40]}...")
    else:
        print(f"  [-] Lỗi lưu DB ({response.status_code}): {response.text}")

# ==========================================
# 2. AI TRÍCH XUẤT VÀ CHIA ĐOẠN (STRUCTURAL CHUNKING)
# ==========================================
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
                model="gemini-3.1-flash-lite",
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

def extract_and_chunk_with_gemini(content_parts):
    print("\n⏳ Đang nhờ AI Gemini bóc tách tài liệu theo cấu trúc pháp luật (Điều > Khoản > Điểm)...")
    model_name = "gemini-3.1-flash-lite" 
    
    if isinstance(content_parts, str):
        # 1. Trích xuất metadata trước từ phần đầu tiên của văn bản
        metadata = extract_metadata_with_gemini(content_parts[:10000])
        law_name = metadata.get("law_name") or "Tài liệu pháp luật"
        # Rút gọn law_name nếu quá dài dòng (chỉ giữ lại phần loại văn bản và số hiệu)
        import re
        match_l = re.search(r'\d+/\d{4}/[\w-]+', law_name)
        if match_l:
            law_name = law_name[:match_l.end()].strip()
        issue_date = metadata.get("issue_date")
        law_type = metadata.get("type") or "Luật"
        
        print(f"🔹 Thông tin trích xuất: Luật: {law_name} | Ngày ban hành: {issue_date} | Loại: {law_type}")
        
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
                    "type": "{law_type}"
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
                        match_l = re.search(r'\d+/\d{4}/[\w-]+', l_name)
                        if match_l:
                            cleaned_l = l_name[:match_l.end()].strip()
                            meta["law_name"] = cleaned_l
                            # Update title of chunk
                            t = item.get("title")
                            if t:
                                parts = t.split(' - ')
                                if parts:
                                    item["title"] = ' - '.join([cleaned_l] + parts[1:])
                all_chunks.extend(chunks_part)
                print(f"  > Bóc tách thành công {len(chunks_part)} đoạn từ phần {idx+1}.")
            else:
                print(f"  > ⚠️ Cảnh báo: Không bóc tách được dữ liệu từ phần {idx+1}.")
                
        print(f"✅ Hoàn thành bóc tách! Tổng số đoạn luật: {len(all_chunks)}")
        return all_chunks

    else:
        # Fallback cho các file upload (PDF/DOCX) sử dụng File API của Google Cloud AI
        prompt = """
        Bạn là một chuyên gia Pháp luật cấp cao. Hãy đọc tài liệu đính kèm và bóc tách nội dung theo cấu trúc pháp luật Việt Nam.
        
        NHIỆM VỤ CỦA BẠN:
        1. Trích xuất chính xác ngày ban hành (issue_date) của văn bản.
        2. Chia nhỏ văn bản thành các đoạn (chunks) dựa trên cấu trúc: Điều > Khoản > Điểm.
        3. Mỗi chunk tương ứng với một đơn vị nội dung hoàn chỉnh (thường là một Khoản hoặc một Điều nếu điều đó ngắn).
        4. Tiêu đề (title) của mỗi chunk phải ghi rõ: [Tên văn bản] - [Điều X] - [Khoản Y].
        5. Nội dung (content) phải giữ nguyên văn, không tóm tắt, bao gồm cả bối cảnh của Điều đó nếu đoạn đó là một Khoản.
        
        YÊU CẦU ĐỊNH DẠNG JSON:
        Trả về duy nhất một mảng JSON:
        [
          {
            "title": "Thông tư số: 18/2026/TT-BTC - Điều 4 - Khoản 1",
            "content": "Nội dung đầy đủ của khoản 1 điều 4...",
            "issue_date": "YYYY-MM-DD",
            "metadata": {
                "law_name": "Thông tư số: 18/2026/TT-BTC",
                "article": "4",
                "section": "1",
                "type": "Thông tư"
            }
          }
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
                        match_l = re.search(r'\d+/\d{4}/[\w-]+', l_name)
                        if match_l:
                            cleaned_l = l_name[:match_l.end()].strip()
                            meta["law_name"] = cleaned_l
                            t = item.get("title")
                            if t:
                                parts = t.split(' - ')
                                if parts:
                                    item["title"] = ' - '.join([cleaned_l] + parts[1:])
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

def process_url(url):
    print(f"🌐 Đang tải dữ liệu từ URL: {url}")
    try:
        # Fake User-Agent để tránh bị block bởi một số trang web
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        text = clean_html(res.text)
        return text[:50000] # Giới hạn độ dài để xử lý tối ưu
    except Exception as e:
        print(f"Lỗi tải URL: {e}")
        sys.exit(1)

def process_file(file_path):
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy tệp tin [{file_path}]")
        sys.exit(1)
        
    ext = os.path.splitext(file_path)[1].lower()
    supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
    
    if ext not in supported_extensions:
        print(f"Lỗi: Định dạng file '{ext}' không được hỗ trợ. Chỉ nhận: {', '.join(supported_extensions)}")
        sys.exit(1)
        
    if ext == '.txt':
        print(f"📝 Đang đọc tệp văn bản [{file_path}]...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Lỗi đọc tệp văn bản: {e}")
            sys.exit(1)
            
    print(f"📄 Đang tải tệp tin [{file_path}] lên Google Cloud AI...")
    try:
        uploaded_file = client.files.upload(file=file_path)
        print("Đã tải lên hệ thống Gemini. Sẵn sàng xử lý!")
        return [uploaded_file]
    except Exception as e:
        print(f"Lỗi đọc/tải tệp tin: {e}")
        sys.exit(1)

def ingest_content(content_parts, source_name):
    # 1. AI bóc tách
    chunks = extract_and_chunk_with_gemini(content_parts)
    
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

def process_directory(dir_path):
    if not os.path.exists(dir_path):
        print(f"Lỗi: Thư mục không tồn tại [{dir_path}]")
        return
        
    if not os.path.isdir(dir_path):
        print(f"Lỗi: [{dir_path}] không phải là một thư mục.")
        return
        
    print(f"📂 Đang quét thư mục [{dir_path}]...")
    supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
    files_to_ingest = []
    
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                files_to_ingest.append(os.path.join(root, f))
                
    if not files_to_ingest:
        print("Không tìm thấy file nào có định dạng được hỗ trợ (.pdf, .docx, .doc, .txt) trong thư mục.")
        return
        
    print(f"Tìm thấy {len(files_to_ingest)} file phù hợp. Bắt đầu nạp dữ liệu...")
    for idx, file_path in enumerate(files_to_ingest):
        print(f"\n[{idx+1}/{len(files_to_ingest)}] Đang xử lý file: {os.path.basename(file_path)}")
        content_parts = process_file(file_path)
        ingest_content(content_parts, os.path.basename(file_path))

def main():
    print("="*60)
    print("🚀 AI TAX - HỆ THỐNG NẠP CƠ SỞ TRI THỨC (AUTO-RAG)")
    print("="*60)
    
    parser = argparse.ArgumentParser(description="Công cụ nhúng dữ liệu vào Supabase bằng AI")
    parser.add_argument('--url', type=str, help='Link bài viết website')
    parser.add_argument('--pdf', type=str, help='Đường dẫn file PDF (Đã cũ, khuyên dùng --file)')
    parser.add_argument('--file', type=str, help='Đường dẫn file hoặc thư mục tài liệu (.pdf, .docx, .doc, .txt)')
    parser.add_argument('--text', type=str, help='Câu text trực tiếp')
    args = parser.parse_args()

    if not GEMINI_API_KEY or not SUPABASE_URL:
        print("Lỗi: Thiếu cấu hình GEMINI_API_KEY hoặc SUPABASE_URL trong .env")
        return

    # Nếu chạy không đối số thì kích hoạt giao diện tương tác
    if not (args.url or args.file or args.pdf or args.text):
        print("Vui lòng chọn nguồn dữ liệu nạp tri thức:")
        print("1. Đường dẫn website")
        print("2. File văn bản luật (pdf/doc/docx/txt)")
        print("3. Thư mục chứa văn bản luật")
        
        try:
            choice = input("Nhập lựa chọn của bạn (1-3): ").strip()
            
            if choice == '1':
                url = input("Vui lòng nhập đường dẫn tới website: ").strip()
                url = url.strip('\'"')
                if not url:
                    print("Lỗi: Đường dẫn không được để trống.")
                    return
                content_parts = process_url(url)
                ingest_content(content_parts, url)
                
            elif choice == '2':
                file_path = input("Vui lòng nhập đường dẫn file: ").strip()
                file_path = file_path.strip('\'"')  # Hỗ trợ kéo thả tệp tin trên Windows
                if not file_path:
                    print("Lỗi: Đường dẫn file không được để trống.")
                    return
                content_parts = process_file(file_path)
                ingest_content(content_parts, os.path.basename(file_path))
                
            elif choice == '3':
                dir_path = input("Vui lòng nhập đường dẫn thư mục: ").strip()
                dir_path = dir_path.strip('\'"')  # Hỗ trợ kéo thả thư mục trên Windows
                if not dir_path:
                    print("Lỗi: Đường dẫn thư mục không được để trống.")
                    return
                process_directory(dir_path)
                
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
        content_parts = process_url(args.url)
        ingest_content(content_parts, args.url)
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
            content_parts = process_file(path_to_process)
            ingest_content(content_parts, os.path.basename(path_to_process))

    print("\n🎉 HOÀN TẤT NẠP TÀI LIỆU VÀO CƠ SỞ TRI THỨC!")

if __name__ == "__main__":
    main()
