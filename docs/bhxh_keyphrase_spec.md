# Đặc tả Keyphrase - Hệ thống tra cứu kiến thức pháp luật (Luật Bảo hiểm xã hội)

## 1. Lĩnh vực và văn bản pháp luật được chọn

- **Lĩnh vực:** Bảo hiểm xã hội (BHXH)
Cả 6 văn bản dưới đây **đã ingest xong** vào bảng `legal_documents` trên Supabase (đã nhúng vector, sẵn sàng để `search_legal_documents` truy xuất):

1. Luật Bảo hiểm xã hội số 41/2024/QH15 (hiệu lực 01/07/2025, thay thế Luật BHXH 2014).
2. Nghị định số 157/2025/NĐ-CP: BHXH bắt buộc đối với quân nhân, công an nhân dân, dân quân thường trực, người làm công tác cơ yếu hưởng lương như quân nhân.
3. Nghị định số 158/2025/NĐ-CP: hướng dẫn chi tiết BHXH bắt buộc.
4. Nghị định số 159/2025/NĐ-CP: hướng dẫn chi tiết BHXH tự nguyện.
5. Nghị định số 176/2025/NĐ-CP: trợ cấp hưu trí xã hội.
6. Nghị định số 274/2025/NĐ-CP: chậm đóng, trốn đóng BHXH bắt buộc/bảo hiểm thất nghiệp; khiếu nại, tố cáo về BHXH.

- **Đối tượng người dùng mục tiêu:** người lao động, người sử dụng lao động, người tham gia BHXH tự nguyện, thân nhân người tham gia.

## 2. Thành phần khái niệm (Concept taxonomy) - tài liệu phân tích

Nhóm khái niệm A–H dưới đây là khung phân tích dùng để thiết kế bộ keyphrase ở mục 4. Mỗi keyphrase ở mục 4 được liệt kê xuất phát từ 1 trong các nhóm khái niệm sau:

| Mã nhóm | Tên nhóm | Mô tả | Ví dụ khái niệm |
|---|---|---|---|
| A | Đối tượng & phạm vi | Ai tham gia, ai áp dụng | người lao động, người sử dụng lao động, thân nhân, cơ quan BHXH |
| B | Loại hình BHXH | Phân loại chế độ bảo hiểm | BHXH bắt buộc, BHXH tự nguyện, bảo hiểm hưu trí bổ sung, trợ cấp hưu trí xã hội |
| C | Chế độ/quyền lợi | Các chế độ cụ thể được hưởng | ốm đau, thai sản, hưu trí, tử tuất |
| D | Nghĩa vụ tài chính | Nghĩa vụ đóng góp | mức đóng, tỷ lệ đóng, tiền lương làm căn cứ đóng, phương thức đóng, chậm đóng, trốn đóng |
| E | Điều kiện hưởng | Điều kiện để đủ tư cách nhận quyền lợi | thời gian đóng BHXH, tuổi nghỉ hưu, mức suy giảm khả năng lao động |
| F | Mức hưởng & cách tính | Công thức/kết quả tài chính | tỷ lệ hưởng lương hưu, mức bình quân tiền lương tháng đóng, trợ cấp một lần |
| G | Thủ tục & hồ sơ | Quy trình hành chính | hồ sơ hưởng chế độ, thời hạn giải quyết, sổ BHXH, mã số BHXH |
| H | Quản lý & xử lý vi phạm | Giám sát, chế tài | quỹ BHXH, thanh tra, xử phạt vi phạm hành chính, khiếu nại, tố cáo |

## 3. Dạng quy định (Provision-type taxonomy) - triển khai trong code

"Dạng quy định" là vai trò tu từ/pháp lý của một đoạn luật (Điều/Khoản). Khác với mục 2, taxonomy này **có chạy thật** trong hệ thống, ở cả 2 chiều: (a) gắn nhãn cho từng đoạn luật lúc ingest, và (b) đoán "dạng câu hỏi" đang hỏi để ưu tiên kết quả tìm kiếm phù hợp hơn.

