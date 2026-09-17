import os
import time
import io
import math
import uuid
import hashlib
import logging
import requests
from collections import defaultdict
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService
from services.guard_service import GuardService
from services.encryption_service import EncryptionService

# Tải các biến môi trường
load_dotenv()

logger = logging.getLogger("app")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [App] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)
app.json.sort_keys = False

# Chỉ tin các header X-Forwarded-* (dùng để lấy IP thật của client) khi app CHẮC CHẮN
# chạy sau một reverse proxy đáng tin cậy (Nginx/Cloudflare/Load Balancer...).
# Bật bằng biến môi trường TRUST_PROXY_HEADERS=true khi triển khai thật.
# Không tin các header này theo mặc định, vì client có thể tự set giá trị tùy ý để
# giả mạo IP nguồn và bypass hoàn toàn rate limit.
if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# Lưu trữ lịch sử giới hạn tần suất yêu cầu trong bộ nhớ (RAM): { ip: [mốc_thời_gian1, mốc_thời_gian2, ...] }
rate_limit_records = defaultdict(list)
_last_rate_limit_cleanup = time.time()
_RATE_LIMIT_CLEANUP_INTERVAL = 600  # 10 phút

def get_client_ip():
    # request.remote_addr đã được ProxyFix chuẩn hóa đúng nếu TRUST_PROXY_HEADERS=true;
    # nếu không, đây luôn là địa chỉ kết nối TCP thật, không thể giả mạo qua header.
    return request.remote_addr

def _cleanup_stale_rate_limit_keys(now):
    """Dọn định kỳ các key có danh sách timestamp rỗng để tránh rò rỉ bộ nhớ dần
    theo thời gian khi có nhiều IP/route khác nhau truy cập qua vòng đời server."""
    global _last_rate_limit_cleanup
    if now - _last_rate_limit_cleanup < _RATE_LIMIT_CLEANUP_INTERVAL:
        return
    stale_keys = [k for k, v in rate_limit_records.items() if not v]
    for k in stale_keys:
        del rate_limit_records[k]
    _last_rate_limit_cleanup = now

def limit_requests(max_requests=20, window_seconds=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = get_client_ip()
            # Sử dụng key kết hợp IP và tên hàm để giới hạn riêng biệt cho từng API
            rate_limit_key = f"{ip}:{f.__name__}"
            now = time.time()
            
            # Loại bỏ các mốc thời gian cũ nằm ngoài khoảng thời gian giới hạn (window)
            timestamps = rate_limit_records[rate_limit_key]
            timestamps = [t for t in timestamps if now - t < window_seconds]
            rate_limit_records[rate_limit_key] = timestamps
            
            if len(timestamps) >= max_requests:
                wait_time = math.ceil(window_seconds - (now - timestamps[0]))
                if wait_time <= 0:
                    wait_time = 1
                return jsonify({
                    "error": f"Too many requests. Vui lòng thử lại sau {wait_time} giây."
                }), 429
                
            rate_limit_records[rate_limit_key].append(now)
            _cleanup_stale_rate_limit_keys(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Khởi tạo các dịch vụ
gemini_service = GeminiService()
supabase_service = SupabaseService()
guard_service = GuardService()
encryption_service = EncryptionService()

# Đường dẫn thư mục uploads tuyệt đối
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# Đảm bảo thư mục uploads tồn tại
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==========================================
# TIỆN ÍCH LƯU TRỮ FILE AN TOÀN (chống Path Traversal + trộn file giữa các user)
# ==========================================

def sanitize_filename(filename: str) -> str:
    """
    Loại bỏ các thành phần có thể gây Path Traversal (đường dẫn thư mục cha '..',
    dấu phân cách '/', '\\', ký tự null) trong khi VẪN GIỮ NGUYÊN ký tự tiếng Việt
    có dấu trong tên file - khác với werkzeug.utils.secure_filename vốn sẽ xóa sạch
    toàn bộ ký tự Unicode và làm hỏng tên file tiếng Việt bình thường (VD
    "hóa đơn tháng 6.pdf" sẽ bị biến dạng nếu dùng secure_filename mặc định).
    """
    if not filename:
        return f"file_{uuid.uuid4().hex}"
    # Chỉ giữ lại phần tên file cuối cùng, bỏ mọi thành phần thư mục nếu có
    filename = os.path.basename(filename)
    filename = filename.replace("\x00", "").replace("\\", "_")
    while ".." in filename:
        filename = filename.replace("..", "")
    filename = filename.strip().strip(".")
    if not filename:
        return f"file_{uuid.uuid4().hex}"
    return filename

def get_user_namespace(user_token: str) -> str:
    """Sinh một thư mục con riêng biệt cho từng user dựa trên hash của token đăng
    nhập, để file của các user khác nhau không bao giờ trùng đường dẫn vật lý và
    ghi đè lẫn nhau (kể cả khi trùng tên file, VD 2 người cùng đặt tên
    "hoa_don.pdf")."""
    if not user_token:
        return "anonymous"
    return hashlib.sha256(user_token.encode("utf-8")).hexdigest()[:16]

def get_user_upload_dir(user_token: str) -> str:
    user_dir = os.path.join(UPLOAD_DIR, get_user_namespace(user_token))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def safe_upload_path(user_token: str, filename: str) -> str:
    """Trả về đường dẫn lưu trữ an toàn: đã sanitize tên file (chống traversal) và
    đặt trong thư mục riêng theo user (chống trộn/ghi đè file chéo user)."""
    return os.path.join(get_user_upload_dir(user_token), sanitize_filename(filename))

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "AI BHXH Assistant Backend is running!"})

