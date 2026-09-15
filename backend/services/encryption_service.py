import os
import stat
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("encryption_service")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [EncryptionService] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class EncryptionKeyMissingError(RuntimeError):
    """
    Raised khi ENCRYPTION_KEY chưa được cấu hình và chế độ tự sinh khóa (chỉ dành
    cho dev) không được bật tường minh. Ứng dụng PHẢI dừng khởi động trong trường
    hợp này - tuyệt đối không được âm thầm tự sinh khóa mới, vì trên môi trường
    container/ephemeral filesystem hoặc khi chạy nhiều instance, mỗi lần
    restart/instance có thể sinh ra khóa KHÁC NHAU, khiến toàn bộ dữ liệu đã mã
    hóa bằng khóa cũ (tin nhắn chat, giao dịch, cài đặt doanh nghiệp, file đính
    kèm...) VĨNH VIỄN không thể giải mã lại được.
    """
    pass


class EncryptionService:
    def __init__(self):
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)

    def _get_or_create_key(self) -> bytes:
        # 1. Ưu tiên tải từ biến môi trường (cách chuẩn cho production: set qua
        # secrets manager / biến môi trường của nền tảng triển khai).
        key_str = os.getenv("ENCRYPTION_KEY")
        if key_str:
            return key_str.encode()

        # 2. Nếu chưa có trong biến môi trường, thử đọc thủ công từ file .env
        # (trường hợp .env tồn tại trên đĩa nhưng chưa được load vào os.environ
        # ở thời điểm module này được import).
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith("ENCRYPTION_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        os.environ["ENCRYPTION_KEY"] = val
                        return val.encode()

        # 3. TUYỆT ĐỐI KHÔNG tự động sinh khóa mới ngầm định theo mặc định.
        # Trước đây code sẽ tự Fernet.generate_key() và ghi vào .env bất cứ khi
        # nào thiếu ENCRYPTION_KEY - đây là nguồn rủi ro mất dữ liệu nghiêm trọng
        # nhất trong toàn bộ hệ thống (xem docstring của EncryptionKeyMissingError).
        # Chỉ cho phép tự sinh khi dev CHỦ ĐỘNG bật cờ dưới đây, dành riêng cho máy
        # dev cá nhân - KHÔNG được bật ở staging/production.
        if os.getenv("ALLOW_DEV_AUTO_ENCRYPTION_KEY", "false").lower() == "true":
            new_key = Fernet.generate_key()
            new_key_str = new_key.decode()

            try:
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write(f"\nENCRYPTION_KEY={new_key_str}\n")
                try:
                    # Giới hạn quyền đọc/ghi file .env chỉ cho chủ sở hữu (chmod 600),
                    # tránh process/user khác trên cùng server đọc được khóa bí mật.
                    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
                except Exception as chmod_err:
                    logger.warning(f"Không thể giới hạn quyền file .env: {chmod_err}")

                logger.warning(
                    f"[DEV MODE] Đã tự sinh ENCRYPTION_KEY mới và lưu vào {env_path}. "
                    "TUYỆT ĐỐI KHÔNG dùng chế độ này ở staging/production - dữ liệu "
                    "mã hóa cũ sẽ mất vĩnh viễn nếu khóa bị thay đổi giữa các lần chạy "
                    "hoặc giữa các instance."
                )
            except Exception as e:
                logger.warning(f"Could not save ENCRYPTION_KEY to .env: {e}")

            os.environ["ENCRYPTION_KEY"] = new_key_str
            return new_key

        # 4. Không có khóa và không được phép tự sinh -> dừng khởi động ngay với
        # thông báo rõ ràng, thay vì âm thầm chạy tiếp bằng một khóa "ma".
        raise EncryptionKeyMissingError(
            "ENCRYPTION_KEY chưa được cấu hình. Vui lòng đặt biến môi trường "
            "ENCRYPTION_KEY (một khóa Fernet hợp lệ, sinh MỘT LẦN DUY NHẤT bằng "
            "Fernet.generate_key() và lưu cố định vào secrets manager/biến môi "
            "trường triển khai) trước khi khởi động ứng dụng. Tuyệt đối không để "
            "hệ thống tự sinh khóa ngầm, vì toàn bộ dữ liệu đã mã hóa bằng khóa cũ "
            "sẽ không thể phục hồi nếu khóa thay đổi. Nếu đây là môi trường dev cục "
            "bộ và bạn hiểu rõ rủi ro, có thể bật tạm biến môi trường "
            "ALLOW_DEV_AUTO_ENCRYPTION_KEY=true để hệ thống tự sinh khóa cho dev."
        )

    def encrypt_text(self, text: str) -> str:
        if not text:
            return ""
        return self.cipher.encrypt(text.encode("utf-8")).decode("utf-8")

    def decrypt_text(self, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""
        try:
            return self.cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return "[Lỗi giải mã nội dung]"

    def encrypt_file(self, file_path: str):
        if not os.path.exists(file_path):
            return

        with open(file_path, "rb") as f:
            data = f.read()

        # Mã hóa dữ liệu
        encrypted_data = self.cipher.encrypt(data)

        with open(file_path, "wb") as f:
            f.write(encrypted_data)

    def decrypt_file(self, file_path: str) -> bytes:
        if not os.path.exists(file_path):
            return b""

        with open(file_path, "rb") as f:
            encrypted_data = f.read()

        try:
            return self.cipher.decrypt(encrypted_data)
        except Exception as e:
            logger.error(f"File decryption error for {file_path}: {e}")
            # Nếu giải mã thất bại, tệp tin có thể đã được giải mã sẵn hoặc bị hỏng. Trả về rỗng.
            return b""
