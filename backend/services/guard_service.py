import re
import time
import logging
import unicodedata

logger = logging.getLogger("guard_service")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [Guard] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class GuardService:
    def __init__(self):
        # ==========================================
        # 1. TỪ KHÓA CẤM - TÁCH THÀNH 2 NHÓM
        # ==========================================
        # 1a. HARD: cụm từ gần như CHẮC CHẮN là tấn công (jailbreak/leakage),
        #     hiếm khi xuất hiện tự nhiên trong câu hỏi về thuế -> chặn ngay khi khớp 1 cụm.
        self.hard_forbidden_keywords = [
            "ignore previous", "ignore all previous", "disregard previous",
            "system prompt", "system_prompt", "hướng dẫn hệ thống",
            "hủy bỏ chỉ thị", "hủy bỏ hướng dẫn",
            "dan", "do anything now", "developer mode", "chế độ nhà phát triển",
            "jailbreak", "you are now", "bạn bây giờ là",
            "viết mã độc", "exploit", "payload",
        ]

        # 1b. SOFT: cụm từ MƠ HỒ - có thể xuất hiện tự nhiên trong câu hỏi thật
        #     (VD "bỏ qua thời hạn nộp thuế", "đóng vai chủ hộ kinh doanh").
        #     Không chặn ngay chỉ vì khớp 1 từ soft - chỉ dùng làm tín hiệu, kết hợp
        #     với việc câu hỏi KHÔNG có từ khóa thuế nào (xem check_input, lớp 3).
        self.soft_forbidden_keywords = [
            "bỏ qua", "quên đi", "quên hết", "quên tất cả", "từ bây giờ",
            "hướng dẫn trước đó", "câu lệnh ban đầu", "đóng vai", "hoá thân",
            "hãy làm ngơ", "ghi đè", "nhiệm vụ duy nhất",
            "hack", "lỗ hổng",
        ]

        # 2. Regex phát hiện các mẫu chèn mã độc hoặc lệnh hệ thống (Code Injection)
        self.malicious_patterns = [
            re.compile(r"```(bash|sh|python|js|javascript|cmd|powershell)"),  # ép AI xuất/chạy code
            re.compile(r"\{\{.*\}\}"),  # Jinja/Template injection
            re.compile(r"\b(exec|eval|os\.system|subprocess)\b", re.IGNORECASE),  # hàm thực thi mã
        ]

        # 3. Giới hạn độ dài đầu vào (Tránh DOS / Token exhaustion)
        self.max_length = 1500

        # 4. BẢO MẬT & PHÒNG THỦ
        self.security_rules = {
            "vietnamese_only": True,
            "prevent_leakage": True,
            "no_empty_response": True,
        }

        # 4.1. Từ khóa rò rỉ dữ liệu (Prompt Leakage Detection in Output)
        self.leakage_keywords = [
            "system prompt", "system_prompt", "rag_context", "ngữ cảnh nội bộ",
            "chỉ thị hệ thống", "cấu trúc dữ liệu", "khung câu hỏi", "prompt gốc",
        ]

        # 4.2. Mẫu chỉ thị "giả mạo" thường bị chèn vào tài liệu RAG để tấn công gián tiếp
        #      (indirect prompt injection qua nội dung retrieve được).
        self.rag_injection_patterns = [
            re.compile(r"(bỏ qua|ignore)\s+(mọi|tất cả|previous|all)\s*(hướng dẫn|instructions?)", re.IGNORECASE),
            re.compile(r"(bạn là|you are)\s+(một|an?)\s*(ai|trợ lý|assistant)\s*(mới|new)", re.IGNORECASE),
            re.compile(r"system\s*prompt", re.IGNORECASE),
            re.compile(r"<\s*(system|instruction|admin)\s*>", re.IGNORECASE),
        ]

        # 5. Từ khóa cho needs_rag - dùng WORD-LEVEL matching (không cộng dồn substring)
        self.core_keywords = [
            "thuế", "vat", "gtgt", "tncn", "ttđb", "thuế xuất nhập khẩu", "chịu thuế",
            "kê khai", "khai báo", "khai thuế", "nộp thuế", "hoàn thuế", "quyết toán", "tờ khai",
            "hóa đơn", "giá trị gia tăng", "thu nhập cá nhân", "loại thuế", "thuế suất",
            "hộ kinh doanh", "cá nhân kinh doanh", "mã số thuế", "mst", "tính thuế",
        ]
        self.context_keywords = [
            "thu chi", "doanh thu", "chi phí", "lợi nhuận", "kế toán",
            "khấu trừ", "miễn giảm", "luật", "nghị định", "thông tư",
            "thu nhập", "mặt hàng", "xuất khẩu", "nhập khẩu", "bán hàng", "kinh doanh",
            "phạt", "chậm nộp", "trốn thuế", "đóng thuế", "nghĩa vụ", "dịch vụ", "spa",
            "làm đẹp", "thẩm mỹ", "sửa chữa", "tư vấn", "xây dựng", "gia công", "sản xuất",
            "bán lẻ", "bán buôn", "nội dung số", "cho thuê tài sản", "đại lý bảo hiểm",
            "xổ số", "đa cấp", "lưu trú", "vận tải", "nhà hàng", "quán ăn", "cafe",
            "sản phẩm số", "quảng cáo trực tuyến", "cá cược", "giải trí",
        ]

        # Danh sách từ tiếng Việt không dấu phổ biến, mở rộng hơn bản gốc, dùng để
        # nhận diện tiếng Việt gõ không dấu khi kiểm tra ngôn ngữ đầu ra.
        self._vn_no_accent_words = {
            "cho", "cua", "toi", "khong", "co", "ve", "duoc", "trong", "va", "nhung",
            "la", "cac", "mot", "nguoi", "nay", "the", "neu", "thi", "khi", "voi",
            "theo", "nam", "thang", "dong", "tien", "thue", "luat", "quy", "dinh",
            "ban", "hay", "nhu", "sau", "truoc", "den", "tu", "den", "hoac", "bi",
        }

    # ==========================================
    # TIỆN ÍCH DÙNG CHUNG
    # ==========================================

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Chuẩn hóa Unicode (NFC) và loại bỏ ký tự zero-width thường dùng để né filter
        (zero-width space/joiner/non-joiner, BOM...).
        """
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
        return text

    @staticmethod
    def _strip_for_match(text: str) -> str:
        """Bỏ khoảng trắng/ký tự đặc biệt/underscore để chống né kiểu 'q-u-ê-n đ-i'."""
        return re.sub(r"\W+", "", text.lower()).replace("_", "")

    def _count_keyword_hits(self, clean_input_words: str, keywords: list[str]) -> set[str]:
        """
        Trả về TẬP HỢP các keyword canonical đã khớp (không cộng dồn theo substring
        trùng lặp, VD 'nộp thuế' chứa 'thuế' chỉ tính là các match riêng biệt,
        nhưng độ điểm được tính theo SỐ KEYWORD KHÁC NHAU khớp, không theo số lần
        substring xuất hiện).
        """
        hits = set()
        for kw in keywords:
            pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
            if re.search(pattern, clean_input_words, flags=re.IGNORECASE):
                hits.add(kw)
        return hits

    # ==========================================
    # QUY TRÌNH KIỂM TRA ĐẦU VÀO (INPUT PIPELINE)
    # ==========================================

    def sanitize_input(self, user_input: str) -> str:
        """
        BƯỚC 1: Chuẩn hóa Unicode, loại ký tự zero-width, rồi làm sạch chống XML injection.
        """
        text = self._normalize(user_input)
        return text.replace("<", "&lt;").replace(">", "&gt;") if text else ""

    def check_input(self, user_input: str) -> tuple[bool, str | None]:
        """
        BƯỚC 2: Bộ lọc bảo mật đa lớp (Multi-layer WAF for LLM).
        Trả về (True, None) nếu an toàn, (False, lý do) nếu có dấu hiệu tấn công.
        """
        if not user_input or not user_input.strip():
            return True, None

        user_input = self._normalize(user_input)

        # Lớp 1: Kiểm tra độ dài
        if len(user_input) > self.max_length:
            reason = "Câu hỏi quá dài"
            logger.warning(f"BỊ CHẶN: {reason}")
            return False, reason

        # Lớp 2: Phát hiện ký tự rác
        special_chars = sum(1 for c in user_input if not c.isalnum() and not c.isspace())
        special_char_ratio = special_chars / len(user_input)
        if special_char_ratio > 0.4:
            reason = "Câu hỏi có quá nhiều ký tự đặc biệt (Tokenizer attack?)"
            logger.warning(f"BỊ CHẶN: {reason}")
            return False, reason

        lower_input = user_input.lower()
        clean_lower_input = self._strip_for_match(lower_input)

        # Lớp 3a: Từ khóa HARD -> chặn ngay khi khớp 1 cụm
        for keyword in self.hard_forbidden_keywords:
            stripped_kw = self._strip_for_match(keyword)
            if stripped_kw in clean_lower_input:
                reason = f"Phát hiện từ khóa tấn công '{keyword}'"
                logger.warning(f"BỊ CHẶN: {reason}")
                return False, reason

        # Lớp 3b: Từ khóa SOFT -> chỉ chặn khi khớp VÀ câu hỏi không hề chứa
        # bất kỳ từ khóa thuế nào (core/context) -> giảm false positive cho
        # câu hỏi thật kiểu "bỏ qua thời hạn nộp thuế thì bị phạt gì".
        soft_hit = None
        for keyword in self.soft_forbidden_keywords:
            stripped_kw = self._strip_for_match(keyword)
            if stripped_kw in clean_lower_input:
                soft_hit = keyword
                break

        if soft_hit:
            has_tax_context = self._count_keyword_hits(lower_input, self.core_keywords) or \
                               self._count_keyword_hits(lower_input, self.context_keywords)
            if not has_tax_context:
                reason = f"Phát hiện từ khóa nghi vấn '{soft_hit}' không kèm ngữ cảnh thuế"
                logger.warning(f"BỊ CHẶN: {reason}")
                return False, reason

        # Lớp 4: Quét cú pháp mã độc bằng Regex
        for pattern in self.malicious_patterns:
            if pattern.search(user_input):
                reason = "Phát hiện cú pháp độc hại (Regex)"
                logger.warning(f"BỊ CHẶN: {reason}")
                return False, reason

        return True, None

    def check_relevance(self, prompt: str, gemini_service=None) -> str:
        """
        BƯỚC 3: Phân loại câu hỏi (rule-based, tiết kiệm quota).
        Trả về: "RELEVANT" hoặc "GREETING".
        """
        if not prompt:
            return "RELEVANT"

        clean_prompt = self._normalize(prompt).strip().lower()

        greetings = ["chào", "hello", "hi ", "cảm ơn", "thanks", "tạm biệt", "bye", "chúc", "ok", "dạ", "vâng"]
        if len(clean_prompt) < 30 and any(g in clean_prompt for g in greetings):
            return "GREETING"

        return "RELEVANT"

    def needs_rag(self, user_input: str) -> tuple[bool, str]:
        """
        BƯỚC 4: Xác định câu hỏi có cần tra cứu RAG hay không, dùng scoring
        dựa trên SỐ KEYWORD KHÁC NHAU khớp (word-boundary), không cộng dồn
        theo substring trùng lặp (VD 'nộp thuế' không tính thêm cho 'thuế').
        """
        if not user_input or not user_input.strip():
            return False, "Câu hỏi trống"

        clean_input = self._normalize(user_input).strip().lower()

        if len(clean_input) < 10:
            return False, "Câu hỏi quá ngắn"

        core_hits = self._count_keyword_hits(clean_input, self.core_keywords)
        context_hits = self._count_keyword_hits(clean_input, self.context_keywords)

        # Điểm: mỗi core keyword riêng biệt = 2đ, mỗi context keyword riêng biệt = 1đ
        score = 2 * len(core_hits) + 1 * len(context_hits)

        if core_hits and score >= 3:
            return True, ""
        else:
            reason = "Câu hỏi không liên quan đến thuế cho hộ kinh doanh/cá nhân kinh doanh"
            logger.info(f"BỊ CHẶN (needs_rag): {reason}")
            return False, reason

    # ==========================================
    # GUARD CHO NGỮ CẢNH RAG (RETRIEVED CONTEXT)
    # ==========================================

    def check_rag_context(self, retrieved_chunks: list[str]) -> tuple[bool, str | None]:
        """
        MỚI: Kiểm tra nội dung các đoạn tài liệu được RAG truy xuất TRƯỚC KHI
        đưa vào prompt của LLM chính. Đây là lớp phòng thủ chống
        "indirect prompt injection" - kẻ tấn công chèn chỉ thị độc hại vào
        nguồn dữ liệu (văn bản luật giả mạo, tài liệu bị chèn thêm) để chiếm
        quyền điều khiển AI qua đường context thay vì qua user_input.

        Trả về (True, None) nếu context an toàn để dùng, (False, lý do) nếu
        nghi ngờ có chỉ thị độc hại chèn trong tài liệu.
        """
        if not retrieved_chunks:
            return True, None

        for chunk in retrieved_chunks:
            if not chunk:
                continue
            text = self._normalize(chunk)
            for pattern in self.rag_injection_patterns:
                if pattern.search(text):
                    reason = "Phát hiện dấu hiệu prompt injection trong tài liệu RAG truy xuất"
                    logger.error(f"BỊ CHẶN (rag_context): {reason} | mẫu: {pattern.pattern}")
                    return False, reason

        return True, None

    # ==========================================
    # QUY TRÌNH KIỂM TRA ĐẦU RA (OUTPUT PIPELINE)
    # ==========================================

    def check_response(self, response: str) -> tuple[bool, str | None]:
        """
        BƯỚC 5: Kiểm tra phản hồi của AI theo các nguyên tắc bảo mật.
        """
        # 1. Không bao giờ trả về câu trả lời rỗng
        if self.security_rules.get("no_empty_response"):
            if not response or not response.strip():
                reason = "Phát hiện phản hồi rỗng"
                logger.warning(f"BỊ CHẶN: {reason}.")
                return False, reason

        response = self._normalize(response)

        # 2. Không tiết lộ chỉ thị hệ thống / context nội bộ
        if self.security_rules.get("prevent_leakage"):
            response_lower = response.lower()
            for keyword in self.leakage_keywords:
                if keyword in response_lower:
                    reason = f"Phát hiện rò rỉ thông tin prompt/internal trong phản hồi ('{keyword}')"
                    logger.error(f"BỊ CHẶN: {reason}")
                    return False, reason

        # 3. Chỉ trả lời bằng Tiếng Việt
        if self.security_rules.get("vietnamese_only"):
            if response and response.strip():
                vietnamese_chars_pattern = re.compile(
                    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
                    re.IGNORECASE,
                )
                if len(response) > 20 and not vietnamese_chars_pattern.search(response):
                    words = set(re.findall(r"[a-zA-Z]+", response.lower()))
                    # Yêu cầu ít nhất 2 từ không dấu phổ biến khớp (thay vì 1) để giảm
                    # nguy cơ 1 từ trùng ngẫu nhiên (VD "co", "la") lọt qua tiếng Anh.
                    matched = words.intersection(self._vn_no_accent_words)
                    if len(matched) < 2:
                        reason = "Câu trả lời không bằng tiếng Việt (Violation ngôn ngữ)"
                        logger.warning(f"BỊ CHẶN: {reason}")
                        return False, reason

        return True, None
