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

# Ánh xạ mã "dạng quy định" (provision_type, xem docs/bhxh_keyphrase_spec.md mục 3)
# sang nhãn đầy đủ bằng tiếng Việt. Đây là NGUỒN DUY NHẤT (single source of truth)
# cho danh sách P1-P9 - ingest_rag.py import trực tiếp từ đây để dựng
# PROVISION_TYPE_LEGEND (dùng lúc AI gắn nhãn cho từng chunk khi ingest), còn
# GuardService.describe_provision_types() dùng để hiển thị nhãn đầy đủ cho người
# dùng (thay vì chỉ hiện mã "P1" khó hiểu) khi đoán "dạng câu hỏi" đang hỏi.
PROVISION_TYPE_LABELS = {
    "P1": "Định nghĩa/giải thích từ ngữ",
    "P2": "Nguyên tắc chung",
    "P3": "Đối tượng áp dụng",
    "P4": "Quyền và nghĩa vụ",
    "P5": "Điều kiện hưởng",
    "P6": "Mức/tỷ lệ (đóng hoặc hưởng)",
    "P7": "Trình tự, thủ tục, hồ sơ",
    "P8": "Hành vi bị nghiêm cấm/xử lý vi phạm",
    "P9": "Điều khoản chuyển tiếp/hiệu lực thi hành",
}