| Mã | Dạng quy định | Dấu hiệu nhận biết trong văn bản |
|---|---|---|
| P1 | Định nghĩa / giải thích từ ngữ | "trong Luật này, các từ ngữ dưới đây được hiểu như sau", "là việc...", "là khoản..." |
| P2 | Nguyên tắc chung | "nguyên tắc", "chính sách của Nhà nước" |
| P3 | Đối tượng áp dụng | "đối tượng áp dụng", "áp dụng đối với" |
| P4 | Quyền và nghĩa vụ | "có quyền", "có trách nhiệm", "có nghĩa vụ" |
| P5 | Điều kiện hưởng | "được hưởng... khi có đủ các điều kiện sau", "đủ... năm đóng" |
| P6 | Mức/tỷ lệ (đóng hoặc hưởng) | "mức đóng bằng...%", "mức hưởng bằng...", "tính theo công thức" |
| P7 | Trình tự, thủ tục, hồ sơ | "hồ sơ gồm", "trình tự thực hiện", "trong thời hạn... ngày" |
| P8 | Hành vi bị nghiêm cấm / xử lý vi phạm | "nghiêm cấm", "xử lý vi phạm", "bị xử phạt" |
| P9 | Điều khoản chuyển tiếp / hiệu lực thi hành | "kể từ ngày Luật này có hiệu lực", "đối với người đã tham gia trước ngày..." |

**Nơi triển khai trong code (nguồn duy nhất - single source of truth):**
- `PROVISION_TYPE_LABELS` trong [guard_service.py](../backend/services/guard_service.py) - dict `{mã: nhãn tiếng Việt}` là nơi định nghĩa DUY NHẤT danh sách P1–P9; mọi nơi khác import từ đây, không định nghĩa lại.
- [ingest_rag.py](../backend/ingest_rag.py) import `PROVISION_TYPE_LABELS` để dựng `PROVISION_TYPE_LEGEND` - chèn vào prompt bóc tách, để AI gắn `provision_type` cho từng chunk lúc ingest (xem mục 6.3).
- `GuardService.classify_provision_types(user_input)` - đoán câu hỏi đang thuộc (các) mã P1–P9 nào, dựa trên `self.provision_type_keywords` (cụm từ dấu hiệu cho từng mã, VD "điều kiện", "đủ điều kiện" → P5). Có thể trả về nhiều mã cùng lúc.
- `GuardService.describe_provision_types(...)` - chuyển tập mã thành nhãn tiếng Việt đầy đủ để hiển thị cho người dùng (không lộ mã nội bộ "P5").
- Dùng ở `app.py` (route `/api/chat`) → truyền vào `supabase_service.search_legal_documents(..., query_provision_types=...)` để hybrid re-rank (mục 6.2 bước 4), và trả `query_provision_labels` trong JSON response → hiển thị ở frontend (`ChatView.tsx`, trường `queryProvisionLabels`).

## 4. Bộ keyphrase — quyết định 2 tầng (triển khai trong `guard_service.py`)

`needs_rag()` quyết định theo **2 tầng khác bản chất**, không còn là 1 công thức tính điểm duy nhất:

- **Tầng 1 — Luật dẫn (Production Rule):** chỉ cần khớp **đúng 1 core keyword** (thuật ngữ BHXH đặc thù, hiếm khi xuất hiện ngoài miền này) là kích hoạt RAG ngay, không cần điều kiện gì thêm. Đây là quyết định nhị phân thuần túy.
- **Tầng 2 — Heuristic / tri thức không chắc chắn:** chỉ chạy khi Tầng 1 **không** khớp core keyword nào. Đếm số **context keyword khác nhau** đã khớp (tín hiệu yếu, dễ lẫn miền khác như "luật", "công ty") — mỗi context keyword là 1 bằng chứng độc lập không đủ tin cậy nếu đứng một mình; đạt đủ `self.context_hits_threshold = 3` bằng chứng khác nhau mới đủ "tích lũy" tin cậy để coi là liên quan BHXH.

