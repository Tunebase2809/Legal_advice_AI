# Đặc tả Keyphrase — Hệ thống tra cứu kiến thức pháp luật Bảo hiểm xã hội (BHXH)

> Trạng thái: **DRAFT** — khung đặc tả dựng trước khi có văn bản luật chính thức. Mọi số liệu cụ thể (tỷ lệ %, số năm, độ tuổi...) xuất hiện trong tài liệu này cần được **đối chiếu lại với văn bản luật thật** (sẽ nạp vào `documents/`) trước khi dùng làm căn cứ trả lời cho người dùng cuối. Các mục đánh dấu `[cần đối chiếu]` là mức độ tin cậy thấp nhất, chỉ mang tính tham khảo cấu trúc.

## 1. Lĩnh vực và văn bản pháp luật được chọn

- **Lĩnh vực:** Bảo hiểm xã hội (BHXH)
- **Văn bản gốc dự kiến:** Luật Bảo hiểm xã hội số 41/2024/QH15 (hiệu lực 01/07/2025, thay thế Luật BHXH 2014) — sẽ thay bằng văn bản chính thức do người dùng cung cấp.
- **Đối tượng người dùng mục tiêu:** người lao động, người sử dụng lao động, người tham gia BHXH tự nguyện, thân nhân người tham gia.

## 2. Đặc tả thành phần khái niệm (Concept taxonomy)

Mỗi keyphrase được gán vào một trong các nhóm khái niệm sau. Nhóm này dùng để (a) sinh ra danh sách keyphrase có hệ thống, và (b) làm nhãn metadata khi ingest văn bản (gắn cùng `article`/`section` hiện có trong `ingest_rag.py`).

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

## 3. Đặc tả dạng quy định (Provision-type taxonomy)

Đây là "dạng luật" — vai trò tu từ/pháp lý của một đoạn quy định, dùng để phân loại từng chunk (Điều/Khoản) khi ingest, tương tự cách `ingest_rag.py` hiện đang gắn `article`/`section`. Có thể mở rộng schema chunk hiện tại thêm trường `provision_type`.

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

## 4. Bộ keyphrase (mirror cấu trúc `core_keywords` / `context_keywords` trong `guard_service.py`)

Giữ nguyên cơ chế chấm điểm hiện có: mỗi `core_keyword` khớp = 2 điểm, mỗi `context_keyword` khớp = 1 điểm, ngưỡng kích hoạt RAG = tổng điểm ≥ 3 và có ít nhất 1 core keyword. Danh sách đầy đủ nằm trong code tại [guard_service.py](../backend/services/guard_service.py); tóm tắt theo nhóm khái niệm (mục 2) như sau:

**Core keywords (tín hiệu trực tiếp, mạnh):**
bảo hiểm xã hội, bhxh, bhxh bắt buộc, bhxh tự nguyện, sổ bảo hiểm xã hội, mã số bhxh, chế độ ốm đau, chế độ thai sản, chế độ hưu trí, chế độ tử tuất, lương hưu, trợ cấp một lần, trợ cấp hưu trí xã hội, bảo hiểm hưu trí bổ sung, mức đóng bhxh, tỷ lệ đóng bhxh, tiền lương đóng bhxh, thời gian đóng bhxh, rút bhxh một lần, hưởng bhxh một lần, tuổi nghỉ hưu, suy giảm khả năng lao động, trợ cấp tuất, mai táng phí, tham gia bhxh, cơ quan bảo hiểm xã hội, quỹ bảo hiểm xã hội.

**Context keywords (tín hiệu bổ trợ, cần kết hợp):**
người lao động, người sử dụng lao động, hợp đồng lao động, tiền lương, nghỉ việc, nghỉ thai sản, sinh con, nuôi con nuôi, thai sản, tai nạn lao động, bệnh nghề nghiệp, nghỉ hưu, về hưu, trốn đóng, chậm đóng, nợ bảo hiểm, truy thu, hồ sơ hưởng, thủ tục hưởng, giải quyết chế độ, khiếu nại, tố cáo, xử phạt, thanh tra, doanh nghiệp, công ty, viên chức, công chức, lao động tự do, thân nhân, bảo hiểm y tế (liên quan), bảo hiểm thất nghiệp (liên quan), luật, nghị định, thông tư.

## 5. Bộ câu hỏi – trả lời mẫu (seed Q&A set)

Bộ này phục vụ (a) test guard/routing layer, (b) test độ chính xác retrieval, (c) làm few-shot/eval set. **Các câu trả lời có số liệu cụ thể đều cần đối chiếu lại văn bản gốc trước khi dùng thật** — đánh dấu `[cần đối chiếu]`.

