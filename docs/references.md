# Nguồn tham chiếu lâm sàng, usability và bảo vệ dữ liệu

Ngày đối chiếu: **2026-10-25**. `[VERIFIED]` nghĩa là nội dung/định danh tài liệu đã được kiểm tra trên trang chính thức hoặc bản gốc được lập chỉ mục. Đây không phải tuyên bố tuân thủ pháp lý hay chứng nhận y khoa của phần mềm.

## Siêu âm phần phụ và phân loại

1. **[VERIFIED] ACR O-RADS US v2022 — Assessment Categories.** [PDF từ ACR](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf). Nguồn mô tả phân loại theo hình thái; nêu nang noãn sinh lý đến 3 cm và các descriptor phục vụ risk assessment. Cần áp dụng đúng phạm vi và đầy đủ dữ liệu; không suy O-RADS chỉ từ mask.
2. **[VERIFIED] ACR O-RADS — Governing Concepts.** [PDF từ ACR](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/O-RADS--US-v2022-Governing-Concepts-only.pdf) và [Applicability Criteria and Management](https://radssupport.acr.org/support/solutions/articles/11000124649-applicability-criteria-and-management). O-RADS 0 liên quan khảo sát kỹ thuật chưa đủ để đánh giá; không dùng chỉ vì bác sĩ chưa chắc chẩn đoán.
3. **[VERIFIED] IOTA Simple Rules, prospective validation.** Timmerman et al., *BMJ* 2010;341:c6839. [Bài gốc](https://www.bmj.com/content/341/bmj.c6839), [PMID 21156740](https://pubmed.ncbi.nlm.nih.gov/21156740/). Bài báo nêu 5 dấu hiệu B, 5 dấu hiệu M và trường hợp không kết luận được khi có cả nhóm hoặc không có nhóm nào. Không được rút gọn trạng thái inconclusive thành chẩn đoán.
4. **[PARTIALLY VERIFIED] IOTA ADNEX.** Van Calster et al., *BMJ* 2014;349:g5920. [Bài gốc](https://www.bmj.com/content/349/bmj.g5920), [PMID 25320247](https://pubmed.ncbi.nlm.nih.gov/25320247/). Định danh bài và DOI đã đối chiếu qua BMJ/PubMed; công thức, hệ số, ngưỡng và yêu cầu đầu vào chưa được kiểm toán độc lập trong codebase này.
5. **[VERIFIED] IOTA standardized terminology — updated consensus notice.** [ISUOG, 8 Apr 2026](https://www.isuog.org/resource/updated-consensus-opinion-on-the-terms-definitions-and-measurements-to-describe-the-sonographic-features-of-adnexal-tumors.html). Trang chính thức nêu bộ thuật ngữ, định nghĩa và phép đo IOTA là nền tảng cho benign descriptors, ADNEX và phân tầng nguy cơ. Nội dung lexicon phải được chuyên gia xác nhận trước khi dùng để suy luận trong sản phẩm.
6. **[PARTIALLY VERIFIED] Đo thể tích buồng trứng.** [AIUM Practice Parameter for the Performance of Ultrasound of the Female Pelvis, 2024 revision](https://onlinelibrary.wiley.com/doi/10.1002/jum.16556) nêu đo buồng trứng ở ba chiều và tính thể tích khi cần. Công thức ellipsoid `0.523 × d1 × d2 × d3` cần được chủ nhiệm chuyên môn xác nhận cùng quy ước mặt phẳng, đơn vị và cách đo trong sản phẩm.

## Usability và accessibility

7. **[VERIFIED] WCAG 2.2.** [W3C Recommendation](https://www.w3.org/TR/WCAG22/). Dùng làm tiêu chí thiết kế/kiểm thử accessibility. Chưa có đánh giá chứng nhận conformance cho toàn bộ ứng dụng.

## Bảo vệ dữ liệu

8. **[VERIFIED] Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.** [Văn bản trên cổng Bộ Thông tin và Truyền thông](https://mst.gov.vn/van-ban-phap-luat/24993.htm), [Cổng Chính phủ](https://chinhphu.vn/default.aspx?docid=207759&pageid=27160). Trích dẫn để lập yêu cầu và câu hỏi cho bên kiểm soát dữ liệu; tài liệu này không đưa ra kết luận pháp lý về mức tuân thủ của prototype.
9. **[VERIFIED] HIPAA Security Rule.** [HHS Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html). Tham chiếu về bảo mật ePHI khi áp dụng cho tổ chức thuộc phạm vi điều chỉnh; không đồng nghĩa prototype tuân thủ HIPAA hoặc HIPAA là luật mặc định tại Việt Nam.

## Chính sách dự án có liên quan

- Chính sách dự án giữ ngưỡng mô tả nang noãn sinh lý `<30 mm`; ACR v2022 ghi `≤3 cm`. Biên đúng 30 mm cần chuyên gia xác nhận trước khi thống nhất cách hiển thị. Không đổi ngưỡng dự án chỉ dựa vào suy diễn.
- Bất thường hình thái không đồng nghĩa ác tính. Segmentation là mask hỗ trợ bác sĩ, không phải kết luận.
- Nguồn ảnh test tự động chỉ được là fixture tổng hợp; không đọc ảnh từ `dataset/` hoặc `ai_training/` trong browser/API E2E.