@app.route('/api/chat', methods=['POST'])
@limit_requests(20, 60)
def chat():
    # Nhận dữ liệu dạng Form Data (Hỗ trợ File)
    user_message = request.form.get('message', '')

    user_token = request.form.get('supabase_token')
    session_id = request.form.get('session_id')

    file = request.files.get('file')

    if file:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # reset file pointer
        max_size = 2 * 1024 * 1024  # 2MB
        if file_size > max_size:
            return jsonify({"error": "Kích thước tệp tin không được vượt quá 2MB."}), 400
            
    if not user_message and not file:
        return jsonify({"error": "Message is required"}), 400
        
    # 1. Guard Service - Chống Prompt Injection
    is_safe, blocked_reason = guard_service.check_input(user_message)
    if not is_safe:
        return jsonify({
            "error": f"Tin nhắn bị từ chối: {blocked_reason}",
            "rag_bypassed_reason": "Từ chối trả lời"
        }), 403
        
    # Kiểm tra sự liên quan của câu hỏi trước khi chạy RAG
    # Bỏ qua từ chối nếu người dùng có tải lên file đi kèm
    is_relevant = True
    if user_message and not file:
        relevance = guard_service.check_relevance(user_message, gemini_service)
        if relevance == "GREETING":
            is_relevant = False

    # 2. Tạo Session nếu chưa có
    if user_token and not session_id:
        if user_message:
            import re
            clean_title = re.sub(r'[#\*_\`\-]', '', user_message).strip()
            title = clean_title[:40] + "..." if clean_title else "Tư vấn Bảo hiểm xã hội"
        else:
            title = "Tư vấn Bảo hiểm xã hội"
        session_id = supabase_service.create_session(title, user_token)
        
    # 3. Xử lý File Upload
    file_path = None
    file_name = None
    file_type = None
    if file:
        file_name = file.filename
        file_type = file_name.split('.')[-1].upper() if '.' in file_name else "FILE"
        # Lưu vào thư mục riêng theo user + tên file đã sanitize để chống Path
        # Traversal (trước đây dùng thẳng file.filename từ client, không kiểm tra
        # gì, có thể ghi đè file ngoài UPLOAD_DIR) và chống trộn/ghi đè file giữa
        # các user khác nhau khi trùng tên (trước đây lưu phẳng theo tên file).
        file_path = safe_upload_path(user_token, file_name)
        file.save(file_path)
        # Mã hóa tệp tin ngay lập tức trên đĩa
        encryption_service.encrypt_file(file_path)
        
        # Lưu thông tin tệp tin vào bảng user_files để quản lý độc lập với lịch sử chat
        if user_token:
            supabase_service.save_user_file(user_token, file_name, file_type)

    # 4. Lưu tin nhắn của User
    if user_token and session_id:
        supabase_service.save_message(session_id, 'user', user_message, user_token, file_name=file_name, file_type=file_type)
        
    # 5. RAG - Lấy ngữ cảnh luật BHXH
    legal_context = ""
    sources = []
    needs_rag_flag = False
    block_reason = None
    query_provision_labels = []
    if is_relevant:
        needs_rag_flag, block_reason = guard_service.needs_rag(user_message)
        if needs_rag_flag:
            # Chuyển đổi câu hỏi của user thành Vector
            query_vector = gemini_service.embed_text(user_message)
            # Đoán "dạng câu hỏi" (provision_type P1-P9) để hybrid re-rank kết quả
            # RAG - ưu tiên chunk vừa gần nghĩa vừa đúng nhóm khái niệm đang hỏi
            query_provision_types = guard_service.classify_provision_types(user_message)
            query_provision_labels = guard_service.describe_provision_types(query_provision_types)
            legal_context, sources = supabase_service.search_legal_documents(
                query_vector, query_provision_types=query_provision_types
            )

    # 6. xử lý các trường hợp không có nguồn tham chiếu, hoặc câu hỏi không liên quan
    empty_sources_reason = None
    if is_relevant and not file and not sources:
        if needs_rag_flag:
            # Đúng chủ đề BHXH (đã qua được needs_rag) nhưng tra Supabase không
            # ra kết quả nào phù hợp - khác với trường hợp bên dưới (không liên
            # quan đến BHXH ngay từ đầu), nên dùng thông điệp riêng cho chính xác.
            ai_response = (
                "Xin lỗi, tôi không tìm thấy căn cứ pháp lý phù hợp trong cơ sở dữ liệu "
                "để trả lời chính xác câu hỏi này. Vui lòng đặt câu hỏi cụ thể hơn hoặc "
                "liên hệ trực tiếp cơ quan Bảo hiểm xã hội để được hỗ trợ."
            )
            empty_sources_reason = "Không tìm thấy căn cứ pháp lý trong cơ sở dữ liệu"
            logger.info("BỊ CHẶN (no_legal_context): Câu hỏi cần tra cứu nhưng không có nguồn phù hợp trong DB.")
        else:
            ai_response = f"Xin lỗi, tôi không thể trả lời! Lý do: {block_reason}."
            empty_sources_reason = block_reason or "Không liên quan đến BHXH"
    else:
        # Gemini API - Tư vấn (Đưa file vào phân tích nếu có)
        ai_response = gemini_service.generate_response(
            user_message,
            context=legal_context,
            file_path=file_path
        )

        if ai_response is None:
            ai_response = "Xin lỗi, tôi không nhận được phản hồi từ mô hình AI."
        is_error = ai_response.startswith("Lỗi") or "lỗi kết nối" in ai_response
        is_refusal = "Xin lỗi, tôi không thể trả lời!" in ai_response
        if is_error or is_refusal:
            if is_refusal:
                if not needs_rag_flag and block_reason:
                    ai_response = f"Xin lỗi, tôi không thể trả lời! Lý do: {block_reason}."
                else:
                    ai_response = "Xin lỗi, tôi không thể trả lời! Lý do: Câu hỏi này nằm ngoài phạm vi tư vấn Luật Bảo hiểm xã hội mà tôi có thể hỗ trợ."
            sources = []
            empty_sources_reason = "Lỗi API" if is_error else "Từ chối trả lời"
        else:
            # 7. Guard Service - Kiểm tra phản hồi (Bảo mật & Phòng thủ)
            is_safe_resp, blocked_reason_resp = guard_service.check_response(ai_response)
            if not is_safe_resp:
                ai_response = f"Tin nhắn bị từ chối: {blocked_reason_resp}"
                sources = []
                empty_sources_reason = "Chặn phản hồi"
        
    # 8. Lưu tin nhắn của AI
    if user_token and session_id:
        supabase_service.save_message(session_id, 'assistant', ai_response, user_token, sources=sources)

    response = {
        "text": ai_response,
        "session_id": session_id,
        "sources": sources,
        "rag_bypassed_reason": empty_sources_reason,
        "user_message": user_message,
        "query_provision_labels": query_provision_labels
    }

    return jsonify(response)

