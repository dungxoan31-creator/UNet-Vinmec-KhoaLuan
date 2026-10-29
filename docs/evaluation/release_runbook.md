# Runbook demo kỹ thuật RUO

**Trạng thái:** GO có giới hạn cho bài E2E scripted trên localhost; triển khai bệnh viện, thử nghiệm lâm sàng và sử dụng lâm sàng là **BLOCKED / NO-GO**.

## Phạm vi được phép

Chỉ chạy `npm run test:e2e:roundtrip` từ thư mục gốc repository trên workstation phát triển đã cài dependency và trình duyệt do Playwright harness yêu cầu. Harness khởi tạo tiến trình backend riêng trên loopback, SQLite tạm, fixture tổng hợp có SHA-256 allowlist, thông tin đăng nhập kiểm thử và trình duyệt headless. Test kiểm tra synthetic-demo health flags, luồng dữ liệu API/SQLite và cleanup tiến trình/runtime.

Đây là kiểm thử kỹ thuật có thể lặp lại, không phải quy trình vận hành bệnh viện hoặc demo UI tương tác. Không nhập, mở, chụp, tải lên, lưu hoặc in dữ liệu bệnh nhân. Không trỏ trình duyệt hay API tới server bệnh viện. Không khởi động demo bằng `scripts/run_prototype.ps1`: launcher đó không tự bật synthetic-only mode.

## Chạy và lưu bằng chứng

1. Xác nhận đang ở đúng checkout và chỉ có fixture tổng hợp của repository. Không đặt `DATABASE_URL`, không mở CORS và không đổi host sang địa chỉ LAN/public.
2. Chạy:

   ```powershell
   npm run test:e2e:roundtrip
   ```

3. Chỉ ghi **PASS** nếu lệnh kết thúc exit code 0, output cuối có `"status":"PASS"`, không báo lỗi page/runtime, và log xác nhận runtime tạm đã được xóa sau khi tiến trình/listener dừng. Ghi lại ngày giờ, commit/source snapshot, exit code và toàn bộ output vào thư mục evidence của đợt audit. Một lần chạy trước đây không thay cho lần chạy trên source snapshot mới.
4. Test thất bại, cleanup lỗi, cờ health sai, hoặc thiếu dependency đều là **FAIL/BLOCKED**. Dừng bài chạy; giữ stdout/stderr và runtime nếu cleanup không xác nhận được. Không xóa lock marker, không tái sử dụng runtime cũ và không chạy tiếp trên một server có sẵn.

Harness kiểm tra `synthetic_demo_mode=true`, `synthetic_demo_uploads_restricted=true`, `clinical_production_ready=false` và `readiness_scope=TECHNICAL_SERVICE_ONLY`. Cờ này chỉ xác nhận ranh giới demo kỹ thuật; không phải đánh giá an toàn hay hiệu quả lâm sàng.

## Khôi phục sau lỗi và dữ liệu

Ở lượt chạy bình thường, harness đóng browser, dừng đúng tiến trình con, xác nhận listener loopback đã đóng rồi mới xóa runtime tạm. Nếu cleanup không hoàn tất hoặc tiến trình bị dừng cưỡng bức, không tái sử dụng runtime đó. Giữ lại log/runtime để điều tra; chỉ tiếp tục sau khi người vận hành xác minh tiến trình con đã dừng và listener đã đóng. Nếu không xác minh được, giữ trạng thái **NO-GO**.

### Quy trình phục hồi cho lần chạy demo bị lỗi

Quy trình này chỉ áp dụng cho E2E scripted với fixture synthetic ở trên; không phải phục hồi dịch vụ hoặc hồ sơ bệnh nhân.

1. Nếu test trả lỗi nhưng harness xác nhận process đã dừng, listener đã đóng và runtime tạm đã được dọn, giữ nguyên stdout/stderr, phân loại lỗi, sửa nguyên nhân rồi chạy lại từ checkout đã biết. Mỗi lượt chạy phải dùng runtime và port mới do harness cấp.
2. Nếu cleanup báo lỗi hoặc runtime còn tồn tại, đánh dấu lượt chạy **FAIL/NO-GO** và giữ nguyên runtime cùng log. Dùng đúng đường dẫn runtime được ghi trong lỗi/diagnostic; không chọn runtime theo tên hoặc thời gian tạo gần nhất.
3. Nếu có `server-ready.json`, đối chiếu `pid`, `host`, `port` và `runtime` với tiến trình con `tests/serve_isolated_app.py` cùng listener loopback. Chỉ dừng tiến trình khi marker, process command line và PID sở hữu listener đều khớp. Không dừng process chỉ dựa vào số port. Nếu marker thiếu, PID không tồn tại, listener thuộc PID khác hoặc thông tin không khớp, không kill và không xóa; giữ **NO-GO** để điều tra.
4. Sau khi dừng đúng tiến trình, xác minh process đã thoát và port loopback không còn listener. Giữ runtime lỗi làm evidence; lần chạy tiếp theo phải tạo runtime mới. Chỉ người phụ trách QA xóa runtime cũ sau khi đã lưu log và xác nhận nó không còn được process nào sử dụng.
5. Nếu không thể xác minh từng điều kiện trên, dừng demo và chuyển xử lý cho người phụ trách môi trường. Không khôi phục hoặc chép DB tạm cũ vào lượt chạy mới.

Không có quy trình sao lưu/khôi phục dữ liệu lâm sàng được phê duyệt. SQLite ở runbook này là dữ liệu kiểm thử tạm và được xóa sau lượt chạy thành công; không được coi là kho lưu trữ hồ sơ. PostgreSQL, migration/rollback trên môi trường đích, backup/restore, RPO/RTO và khôi phục sau thảm họa đều **BLOCKED / NOT TESTED**. Không tạo bản sao runtime kiểm thử rồi gọi đó là backup vận hành.

## Cổng phát hành

| Phạm vi | Trạng thái | Điều kiện còn thiếu |
|---|---|---|
| E2E kỹ thuật localhost với fixture tổng hợp | **GO có giới hạn** | Chỉ cho bài scripted nêu trên; phải có evidence của source snapshot đang đánh giá |
| Chạy thử nội bộ tại bệnh viện với dữ liệu phi lâm sàng | **BLOCKED** | Môi trường triển khai, an ninh, vận hành và UAT tại site chưa được xác minh |
| Thử nghiệm lâm sàng | **BLOCKED** | Clinical validation độc lập, bộ ca được chuyên gia phê duyệt, patient-level independence, đánh giá nguy cơ và phê duyệt cơ sở/pháp quy |
| Chăm sóc hoặc quyết định trên bệnh nhân | **NO-GO** | Hệ thống RUO chưa được xác nhận/cho phép cho mục đích này |

Xem [đánh giá Go-live hiện hành](../../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) và [status audit](../../artifacts/audit_remediation_2026_10_28/status.md) để biết evidence cùng các blocker mới nhất.