class GuardService:
    def __init__(self):
        # ==========================================
        # 1. TỪ KHÓA CẤM - TÁCH THÀNH 2 NHÓM
        # ==========================================
        # 1a. HARD: cụm từ gần như CHẮC CHẮN là tấn công (jailbreak/leakage),
        #     hiếm khi xuất hiện tự nhiên trong câu hỏi về BHXH -> chặn ngay khi khớp 1 cụm.
        self.hard_forbidden_keywords = [
            "ignore previous", "ignore all previous", "disregard previous",
            "system prompt", "system_prompt", "hướng dẫn hệ thống",
            "hủy bỏ chỉ thị", "hủy bỏ hướng dẫn",
            "dan", "do anything now", "developer mode", "chế độ nhà phát triển",
            "jailbreak", "you are now", "bạn bây giờ là",
            "viết mã độc", "exploit", "payload",
        ]

        # 1b. SOFT: cụm từ MƠ HỒ - có thể xuất hiện tự nhiên trong câu hỏi thật.
        #     Không chặn ngay chỉ vì khớp 1 từ soft - chỉ dùng làm tín hiệu, kết hợp
        #     với việc câu hỏi KHÔNG có từ khóa BHXH nào (xem check_input, lớp 3).
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

        # 5. Từ khóa cho needs_rag - mỗi từ khóa gắn 1 Hệ số tin cậy (Certainty
        #    Factor - CF, kiểu MYCIN) thay vì cộng điểm tùy tiện, để "độ tin cậy
        #    câu hỏi thuộc miền BHXH" có ý nghĩa xác suất/tin cậy rõ ràng, kết
        #    hợp bằng công thức CF chuẩn (xem _combine_cf_list) thay vì cộng dồn
        #    số nguyên. Core keyword (CF cao, 0.7-0.85): thuật ngữ BHXH đặc thù,
        #    hiếm khi xuất hiện ngoài miền này. Context keyword (CF thấp, 0.15-0.3):
        #    tín hiệu bổ trợ, dễ lẫn với miền khác (VD "luật", "công ty").
        #    Đặc tả đầy đủ: docs/bhxh_keyphrase_spec.md mục 4.
        self.core_keywords = {
            "bảo hiểm xã hội": 0.75, "bhxh": 0.7, "bhxh bắt buộc": 0.8, "bhxh tự nguyện": 0.8,
            "sổ bảo hiểm xã hội": 0.8, "mã số bhxh": 0.75,
            "chế độ ốm đau": 0.8, "chế độ thai sản": 0.8, "chế độ hưu trí": 0.8, "chế độ tử tuất": 0.8,
            "lương hưu": 0.75, "trợ cấp một lần": 0.7, "trợ cấp hưu trí xã hội": 0.85,
            "bảo hiểm hưu trí bổ sung": 0.85, "mức đóng bhxh": 0.8, "tỷ lệ đóng bhxh": 0.8,
            "tiền lương đóng bhxh": 0.8, "thời gian đóng bhxh": 0.8, "rút bhxh một lần": 0.85,
            "hưởng bhxh một lần": 0.85, "tuổi nghỉ hưu": 0.7, "suy giảm khả năng lao động": 0.75,
            "trợ cấp tuất": 0.8, "mai táng phí": 0.75, "tham gia bhxh": 0.75,
            "cơ quan bảo hiểm xã hội": 0.8, "quỹ bảo hiểm xã hội": 0.8,
        }
        self.context_keywords = {
            "người lao động": 0.3, "người sử dụng lao động": 0.3, "hợp đồng lao động": 0.3,
            "tiền lương": 0.25, "nghỉ việc": 0.25, "nghỉ thai sản": 0.3, "sinh con": 0.3, "nuôi con nuôi": 0.3,
            "thai sản": 0.3, "tai nạn lao động": 0.3, "bệnh nghề nghiệp": 0.3, "nghỉ hưu": 0.3, "về hưu": 0.3,
            "trốn đóng": 0.3, "chậm đóng": 0.3, "nợ bảo hiểm": 0.3, "truy thu": 0.25,
            "hồ sơ hưởng": 0.3, "thủ tục hưởng": 0.3, "giải quyết chế độ": 0.3,
            "khiếu nại": 0.2, "tố cáo": 0.2, "xử phạt": 0.2, "thanh tra": 0.2,
            "doanh nghiệp": 0.15, "công ty": 0.15, "viên chức": 0.25, "công chức": 0.25, "lao động tự do": 0.25,
            "thân nhân": 0.25, "bảo hiểm y tế": 0.25, "bảo hiểm thất nghiệp": 0.25,
            "luật": 0.15, "nghị định": 0.15, "thông tư": 0.15,
        }

        # Ngưỡng CF để kích hoạt RAG (needs_rag). 0.5 = "nhiều khả năng đúng hơn
        # là sai" theo thang CF chuẩn [-1, 1]; một core keyword bất kỳ (CF thấp
        # nhất 0.7) đã tự nó vượt ngưỡng này, nên vẫn giữ điều kiện "phải có ít
        # nhất 1 core keyword" song song để tránh việc nhiều context keyword mơ
        # hồ cộng dồn đủ CF mà không hề có tín hiệu BHXH rõ ràng nào.
        self.needs_rag_cf_threshold = 0.5

        # 6. Từ khóa nhận diện "dạng quy định" (provision_type P1-P9) mà CÂU HỎI
        #    đang hỏi - dùng để hybrid re-rank kết quả RAG ở
        #    supabase_service.search_legal_documents(), ưu tiên chunk vừa gần
        #    nghĩa (similarity) vừa đúng nhóm khái niệm câu hỏi đang hỏi.
        #    Đặc tả: docs/bhxh_keyphrase_spec.md mục 3 và mục 6.2 bước 4.
        #    Một câu hỏi có thể khớp nhiều mã cùng lúc (VD hỏi cả điều kiện lẫn
        #    mức hưởng) - đây chỉ là gợi ý re-rank "mềm", không dùng để lọc/chặn.
        self.provision_type_keywords = {
            "P1": ["là gì", "định nghĩa", "khái niệm", "được hiểu là", "nghĩa là"],
            "P2": ["nguyên tắc", "chính sách của nhà nước"],
            "P3": ["đối tượng áp dụng", "đối tượng nào", "ai được", "ai phải",
                   "áp dụng đối với", "áp dụng cho"],
            "P4": ["quyền lợi", "nghĩa vụ", "trách nhiệm", "có quyền", "có được"],
            "P5": ["điều kiện", "đủ điều kiện", "khi nào được hưởng",
                   "bao nhiêu năm thì được", "bao lâu thì được"],
            "P6": ["mức đóng", "mức hưởng", "tỷ lệ đóng", "tỷ lệ hưởng",
                   "bao nhiêu phần trăm", "bao nhiêu tiền", "cách tính", "công thức tính"],
            "P7": ["thủ tục", "hồ sơ", "trình tự", "quy trình", "nộp ở đâu",
                   "làm ở đâu", "đóng ở đâu", "cần giấy tờ gì", "thời hạn giải quyết"],
            "P8": ["bị phạt", "xử phạt", "vi phạm", "nghiêm cấm", "trốn đóng",
                   "chậm đóng", "xử lý vi phạm"],
            "P9": ["hiệu lực thi hành", "hiệu lực từ", "trước ngày luật",
                   "chuyển tiếp", "áp dụng từ ngày"],
        }

        # Danh sách từ tiếng Việt không dấu phổ biến, dùng để nhận diện tiếng Việt
        # gõ không dấu khi kiểm tra ngôn ngữ đầu ra.
        self._vn_no_accent_words = {
            "cho", "cua", "toi", "khong", "co", "ve", "duoc", "trong", "va", "nhung",
            "la", "cac", "mot", "nguoi", "nay", "the", "neu", "thi", "khi", "voi",
            "theo", "nam", "thang", "dong", "tien", "bao", "hiem", "quy", "dinh",
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
        text = re.sub(r"[​‌‍﻿]", "", text)
        return text

    @staticmethod
    def _strip_for_match(text: str) -> str:
        """Bỏ khoảng trắng/ký tự đặc biệt/underscore để chống né kiểu 'q-u-ê-n đ-i'."""
        return re.sub(r"\W+", "", text.lower()).replace("_", "")

    def _count_keyword_hits(self, clean_input_words: str, keywords) -> set[str]:
        """
        Trả về TẬP HỢP các keyword canonical đã khớp (không cộng dồn theo substring
        trùng lặp, VD 'rút bhxh một lần' chứa 'bhxh' chỉ tính là các match riêng
        biệt). `keywords` có thể là list hoặc dict (keyword -> CF) - hàm chỉ lặp
        qua các "khóa" (từ khóa), không quan tâm cấu trúc chứa nó.
        """
        hits = set()
        for kw in keywords:
            pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
            if re.search(pattern, clean_input_words, flags=re.IGNORECASE):
                hits.add(kw)
        return hits

    @staticmethod
    def _combine_two_cf(cf1: float, cf2: float) -> float:
        """
        Công thức kết hợp Hệ số tin cậy (Certainty Factor) chuẩn kiểu MYCIN, kết
        hợp 2 bằng chứng ĐỘC LẬP thành 1 CF duy nhất - thay cho việc cộng điểm
        tùy tiện. Với các giá trị luôn dương (trường hợp của core/context
        keywords ở đây), công thức này tương đương 1 - (1-cf1)(1-cf2): mỗi bằng
        chứng thêm vào làm tăng độ tin cậy nhưng giảm dần biên độ, không bao giờ
        vượt quá 1.
        """
        if cf1 >= 0 and cf2 >= 0:
            return cf1 + cf2 * (1 - cf1)
        if cf1 < 0 and cf2 < 0:
            return cf1 + cf2 * (1 + cf1)
        return (cf1 + cf2) / (1 - min(abs(cf1), abs(cf2)))

    def _combine_cf_list(self, cf_values: list[float]) -> float:
        """Kết hợp tuần tự nhiều CF thành 1 giá trị duy nhất bằng _combine_two_cf.
        Công thức CF là giao hoán/kết hợp (associative) với các giá trị cùng dấu,
        nên thứ tự duyệt qua danh sách không ảnh hưởng tới kết quả cuối."""
        combined = 0.0
        for cf in cf_values:
            combined = self._combine_two_cf(combined, cf)
        return combined

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
        # bất kỳ từ khóa BHXH nào (core/context) -> giảm false positive cho
        # câu hỏi thật kiểu "bỏ qua thời hạn đóng bhxh thì bị phạt gì".
        soft_hit = None
        for keyword in self.soft_forbidden_keywords:
            stripped_kw = self._strip_for_match(keyword)
            if stripped_kw in clean_lower_input:
                soft_hit = keyword
                break

        if soft_hit:
            has_bhxh_context = self._count_keyword_hits(lower_input, self.core_keywords) or \
                                self._count_keyword_hits(lower_input, self.context_keywords)
            if not has_bhxh_context:
                reason = f"Phát hiện từ khóa nghi vấn '{soft_hit}' không kèm ngữ cảnh bảo hiểm xã hội"
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
        BƯỚC 4: Xác định câu hỏi có cần tra cứu RAG hay không, dùng mô hình Hệ số
        tin cậy (Certainty Factor): mỗi từ khóa khớp đóng góp 1 CF độc lập
        (self.core_keywords/self.context_keywords), các CF được kết hợp bằng
        công thức CF chuẩn (_combine_cf_list) thành CF_kết_hợp duy nhất, sau đó
        so với ngưỡng self.needs_rag_cf_threshold - thay cho cách cộng điểm tùy
        ý (2đ/1đ) trước đây.

        Vẫn giữ điều kiện "phải có ít nhất 1 core keyword": vì CF của core
        keyword thấp nhất (0.7) đã tự nó vượt ngưỡng 0.5, nếu bỏ điều kiện này
        thì chỉ cần 2 context keyword mơ hồ (VD "luật" + "công ty", CF 0.15 mỗi
        cái) kết hợp lại cũng có thể vượt 0.5 dù câu hỏi không hề nhắc gì tới
        BHXH - core keyword là điều kiện CẦN, CF là điều kiện ĐỦ.
        """
        if not user_input or not user_input.strip():
            return False, "Câu hỏi trống"

        clean_input = self._normalize(user_input).strip().lower()

        if len(clean_input) < 10:
            return False, "Câu hỏi quá ngắn"

        core_hits = self._count_keyword_hits(clean_input, self.core_keywords)
        context_hits = self._count_keyword_hits(clean_input, self.context_keywords)

        cf_values = [self.core_keywords[kw] for kw in core_hits] + \
                    [self.context_keywords[kw] for kw in context_hits]
        combined_cf = self._combine_cf_list(cf_values)

        if core_hits and combined_cf >= self.needs_rag_cf_threshold:
            return True, ""
        else:
            reason = "Câu hỏi không liên quan đến bảo hiểm xã hội"
            logger.info(f"BỊ CHẶN (needs_rag): {reason} (CF={combined_cf:.2f})")
            return False, reason

    def classify_provision_types(self, user_input: str) -> set[str]:
        """
        Đoán "dạng quy định" (provision_type, mã P1-P9 - xem
        docs/bhxh_keyphrase_spec.md mục 3) mà câu hỏi đang hỏi, dựa trên các cụm
        từ dấu hiệu ở self.provision_type_keywords. Có thể trả về nhiều mã cùng
        lúc (câu hỏi hỏi cả điều kiện lẫn mức hưởng), hoặc set rỗng nếu không
        nhận diện được dạng nào rõ ràng.

        Dùng để HYBRID RE-RANK "mềm" ở supabase_service.search_legal_documents()
        (mục 6.2 bước 4) - chỉ cộng thêm điểm ưu tiên cho chunk có provision_type
        khớp, KHÔNG dùng để lọc/chặn câu hỏi như needs_rag().
        """
        if not user_input:
            return set()

        clean_input = self._normalize(user_input).strip().lower()
        matched = set()
        for ptype, phrases in self.provision_type_keywords.items():
            for phrase in phrases:
                if phrase in clean_input:
                    matched.add(ptype)
                    break
        return matched

    def describe_provision_types(self, provision_types) -> list[str]:
        """
        Chuyển tập mã P1-P9 (kết quả của classify_provision_types) thành danh
        sách nhãn đầy đủ bằng tiếng Việt (VD "P1" -> "Định nghĩa/giải thích từ
        ngữ"), sắp theo thứ tự P1->P9, để hiển thị cho người dùng thay vì lộ mã
        nội bộ khó hiểu.
        """
        if not provision_types:
            return []
        return [PROVISION_TYPE_LABELS[p] for p in sorted(provision_types) if p in PROVISION_TYPE_LABELS]

    # ==========================================
    # GUARD CHO NGỮ CẢNH RAG (RETRIEVED CONTEXT)
    # ==========================================

    def check_rag_context(self, retrieved_chunks: list[str]) -> tuple[bool, str | None]:
        """
        Kiểm tra nội dung các đoạn tài liệu được RAG truy xuất TRƯỚC KHI đưa vào
        prompt của LLM chính. Đây là lớp phòng thủ chống "indirect prompt
        injection" - kẻ tấn công chèn chỉ thị độc hại vào nguồn dữ liệu (văn bản
        luật giả mạo, tài liệu bị chèn thêm) để chiếm quyền điều khiển AI qua
        đường context thay vì qua user_input.

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
