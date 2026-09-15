# 🚀 Tax_AI

**Trợ lý AI tin cậy dành riêng cho hộ kinh doanh cá thể Việt Nam**

Tax_AI là hệ thống hỗ trợ khai báo thuế và quản lý kế hoạch tài chính dành riêng cho hộ kinh doanh cá thể. Dự án kết hợp sức mạnh của LLM (Gemini 3.1 Flash Lite) và cơ chế RAG (Retrieval-Augmented Generation) để đảm bảo tính chính xác về pháp lý và bảo mật dữ liệu tuyệt đối.

> *"AI tốt không chỉ là AI chính xác — mà là AI mà con người có thể tin tưởng, hiểu được và kiểm soát được."*
> 
> — **Nhóm thực hiện đồ án**

---

## ✨ Tính năng cốt lõi

- 📚 **Tra cứu Luật Thuế Chính xác:** Sử dụng RAG với cơ sở dữ liệu từ Thông tư 40/2021/TT-BTC và mới nhất là Nghị định 141/2026/NĐ-CP (ngưỡng miễn thuế 1 tỷ VNĐ).
- 🧮 **Tính thuế Deterministic:** Thuế suất được lập trình cứng (hard-coded) để loại bỏ hoàn toàn hiện tượng "ảo giác" toán học của AI, đảm bảo chính xác 100% về con số.
- 🛡️ **Bảo mật Đa lớp (GuardService):** Tích hợp WAF riêng cho LLM để chặn 100% các cuộc tấn công Prompt Injection, Jailbreak và rò rỉ dữ liệu.
- 🔒 **Mã hóa Dữ liệu Nhạy cảm:** Toàn bộ hóa đơn tải lên được mã hóa đối xứng bằng Fernet AES-128. Dữ liệu chỉ được giải mã trong bộ nhớ RAM và xóa sạch sau khi xử lý.
- 🖼️ **Phân tích Đa phương thức:** Hỗ trợ đọc hiểu hóa đơn qua ảnh chụp, PDF, Excel và CSV nhờ khả năng multimodal của Gemini.

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

| Thành phần | Công nghệ |
| :--- | :--- |
| **Frontend** | Next.js 14.2 (TypeScript), Vanilla CSS |
| **Backend** | Flask 3.1 (Python 3.14) |
| **LLM Engine** | Gemini 3.1 Flash Lite |
| **Vector DB** | Supabase (PostgreSQL + pgvector) |
| **Embedding** | Gemini-Embedding-2 (768 dimensions) |

### 📦 Các thư viện Node.js (Node Modules)
Dự án sử dụng các module chính sau (tập trung tại `frontend`):
- **`next`** (`^14.2.24`): Framework React cốt lõi.
- **`react`**, **`react-dom`** (`^18`): Thư viện xây dựng giao diện UI.
- **`@supabase/supabase-js`** (`^2.105.1`): Giao tiếp với Supabase (Vector DB).
- **`marked`** (`^18.0.4`): Parse và render văn bản Markdown.
- **`http-proxy`** (`^1.18.1`): Thiết lập reverse proxy chuyển tiếp request từ frontend sang backend.
- Cùng với các devDependencies phục vụ phát triển: `typescript`, `eslint`, `eslint-config-next`, và các gói `@types/*`.

---

## 🏗️ Cấu trúc dự án

```text
AI_TAX/
├── backend/            # Flask API & Business Logic (GuardService, TaxCalculator)
|   └── uploads/        # Thư mục lưu trữ tệp người dùng tải lên khi sử dụng Chat (đã mã hóa)
├── frontend/           # Giao diện người dùng Next.js
└── documents/          # Thư viện văn bản pháp luật (PDF/Markdown) cho RAG
```

---

## 💻 Hướng dẫn cài đặt

### 1. Yêu cầu hệ thống
- **Node.js:** Phiên bản 24.x hoặc mới hơn.
- **Python:** Phiên bản 3.14 (Để đảm bảo tính ổn định của các thư viện mã hóa).

### 2. Triển khai Backend
```bash
cd backend
pip install -r requirements.txt

# Tạo file .env và cấu hình: GEMINI_API_KEY, SUPABASE_URL, ENCRYPTION_KEY
python app.py
```

### 3. Triển khai Frontend
```bash
cd frontend
npm install
npm run dev
```
> **Lưu ý:** Hệ thống đã cấu hình Reverse Proxy tự động chuyển hướng các yêu cầu `/api/*` sang cổng 5000.

---

## ⚖️ Cam kết AI có trách nhiệm (Responsible AI)

Hệ thống được thiết kế dựa trên 5 trụ cột đạo đức:

1. **Reliability:** Khả năng tự phục hồi với cơ chế Retry logic và tính toán tất định.
2. **Bias Control:** Thuật toán tính thuế trung lập, không phân biệt vùng miền, giới tính.
3. **Robustness:** Kháng lỗi mạnh mẽ với lớp bảo vệ GuardService.
4. **Explainability:** Mọi câu trả lời đều có trích dẫn Điều/Khoản/Điểm từ nguồn luật chính thống.
5. **Social Impact:** Khách quan về mặt pháp lý, tuân thủ quy định về bảo mật thông tin cá nhân.

---

## 👥 Đội ngũ thực hiện

- Nguyễn Thái Tú
- Đỗ Quốc Thắng
- Quách Văn Ngọc
- Dương Trần Quang Huy