| # | Câu hỏi | Nhóm khái niệm | Trả lời mẫu (khung, cần đối chiếu số liệu) |
|---|---|---|---|
| 1 | BHXH bắt buộc và BHXH tự nguyện khác nhau như thế nào? | B | BHXH bắt buộc do Nhà nước tổ chức, người lao động và người sử dụng lao động bắt buộc tham gia theo quy định; BHXH tự nguyện do người dân tự nguyện tham gia, tự chọn mức đóng và phương thức đóng phù hợp thu nhập. `[cần đối chiếu]` phạm vi chế độ cụ thể của từng loại. |
| 2 | Đóng BHXH bao nhiêu năm thì được hưởng lương hưu? | E | Cần đủ số năm đóng BHXH tối thiểu theo quy định hiện hành và đủ tuổi nghỉ hưu. `[cần đối chiếu]` con số năm tối thiểu chính xác trong văn bản đang dùng. |
| 3 | Điều kiện để rút BHXH một lần là gì? | E | Áp dụng cho một số trường hợp cụ thể (ra nước ngoài định cư, mắc bệnh hiểm nghèo, chưa đủ điều kiện hưởng lương hưu sau thời gian nghỉ việc theo quy định...). `[cần đối chiếu]` danh sách đầy đủ và mốc thời gian áp dụng theo văn bản thật. |
| 4 | Mức hưởng chế độ thai sản được tính như thế nào? | F | Tính trên cơ sở mức bình quân tiền lương tháng đóng BHXH của một số tháng liền kề trước khi nghỉ, nhân với số tháng nghỉ theo chế độ. `[cần đối chiếu]` công thức và số tháng cụ thể. |
| 5 | Người sử dụng lao động phải đóng BHXH cho người lao động theo tỷ lệ bao nhiêu? | D | Gồm phần đóng vào các quỹ (hưu trí – tử tuất, ốm đau – thai sản...) theo tỷ lệ % trên tiền lương tháng đóng BHXH. `[cần đối chiếu]` tỷ lệ chính xác theo văn bản/nghị định hướng dẫn hiện hành. |
| 6 | Hồ sơ hưởng chế độ tử tuất gồm những gì? | G | Thường gồm giấy chứng tử/giấy báo tử, tờ khai của thân nhân, sổ BHXH... `[cần đối chiếu]` danh mục hồ sơ đầy đủ theo văn bản. |
| 7 | Chậm đóng BHXH bị xử lý như thế nào? | D, H | Bị tính lãi chậm đóng và có thể bị xử phạt vi phạm hành chính; cơ quan BHXH có quyền yêu cầu truy thu. `[cần đối chiếu]` mức lãi suất/mức phạt cụ thể. |
| 8 | Ai được hưởng trợ cấp hưu trí xã hội? | B, E | Người cao tuổi không có lương hưu hoặc trợ cấp BHXH hằng tháng, đáp ứng điều kiện về độ tuổi theo quy định. `[cần đối chiếu]` mốc tuổi chính xác. |
| 9 | Người lao động nghỉ việc chưa đủ điều kiện hưởng lương hưu thì có được bảo lưu thời gian đóng BHXH không? | E | Có, thời gian đã đóng được bảo lưu để cộng dồn cho lần tham gia sau hoặc tính hưởng chế độ khi đủ điều kiện. |
| 10 | Sổ BHXH dùng để làm gì và ai cấp? | G | Ghi nhận quá trình tham gia và đóng BHXH của người lao động, làm căn cứ giải quyết các chế độ; do cơ quan bảo hiểm xã hội cấp. |

> Khi có văn bản luật thật, nên mở rộng bộ này lên 30–50 cặp câu hỏi – trả lời, rải đều theo 8 nhóm khái niệm (mục 2) và ít nhất 1 câu/nhóm cho mỗi dạng quy định P1–P9 (mục 3), để bộ eval bao phủ cả tra cứu quy định và tra cứu ngữ nghĩa.

## 6. Thiết kế giải pháp tra cứu

### 6.1 Bài toán 1 — Tra cứu quy định (structured/regulation lookup)

- **Đầu vào:** câu hỏi có chỉ rõ hoặc suy ra được thực thể pháp lý cụ thể (VD: "Điều 5 khoản 2 Luật BHXH", "chế độ thai sản").
- **Cơ chế:** query có điều kiện trên metadata đã gắn khi ingest (`law_name`, `law_number`, `law_year`, `article`, `section`, `provision_type` — mục 3), lưu trong bảng `legal_documents` (`database/schema.sql`), cột `metadata` kiểu JSONB nên không cần đổi schema DB khi thêm trường mới.
- **Kết quả:** trả về đúng chunk (Điều/Khoản) tương ứng, kèm trích dẫn nguồn (đã có sẵn cơ chế này trong `gemini_service.py`, phần system rule 2.1).

