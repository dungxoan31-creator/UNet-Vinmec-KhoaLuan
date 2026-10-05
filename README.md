# Ovarian Ultrasound Segmentation Research Prototype

Đề tài khóa luận của Nguyễn Hữu Dũng (MSV 11235559): hệ thống hỗ trợ phân đoạn vùng nghi ngờ tổn thương trên ảnh siêu âm buồng trứng, có bước chuyên viên rà soát và chỉnh sửa (Human-in-the-Loop, HITL).

Đây là prototype nghiên cứu. Kết quả phân đoạn hỗ trợ rà soát ảnh; hệ thống không đưa ra chẩn đoán lâm sàng và không thay thế quyết định của chuyên viên y tế.

## Phạm vi và dữ liệu

### Mốc 1: bộ tham chiếu 307 ảnh

- Chia ảnh: Train 215, Validation 46, Test 46 (`ai_training/splits/archive_milestone_1/`).
- 185 nhãn nhóm ẩn danh được ghi trong manifest; danh tính bệnh nhân nguồn không được xác minh. Vì vậy, không kết luận đây là patient-level split.
- Có 35 bản ghi có mask rỗng dẫn xuất. Chúng có provenance ở `dataset/vinmec_ovarian/empty_masks/PROVENANCE.json`, là artifact tương thích pipeline, không phải nhãn âm tính lâm sàng. Audit ghi nhận mask nguồn của các ảnh này có pixel dương.
- Các segmentation metrics lịch sử của Mốc 1 nằm trong báo cáo Mốc 1 và `evaluation/baseline_test_metrics.json`. Không diễn giải chúng thành Diagnostic Accuracy.

### Checkpoint tích hợp hiện hành

- Checkpoint SHA-256 `5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e`, được trỏ qua `checkpoints/baseline_unet_best.pth`.
- Được chọn bằng Validation của lượt huấn luyện riêng (123 ảnh). Test summary của lượt đó dùng 382 ảnh và threshold 0.5; xem `evaluation/selected_model.json` và `evaluation/retrain_2d_2026-10-03/test_summary.json`.
- Lượt huấn luyện riêng dùng split 697/123/382. Test đã được dùng trong các lượt đánh giá trước đó; kết quả được ghi với giới hạn này, không xem là lần đánh giá mù đầu tiên.
- Checkpoint này là mô hình tích hợp prototype, không phải kết quả huấn luyện trên bộ Mốc 1. Mốc 2 không tạo segmentation metrics mới cho checkpoint này trên Test Mốc 1.

Dice, IoU, Precision, Recall và Specificity là segmentation metrics ở mức pixel. Chúng không đo độ chính xác chẩn đoán lâm sàng. Không gán phân loại bệnh học cho vùng được phân đoạn khi chưa có xác nhận chuyên môn.

## Luồng ứng dụng

`Upload ảnh R/L → tiền xử lý grayscale và Letterbox 512×512 → U-Net inference → Original/Mask/Overlay → Review/Edit → Confirm/Save`

Frontend dùng HTML, CSS và JavaScript Canvas; backend dùng FastAPI, SQLAlchemy/SQLite và PyTorch. Prototype hỗ trợ Brush, Eraser, điều chỉnh kích thước nét, Undo/Redo và lưu bản mask rà soát. Trạng thái Confirm trong ứng dụng ghi nhận thao tác; tự nó không xác nhận mask thành Ground Truth chuyên môn.

## Cài đặt và chạy

Yêu cầu Python 3.10 trở lên. Trên Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Chạy API từ thư mục gốc:

```powershell
$env:PYTHONPATH = "."
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/`. Checkpoint được chọn và kiểm tra hash qua `evaluation/selected_model.json`; API từ chối nạp nếu SHA không khớp.

## Kiểm thử và lint

```powershell
$env:PYTHONPATH = "."
pytest -q
ruff check .
```

Browser smoke test hiện có: `tests/browser_hitl_smoke.js`. Báo cáo smoke hiện lưu tại `evaluation/milestone_2_m1_scope/browser_smoke_2026-10-04.json`; nó chứng minh kịch bản đã ghi trong artifact, không thay thế usability study hoặc xác nhận lâm sàng.

## Cấu trúc chính

```text
backend/                 FastAPI routes, schemas, database, inference services
ai_training/             Dataset loader, training code, split snapshots
checkpoints/             Model weights and training metadata
dataset/                 Research image data and provenance
evaluation/              Metric summaries, latency and smoke-test evidence
frontend/                HTML, CSS and Canvas HITL interface
docs/reports/            Milestone and technical reports
scripts/                 Audit, preprocessing and report utilities
tests/                   Python tests and browser smoke test
```

## Tài liệu liên quan

- Báo cáo Mốc 1 và Mốc 2: `docs/reports/`
- Trạng thái dự án: `docs/project_status.json`
- Model card: `MODEL_CARD.md`
- Stack kỹ thuật: `TECH_STACK.md`
