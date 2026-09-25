# 🚀 LEGAL_ADVICE_AI
**Trợ lý AI tin cậy tư vấn Luật Bảo hiểm xã hội Việt Nam**

**LEGAL_ADVICE_AI** là hệ thống tư vấn pháp lý và hỗ trợ tra cứu chế độ Bảo hiểm xã hội dành cho người lao động và doanh nghiệp tại Việt Nam. Dự án sử dụng sức mạnh của LLM (Gemini) kết hợp với cơ chế RAG (Retrieval-Augmented Generation) dựa trên cơ sở dữ liệu văn bản pháp luật chuẩn xác (**Luật Bảo hiểm xã hội số 41/2024/QH15**) nhằm đảm bảo tính chính xác về mặt pháp lý và bảo mật dữ liệu.

## ✨ Tính năng cốt lõi

- 📚 **Tra cứu Luật Bảo hiểm xã hội Chính xác:** Tích hợp RAG với cơ sở dữ liệu pháp luật được trích xuất từ **Luật Bảo hiểm xã hội số 41/2024/QH15** cùng các nghị định hướng dẫn liên quan (157, 158, 159, 176, 274/2025/NĐ-CP).
- 🧠 **Tầng định tuyến bằng từ khóa (GuardService):** `GuardService.needs_rag()` chỉ kích hoạt RAG khi câu hỏi khớp ít nhất 1 từ khóa cốt lõi (core keyword) đặc thù của miền BHXH — tránh gọi Gemini Embedding/Supabase cho các câu hỏi rõ ràng ngoài phạm vi.
- 🎯 **Hybrid re-rank theo dạng quy định:** Câu hỏi được phân loại theo 9 "dạng quy định" (P1–P9: định nghĩa, điều kiện hưởng, mức hưởng, thủ tục...) để ưu tiên đúng loại đoạn luật phù hợp, kết hợp với độ tương đồng vector thay vì chỉ dựa thuần similarity.
- 🔗 **Đối chiếu quan hệ sửa đổi văn bản (BFS đa tầng):** Khi ingest, hệ thống tự nhận diện văn bản nào sửa đổi Điều/Khoản nào của văn bản khác; lúc trả lời, `_fetch_amending_chunks()` duyệt theo tầng (Breadth-First Search) để tìm đúng phiên bản mới nhất, kể cả khi bị sửa đổi nhiều lớp.
- 🛡️ **Bảo mật & Kiểm soát Đa lớp (GuardService):** Tự động phát hiện và chặn các cuộc tấn công Prompt Injection, Jailbreak, lọc các câu hỏi không liên quan và kiểm tra chống rò rỉ dữ liệu hệ thống.
- 🔒 **Mã hóa Dữ liệu Nhạy cảm:** Tất cả tệp tin tài liệu/sổ BHXH/tờ khai do người dùng tải lên được mã hóa đối xứng bằng Fernet (AES-128) trước khi lưu đĩa, bảo mật theo không gian lưu trữ riêng (namespace) cho từng người dùng.
- 🖼️ **Xử lý Đa phương thức (Multimodal):** Hỗ trợ phân tích nội dung từ hình ảnh, tài liệu PDF và tệp văn bản đính kèm qua mô hình Gemini.
- 💬 **Quản lý Lịch sử Trò chuyện:** Lưu trữ session và danh sách tin nhắn, tài liệu đính kèm đồng bộ với Supabase DB.

> 📄 Đặc tả chi tiết bộ keyphrase, taxonomy khái niệm/dạng quy định và thiết kế pipeline tra cứu: [`docs/bhxh_keyphrase_spec.md`](docs/bhxh_keyphrase_spec.md).

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

| Thành phần | Công nghệ |
| :--- | :--- |
| **Frontend** | Next.js 14.2 (TypeScript), Vanilla CSS |
| **Backend** | Flask 3.1 (Python 3.x) |
| **LLM Engine** | Gemini API (`google-genai`) — sinh câu trả lời + Gemini Embedding (768 chiều) |
| **Vector DB / Storage** | Supabase (PostgreSQL + pgvector, chỉ mục HNSW) |
| **Security & Encryption** | GuardService (keyword routing + Regex filter), Fernet AES-128 (`cryptography`) |

### 📦 Thư viện chính