### 6.2 Bài toán 2 — Tra cứu theo ngữ nghĩa đơn giản (simple semantic search)

- **Bước 1 — Guard/Routing (keyphrase scoring):** dùng bộ keyphrase ở mục 4 để quyết định câu hỏi có thuộc miền BHXH hay không và có cần kích hoạt RAG không (`guard_service.needs_rag`).
- **Bước 2 — Vector retrieval:** dùng pipeline nhúng đã có (`embed_text` — Gemini Embedding, 768 chiều, lưu Supabase pgvector, hàm RPC `match_legal_documents`) để tìm các chunk gần nghĩa nhất với câu hỏi qua cosine similarity, không yêu cầu khớp chính xác từ khóa.
- **Bước 3 — Đối chiếu quan hệ sửa đổi (đã triển khai):** mỗi chunk khi ingest được gắn `amendments_to` (văn bản này sửa Điều/Khoản nào của văn bản khác — AI trích trực tiếp từ câu chữ, VD "sửa đổi Điều 3... Nghị định số 68/2026/NĐ-CP"), sau đó `ingest_rag.py:backfill_amended_by()` ghi ngược quan hệ đó thành `amended_by` vào đúng chunk cũ bị sửa (PATCH 1 lần lúc ingest). Khi trả lời, `supabase_service.search_legal_documents()` chỉ đọc thẳng `amended_by` có sẵn trong metadata và fetch nội dung sửa đổi bằng 1 request duy nhất (`_fetch_amending_chunks`) — không còn phải "ilike" toàn bộ nội dung + so sánh ngày tháng ở mỗi câu hỏi như thiết kế ban đầu.
- **Bước 4 — Hybrid re-rank theo `provision_type` (chưa triển khai, tuỳ chọn nâng cao):** kết hợp điểm keyphrase (mục 4) với điểm similarity vector để ưu tiên chunk vừa gần nghĩa vừa đúng nhóm khái niệm câu hỏi đang hỏi (VD câu hỏi thuộc nhóm E "điều kiện hưởng" thì ưu tiên chunk có `provision_type = P5`). `provision_type` đã được AI gắn sẵn lúc ingest (mục 3), chỉ còn thiếu bước dùng nó để re-rank ở `search_legal_documents`.
- **Bước 5 — Sinh câu trả lời có căn cứ:** đưa các chunk truy xuất được (kèm cảnh báo "đã bị sửa đổi bởi..." nếu có) vào context, LLM bắt buộc trích dẫn Điều/Khoản, không suy diễn ngoài context (nguyên tắc 2.1–2.3 trong `gemini_service.py`, hệ thống chỉ dẫn "chuyên gia tư vấn BHXH").

### 6.3 Schema metadata mỗi chunk (đã triển khai trong `ingest_rag.py`)

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
`amendments_to` được AI điền trực tiếp lúc bóc tách văn bản MỚI (biết ngay nó đang sửa gì); `amended_by` luôn khởi tạo rỗng lúc ingest và chỉ được `backfill_amended_by()` ghi ngược vào văn bản CŨ sau đó — xem chi tiết trong `ingest_rag.py`.

## 7. Việc còn lại / phụ thuộc

1. Văn bản Luật BHXH số 41/2024/QH15 đã có tại `documents/41_2024_QH15.txt` → còn cần chạy `ingest_rag.py --file documents/41_2024_QH15.txt` để nhúng vào Supabase (bảng `legal_documents`, hàm RPC `match_legal_documents` — đã đổi tên khỏi `tax_documents`/`match_tax_documents`).
2. Đối chiếu và cập nhật lại toàn bộ số liệu đánh dấu `[cần đối chiếu]` ở mục 5 sau khi ingest xong.
3. Toàn bộ ứng dụng (backend + frontend) đã được chuyển hẳn sang miền BHXH — không còn giữ song song chatbot thuế. `guard_service.py`, `gemini_service.py` (system prompt), `supabase_service.py`, `app.py` và frontend (`page.tsx`, `ChatView.tsx`) đều chỉ còn phục vụ tra cứu luật BHXH; các module/API/view riêng cho thuế (tax_calculator, tax_schedule_service, DashboardView, LedgerView, TaxScheduleView...) đã bị xóa.
4. Bước 4 ở mục 6.2 (hybrid re-rank theo `provision_type`) chưa triển khai — có thể làm thêm nếu muốn nâng cao độ chính xác truy xuất theo đúng dạng quy định câu hỏi đang hỏi.