Tầng 2 giúp các câu hỏi diễn đạt vòng vo, không gọi đúng tên BHXH nhưng vẫn rõ ràng liên quan — VD *"người lao động nghỉ việc có được nhận bảo hiểm thất nghiệp không?"* (3 context keyword: "người lao động", "nghỉ việc", "bảo hiểm thất nghiệp" → đạt ngưỡng → chấp nhận), trong khi *"công ty tôi có người lao động nghỉ việc thì xử lý sao?"* (chỉ 2 context keyword) vẫn bị từ chối vì chưa đủ tích lũy bằng chứng.

**Cài đặt:** [guard_service.py](../backend/services/guard_service.py) — `self.core_keywords`/`self.context_keywords` (list), `self.context_hits_threshold`, `needs_rag()`.

**Core keywords (Tầng 1 — chỉ cần khớp 1 từ là đủ):**
bảo hiểm xã hội, bhxh, bhxh bắt buộc, bhxh tự nguyện, sổ bảo hiểm xã hội, mã số bhxh, chế độ ốm đau, chế độ thai sản, chế độ hưu trí, chế độ tử tuất, lương hưu, trợ cấp một lần, trợ cấp hưu trí xã hội, bảo hiểm hưu trí bổ sung, mức đóng bhxh, tỷ lệ đóng bhxh, tiền lương đóng bhxh, thời gian đóng bhxh, rút bhxh một lần, hưởng bhxh một lần, tuổi nghỉ hưu, suy giảm khả năng lao động, trợ cấp tuất, mai táng phí, tham gia bhxh, cơ quan bảo hiểm xã hội, quỹ bảo hiểm xã hội, tai nạn lao động, bệnh nghề nghiệp.

**Context keywords (Tầng 2 — cần ≥3 từ khác nhau khớp cùng lúc, khi không có core keyword nào; cũng dùng ở `check_input()` để nhận diện ngữ cảnh BHXH khi có từ khóa nghi vấn):**
người lao động, người sử dụng lao động, hợp đồng lao động, tiền lương, nghỉ việc, nghỉ thai sản, sinh con, nuôi con nuôi, thai sản, nghỉ hưu, về hưu, trốn đóng, chậm đóng, nợ bảo hiểm, truy thu, không đóng bảo hiểm, hồ sơ hưởng, thủ tục hưởng, giải quyết chế độ, nộp hồ sơ, giải quyết hồ sơ, khiếu nại, tố cáo, xử phạt, thanh tra, doanh nghiệp, công ty, viên chức, công chức, lao động tự do, thân nhân, bảo hiểm y tế, bảo hiểm thất nghiệp, luật, nghị định, thông tư, mức hưởng, tỷ lệ hưởng, cách tính, công thức tính, quyền lợi, ốm đau, tử tuất, nghỉ ốm, bảo lưu, chốt sổ, trừ lương hưu.

**Từ khóa dấu hiệu cho `provision_type` (mục 3), dùng bởi `classify_provision_types()`:** mỗi mã P1–P9 có 1 danh sách cụm từ riêng trong `self.provision_type_keywords` (VD P5 "Điều kiện hưởng" ↔ "điều kiện", "đủ điều kiện", "khi nào được hưởng"...) - xem đầy đủ trong code, không lặp lại ở đây để tránh 2 nguồn dữ liệu lệch nhau.


## 5. Thiết kế giải pháp tra cứu - Tra cứu theo ngữ nghĩa đơn giản (simple semantic search)

Toàn bộ luồng nằm trong `app.py` (route `/api/chat`) gọi `guard_service` rồi `supabase_service.search_legal_documents()`:

- **Bước 1 - Guard/Routing (2 tầng: luật + heuristic):** `guard_service.needs_rag()` quyết định câu hỏi có thuộc miền BHXH và có cần kích hoạt RAG không - Tầng 1 chấp nhận ngay nếu khớp ≥1 core keyword; Tầng 2 (chỉ chạy khi không có core keyword) chấp nhận nếu khớp ≥3 context keyword khác nhau (mục 4).
- **Bước 2 - Vector retrieval:** `gemini_service.embed_text()` (Gemini Embedding, 768 chiều) nhúng câu hỏi, gọi RPC `match_legal_documents` trên Supabase pgvector để tìm chunk gần nghĩa nhất qua cosine similarity (`match_threshold=0.3`), không yêu cầu khớp chính xác từ khóa.
- **Bước 3 - Hybrid re-rank theo `provision_type`:** `guard_service.classify_provision_types()` đoán "dạng câu hỏi" (P1-P9). Kết quả truyền vào `search_legal_documents(query_vector, query_provision_types=...)`, cộng thêm `PROVISION_TYPE_BOOST = 0.05` (nhỏ so với thang similarity 0..1) vào điểm của chunk có `provision_type` khớp, sắp lại toàn bộ `results` theo điểm kết hợp này **trước** bước round-robin - vì round-robin chỉ lấy tối đa vài đoạn đầu mỗi văn bản nên phải ưu tiên đúng thứ tự từ trước đó.
- **Bước 4 - Đa dạng hóa kết quả (round-robin, 2 vòng):** vòng 1 lấy xoay vòng tối đa `max_per_doc=3` đoạn/văn bản cho tới khi đủ `max_total_chunks=12` hoặc hết dữ liệu; vòng 2 (nếu vòng 1 chưa lấp đầy 12, tức số văn bản liên quan thực sự ít) bỏ giới hạn `max_per_doc`, lấy tiếp các đoạn còn lại đã ưu tiên sẵn - tránh lãng phí slot khi chỉ có ít văn bản nhưng liên quan sâu (nhiều Khoản).
- **Bước 5 - Đối chiếu quan hệ sửa đổi (đa tầng bằng BFS):** mỗi chunk khi ingest được gắn `amendments_to` (văn bản này sửa Điều/Khoản nào của văn bản khác - AI trích trực tiếp từ câu chữ, VD "sửa đổi Điều 3... Nghị định số 68/2026/NĐ-CP"); `ingest_rag.py:backfill_amended_by()` ghi ngược quan hệ đó thành `amended_by` vào đúng chunk cũ bị sửa (PATCH 1 lần lúc ingest, không phải mỗi câu hỏi). Khi trả lời, `supabase_service._fetch_amending_chunks()` duyệt **BFS nhiều tầng** theo `amended_by`: nếu văn bản B sửa A, rồi văn bản C lại sửa B, hệ thống tự lần sang C ở tầng kế tiếp (không dừng ở 1 tầng), mỗi tầng chỉ tốn đúng 1 request HTTP (gộp bằng `or=(and(...),...)`), giới hạn an toàn `max_hops=5`/`max_total=30`.
- **Bước 6 - Sinh câu trả lời có căn cứ:** đưa các chunk truy xuất được (kèm cảnh báo "đã bị sửa đổi bởi..." nếu có `amended_by`) vào context, LLM bắt buộc trích dẫn Điều/Khoản, không suy diễn ngoài context (nguyên tắc 2.1–2.4 trong `gemini_service.py`, hệ thống chỉ dẫn "chuyên gia tư vấn BHXH").

### 6. Schema metadata mỗi chunk (triển khai trong `ingest_rag.py`)

```json
{
  "type": "Nghị định",
  "provision_type": "P6",
  "law_name": "Nghị định số 68/2026/NĐ-CP",
  "law_number": "68",
  "law_year": 2026,
  "article": "3",
  "section": "1",
  "amendments_to": [],
  "amended_by": [
    {"law_number": "141", "law_year": 2026, "article": "1", "section": "1"}
  ]
}
```
`law_number`/`law_year` được tách bằng regex từ `law_name` đã làm sạch (không nhờ AI đoán số, tránh ảo giác), dùng để so khớp chính xác (`=`) thay vì "ilike" chuỗi con. `amendments_to` được AI điền trực tiếp lúc bóc tách văn bản MỚI (biết ngay nó đang sửa gì, nhờ đọc đúng câu chữ trong văn bản). `amended_by` luôn khởi tạo rỗng lúc ingest và chỉ được `backfill_amended_by()` ghi ngược vào văn bản cũ sau đó.
