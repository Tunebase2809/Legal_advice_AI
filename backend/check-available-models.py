import os
import sys
from dotenv import load_dotenv
from google import genai

# Cấu hình encoding UTF-8 cho Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Tải biến môi trường từ file .env
load_dotenv()

# Lấy API key từ biến môi trường GEMINI_API_KEY trong .env hoặc hệ thống
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Cách 2: Nếu muốn dán trực tiếp API key (không khuyến khích hardcode)
# client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

print("=== DANH SÁCH CÁC MODEL TÀI KHOẢN CỦA BẠN CÓ THỂ DÙNG ===")
try:
    # Lấy danh sách tất cả các model khả dụng
    for model in client.models.list():
        # Chỉ lọc ra các model hỗ trợ tạo nội dung (generateContent)
        if "generateContent" in model.supported_actions:
            # model.name thường có dạng "models/gemini-..."
            model_id = model.name.replace("models/", "")
            print(f"• ID: {model_id:<30} | Tên: {model.display_name}")

except Exception as e:
    print(f"Lỗi khi kết nối API: {e}")