#### Backend (Python):
- `flask` (`3.1.3`), `flask-cors` (`6.0.2`): API Framework & CORS setup.
- `google-genai` (`1.75.0`): SDK tương tác với mô hình Gemini (sinh câu trả lời + nhúng vector).
- `cryptography`: Dịch vụ mã hóa tệp tin Fernet.
- `beautifulsoup4`: Bóc tách nội dung văn bản luật khi ingest trực tiếp từ HTML (`ingest_rag.py --url`).
- `python-dotenv`, `requests`, `werkzeug`.

#### Frontend (Node.js):
- `next` (`^14.2.24`), `react`, `react-dom` (`^18`): Framework React & UI Engine.
- `@supabase/supabase-js` (`^2.105.1`): Kết nối Supabase Database.
- `marked` (`^18.0.4`): Parse & render nội dung Markdown.
- `http-proxy` (`^1.18.1`): Reverse proxy chuyển tiếp API request sang Flask backend (cổng 5000).

---

## 🏗️ Cấu trúc dự án

```text
Legal_advice_AI/
├── backend/            # Flask API & Business Logic
│   ├── database/       # schema.sql: bảng legal_documents (pgvector), chat_sessions, chat_messages...
│   ├── services/       # GeminiService, GuardService, SupabaseService, EncryptionService
│   ├── uploads/        # Thư mục lưu trữ tệp tin đã mã hóa (phân loại theo user namespace)
│   ├── app.py          # Entry point của Flask server
│   └── ingest_rag.py   # Bóc tách + nhúng vector + nạp văn bản luật vào Supabase (hỗ trợ --file / --url)
├── frontend/           # Giao diện ứng dụng Next.js
├── documents/          # Văn bản pháp luật nguồn dạng file cục bộ (Vd: Luật BHXH 41/2024/QH15)
└── docs/               # Đặc tả keyphrase, taxonomy khái niệm/dạng quy định, thiết kế pipeline tra cứu
```

---

## 💻 Hướng dẫn cài đặt & Triển khai

### 1. Yêu cầu hệ thống
- **Node.js:** v18.x trở lên.
- **Python:** v3.10 trở lên.

### 2. Triển khai Backend (Flask API)
```bash
cd backend

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# Cấu hình biến môi trường trong file backend/.env:
# GEMINI_API_KEY=...
# SUPABASE_URL=...
# SUPABASE_ANON_KEY=...       # dùng cho API runtime (RLS theo user)
# SUPABASE_SERVICE_KEY=...    # dùng cho ingest_rag.py (ghi dữ liệu, bỏ qua RLS)
# ENCRYPTION_KEY=...          # base64 Fernet key; để trống + ALLOW_DEV_AUTO_ENCRYPTION_KEY=true để tự sinh khi chạy dev

# Chạy server API (Cổng mặc định: 5000)
python app.py
```

### 3. Nạp dữ liệu tri thức RAG
```bash
cd backend

# Từ file cục bộ trong documents/ (.txt/.pdf/.docx/.html)
python ingest_rag.py --file ../documents/41_2024_QH15.txt

# Hoặc trực tiếp từ URL văn bản luật (không cần lưu file cục bộ)
python ingest_rag.py --url https://...
```
Script tự bóc tách theo cấu trúc Điều/Khoản, gắn `provision_type` (P1–P9) và nhận diện quan hệ sửa đổi (`amendments_to`/`amended_by`) giữa các văn bản, rồi nhúng vector và lưu vào bảng `legal_documents` trên Supabase.

### 4. Triển khai Frontend (Next.js)
```bash
cd frontend

# Cấu hình biến môi trường trong file frontend/.env.local:
# NEXT_PUBLIC_SUPABASE_URL=...
# NEXT_PUBLIC_SUPABASE_ANON_KEY=...

# Cài đặt các gói phụ thuộc
npm install

# Khởi chạy môi trường phát triển
npm run dev
```

> ℹ️ **Lưu ý:** Hệ thống đã được thiết lập Reverse Proxy chuyển tiếp tất cả yêu cầu từ Frontend `/api/*` sang Backend `http://localhost:5000`.

---

## 👥 Đội ngũ thực hiện


- Nguyễn Thái Tú
- Đỗ Quốc Thắng
- Đỗ Quốc Học
- Dương Trần Quang Huy
- Lê Hoàng Lộc
- Lê Thị Tuấn Anh
- Đoàn Mậu Thiên Thư

