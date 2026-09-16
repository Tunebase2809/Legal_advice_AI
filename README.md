# 🚀 BHXH_AI

**Trợ lý AI tin cậy tư vấn Luật Bảo hiểm xã hội Việt Nam**

BHXH_AI là hệ thống tư vấn pháp lý và hỗ trợ tra cứu chế độ Bảo hiểm xã hội dành cho người lao động và doanh nghiệp tại Việt Nam. Dự án sử dụng sức mạnh của LLM (Gemini) kết hợp với cơ chế RAG (Retrieval-Augmented Generation) dựa trên cơ sở dữ liệu văn bản pháp luật chuẩn xác (**Luật Bảo hiểm xã hội số 41/2024/QH15**) nhằm đảm bảo tính chính xác về mặt pháp lý và bảo mật dữ liệu.

## ✨ Tính năng cốt lõi

- 📚 **Tra cứu Luật Bảo hiểm xã hội Chính xác:** Tích hợp RAG với cơ sở dữ liệu pháp luật được trích xuất từ **Luật Bảo hiểm xã hội số 41/2024/QH15**.
- 🛡️ **Bảo mật & Kiểm soát Đa lớp (GuardService):** Tự động phát hiện và chặn các cuộc tấn công Prompt Injection, Jailbreak, lọc các câu hỏi không liên quan và kiểm tra chống rò rỉ dữ liệu hệ thống.
- 🔒 **Mã hóa Dữ liệu Nhạy cảm:** Tất cả tệp tin tài liệu/sổ BHXH/tờ khai do người dùng tải lên được mã hóa đối xứng bằng Fernet (AES-128) trước khi lưu đĩa, bảo mật theo không gian lưu trữ riêng (namespace) cho từng người dùng.
- 🖼️ **Xử lý Đa phương thức (Multimodal):** Hỗ trợ phân tích nội dung từ hình ảnh, tài liệu PDF, Excel, CSV và tệp văn bản đính kèm qua mô hình Gemini.
- 💬 **Quản lý Lịch sử Trò chuyện:** Lưu trữ session và danh sách tin nhắn, tài liệu đính kèm đồng bộ với Supabase DB.

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

| Thành phần | Công nghệ |
| :--- | :--- |
| **Frontend** | Next.js 14.2 (TypeScript), Vanilla CSS |
| **Backend** | Flask 3.1 (Python 3.x) |
| **LLM Engine** | Gemini API (`google-genai`) |
| **Vector DB / Storage** | Supabase (PostgreSQL + pgvector) |
| **Security & Encryption** | GuardService (Regex & AI Filter), Fernet AES-128 (`cryptography`) |

### 📦 Thư viện chính

#### Backend (Python):
- `flask` (`3.1.3`), `flask-cors` (`6.0.2`): API Framework & CORS setup.
- `google-genai` (`1.75.0`): SDK tương tác với mô hình Gemini.
- `cryptography`: Dịch vụ mã hóa tệp tin Fernet.
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
│   ├── database/       # Tương tác với Supabase Vector DB & Chat sessions
│   ├── services/       # GeminiService, GuardService, SupabaseService, EncryptionService
│   ├── uploads/        # Thư mục lưu trữ tệp tin đã mã hóa (phân loại theo user namespace)
│   ├── app.py          # Entry point của Flask server
│   └── ingest_rag.py   # Script trích xuất và nạp dữ liệu RAG vào Supabase
├── frontend/           # Giao diện ứng dụng Next.js
├── documents/          # Văn bản pháp luật nguồn (Vd: Luật BHXH 41/2024/QH15, các nghị định/thông tư liên quan...)
└── docs/               # Đặc tả kỹ thuật (phân loại từ khóa & bộ lọc RAG)
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
# SUPABASE_KEY=...
# ENCRYPTION_KEY=...

# Chạy server API (Cổng mặc định: 5000)
python app.py
```

### 3. Triển khai Frontend (Next.js)
```bash
cd frontend

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