@app.route('/api/document', methods=['GET'])
@limit_requests(30, 60)
def get_document():
    title = request.args.get('title')
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not title:
        return jsonify({"error": "Title is required"}), 400
        
    if not supabase_service.url or not supabase_service.key:
         return jsonify({"error": "Supabase not configured"}), 500
         
    # Parse title "Nghị định số: 141/2026/NĐ-CP (Điều 4, Khoản 1)" -> law_name
    import re
    match = re.match(r'^(.*?)(?:\s*\((.*?)\))?$', title)
    law_name = title
    db_title = title
    if match:
        law_name = match.group(1).strip()
        details = match.group(2)
        if details:
            # Chuyển "Điều 10, Khoản 1" thành "Điều 10 - Khoản 1"
            details_str = details.replace(', ', ' - ')
            db_title = f"{law_name} - {details_str}"
            
    headers = {"apikey": supabase_service.key, "Authorization": f"Bearer {supabase_service.key}"}
    
    try:
        # Cách 1: Thử tìm chính xác bằng cột title (cấu trúc gốc trong DB)
        params_exact = {
            "select": "content,metadata,title",
            "title": f"ilike.*{db_title}*",
            "limit": 1
        }
        resp_exact = requests.get(f"{supabase_service.url}/rest/v1/legal_documents", headers=headers, params=params_exact, timeout=5)
        if resp_exact.status_code == 200:
            results_exact = resp_exact.json()
            if results_exact and len(results_exact) > 0:
                return jsonify({"title": title, "content": results_exact[0].get('content', '')})
        
        # Cách 2: Tìm kiếm tương đối (Fallback)
        doc_info = supabase_service._parse_doc_id(law_name)
        search_term = doc_info['full'] if doc_info else law_name
        
        params = {
            "select": "content,metadata,title",
            "content": f"ilike.*{search_term}*",
            "limit": 50
        }
        
        resp = requests.get(f"{supabase_service.url}/rest/v1/legal_documents", headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            results = resp.json()
            # Filter results to exactly match the title if possible
            best_match = None
            for row in results:
                meta = row.get('metadata', {})
                # Try exact db_title match on row's title first
                if row.get('title') == db_title:
                    best_match = row
                    break
                    
                row_law_name = meta.get('law_name', row.get('title', ''))
                article = meta.get('article', 'N/A')
                section = meta.get('section', 'N/A')
                
                source_parts = []
                if article and article != 'N/A':
                    source_parts.append(f"Điều {article}")
                if section and section != 'N/A':
                    source_parts.append(f"Khoản {section}")
                
                source_label = row_law_name
                if source_parts:
                    source_label += f" ({', '.join(source_parts)})"
                    
                if source_label == title:
                    best_match = row
                    break
                    
            if not best_match and len(results) > 0:
                best_match = results[0] # Fallback to first matching doc
                
            if best_match:
                content = best_match.get('content', '')
                return jsonify({"title": title, "content": content})
                
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        
    return jsonify({"error": "Không tìm thấy nội dung văn bản này."}), 404

@app.route('/api/files', methods=['GET'])
@limit_requests(30, 60)
def list_files():
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_files = supabase_service.get_user_files(user_token)
    allowed_filenames = {f.get('file_name') for f in user_files if f.get('file_name')}
    
    # Chỉ quét trong thư mục riêng của user này, không quét UPLOAD_DIR chung -
    # tránh liệt kê nhầm file của user khác nếu có sự trùng tên/đường dẫn.
    upload_dir = get_user_upload_dir(user_token)
    if not os.path.exists(upload_dir):
        return jsonify([])
    
    files = []
    for filename in os.listdir(upload_dir):
        if filename not in allowed_filenames:
            continue
        file_path = os.path.join(upload_dir, filename)
        if os.path.isfile(file_path):
            stats = os.stat(file_path)
            files.append({
                "name": filename,
                "size": stats.st_size,
                "ctime": stats.st_ctime,
                "type": filename.split('.')[-1].upper() if '.' in filename else "FILE"
            })
    # Sắp xếp theo thời gian tạo mới nhất
    files.sort(key=lambda x: x['ctime'], reverse=True)
    return jsonify(files)

@app.route('/api/files/<filename>', methods=['GET'])
@limit_requests(30, 60)
def download_file(filename):
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_files = supabase_service.get_user_files(user_token)
    allowed_filenames = {f.get('file_name') for f in user_files if f.get('file_name')}
    
    if filename not in allowed_filenames:
        return jsonify({"error": "Forbidden: Bạn không có quyền truy cập tệp tin này"}), 403
        
    import mimetypes
    
    # Dùng safe_upload_path (sanitize + thư mục riêng theo user) thay vì ghép thẳng
    # UPLOAD_DIR + filename - trước đây dễ bị Path Traversal vì filename lấy thẳng
    # từ URL, đồng thời không phân biệt file theo user nên có thể vô tình đọc trúng
    # file cùng tên của user khác nếu bị ghi đè.
    file_path = safe_upload_path(user_token, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
        
    try:
        decrypted_bytes = encryption_service.decrypt_file(file_path)
        
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        return send_file(
            io.BytesIO(decrypted_bytes),
            mimetype=mime_type,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Lỗi giải mã file tải về: {e}")
        return jsonify({"error": "Không thể giải mã tệp tin"}), 500

@app.route('/api/sessions', methods=['GET'])
@limit_requests(30, 60)
def get_sessions():
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    sessions = supabase_service.get_sessions(user_token)
    return jsonify(sessions)

@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
@limit_requests(30, 60)
def get_messages(session_id):
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    messages = supabase_service.get_messages(session_id, user_token)
    return jsonify(messages)

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
@limit_requests(30, 60)
def delete_session(session_id):
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    success = supabase_service.delete_session(session_id, user_token)
    if success:
        return jsonify({"message": "Session deleted successfully"})
    else:
        return jsonify({"error": "Failed to delete session"}), 500

@app.route('/api/files/<filename>', methods=['DELETE'])
@limit_requests(30, 60)
def delete_file(filename):
    user_token = request.headers.get('Authorization')
    if not user_token:
        user_token = request.args.get('supabase_token')
    else:
        if user_token.startswith("Bearer "):
            user_token = user_token[7:]
            
    if not user_token:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_files = supabase_service.get_user_files(user_token)
    allowed_filenames = {f.get('file_name') for f in user_files if f.get('file_name')}
    
    if filename not in allowed_filenames:
        return jsonify({"error": "Forbidden: Bạn không có quyền xóa tệp tin này"}), 403
        
    file_path = safe_upload_path(user_token, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        supabase_service.delete_user_file(user_token, filename)
        return jsonify({"message": f"Deleted {filename}"})
    return jsonify({"error": "File not found"}), 404


if __name__ == '__main__':
    # QUAN TRỌNG: debug=True bật Werkzeug interactive debugger - nếu có exception
    # chưa được xử lý, bất kỳ ai truy cập trang lỗi đó đều có thể chạy code Python
    # tùy ý ngay trên server (RCE). Trước đây debug=True được hardcode, rất nguy
    # hiểm nếu triển khai production ở chế độ này. Giờ mặc định TẮT, chỉ bật khi
    # đặt biến môi trường FLASK_DEBUG=true (dùng cho dev local).
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug_mode, port=port)

