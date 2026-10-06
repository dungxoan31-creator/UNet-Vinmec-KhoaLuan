# KIẾN TRÚC & DANH MỤC VAI TRÒ DỰ ÁN (PROJECT STRUCTURE & ROLE MANIFEST)
> **Dự án**: Hệ thống Hỗ trợ Chẩn đoán & Phân đoạn Siêu âm Buồng trứng Human-in-the-Loop (Khóa luận Tốt nghiệp MIS / ITBA / AI - NEU)  
> **Cơ sở dữ liệu lâm sàng**: Bệnh viện Đa khoa Quốc tế Vinmec Times City  
> **Cập nhật gần nhất**: 2026-10-06 | Phiên bản kiến trúc: 1.2.0

---

## 1. NGUYÊN TẮC CỐT LÕI (CORE INVARIANTS)
1. **Single Source of Truth**: Mỗi cấu hình, tập dữ liệu chia mẫu (split) và mô hình production chỉ có một vị trí khai báo chính thức duy nhất.
2. **Bảo toàn Dữ liệu Lâm sàng**: Thư mục `dataset/2d` và `dataset/3d` là tài sản nghiên cứu gốc, luôn ở chế độ chỉ đọc (read-only) trong quá trình huấn luyện và đánh giá.
3. **Phân định Rõ ràng Runtime vs Source**: Thư mục `data/` chỉ dùng cho runtime (file tạm bác sĩ upload và báo cáo PDF xuất tự động), không chứa mã nguồn.
4. **Kiểm soát Trọng số Mô hình**: File `evaluation/selected_model.json` chỉ định mô hình chính thức thông qua băm SHA-256 (`checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth`).

---

## 2. SƠ ĐỒ CÂY THƯ MỤC CHUẨN HÓA (STANDARDIZED DIRECTORY TREE)

```
UNet-Vinmec-KhoaLuan/
├── .gitignore                   # Cấu hình bỏ qua cache, file đệm, weights lớn, uploads
├── AGENTS.md                    # Bộ tri thức chung & quy tắc làm việc Master (ECC, Zero-Hallucination)
├── Dockerfile                   # Đặc tả container hóa ứng dụng CDSS
├── docker-compose.yml           # Khởi chạy dịch vụ FastAPI Backend và Nginx
├── MACHINE_RESOURCES.md         # Báo cáo định lượng tài nguyên phần cứng (RAM, VRAM, Disk)
├── MODEL_CARD.md                # Thẻ mô hình AI (Model Card) chuẩn học thuật
├── nginx.conf                   # Cấu hình Reverse Proxy Nginx cho môi trường triển khai
├── ovarian_ai.db                # Cơ sở dữ liệu SQLite cục bộ (lưu trữ ca khám, nhật ký HITL)
├── package.json                 # Khai báo Playwright phục vụ End-to-End browser test
├── PROJECT_STRUCTURE.md         # Tài liệu này: Danh mục vai trò toàn bộ tệp tin trong dự án
├── pyproject.toml               # Cấu hình công cụ Python (Ruff, Pytest path)
├── README.md                    # Hướng dẫn tổng quan cài đặt và vận hành hệ thống
├── requirements.txt             # Danh sách thư viện Python phụ thuộc
├── TECH_STACK.md                # Báo cáo kiến trúc công nghệ & thư viện sử dụng
│
├── ai_training/                 # MODULE HUẤN LUYỆN MÔ HÌNH AI (PYTORCH)
│   ├── dataset_loader.py        # PyTorch Dataset & DataLoader nạp ảnh siêu âm kèm tiền xử lý
│   ├── finetune_2d_unet.py      # Pipeline tinh chỉnh (fine-tune) U-Net trên dữ liệu 2D
│   ├── metrics_clinical.py      # Tính toán các chỉ số lâm sàng (Dice, IoU, Recall, Precision)
│   ├── splits/                  # Thư mục chứa các file phân chia tập train/val/test
│   │   ├── unified_vinmec_clean_2026-10-06/ # Tập split chính thức hiện tại (Train 663, Val 541, Test 402)
│   │   ├── kltn_ground_truth_307.csv         # Bộ ground truth chuẩn hóa 307 ca
│   │   ├── train.csv, val.csv, test.csv      # Phân chia mẫu theo cấu trúc chuẩn
│   │   └── archive/             # Lưu trữ các file split thử nghiệm qua các mốc cũ
│   ├── train_baseline_unet.py   # Huấn luyện mô hình Standard U-Net Baseline
│   ├── train_full_unet.py       # Huấn luyện U-Net trên toàn bộ tập dữ liệu tổng hợp
│   ├── train_standard_unet_gray_imagenet_norm.py # Thử nghiệm chuẩn hóa ImageNet
│   └── train_unetplusplus_resnet34.py            # Huấn luyện biến thể U-Net++ (Backbone ResNet-34)
│
├── backend/                     # MODULE MÁY CHỦ DỊCH VỤ CDSS (FASTAPI)
│   ├── app/
│   │   ├── config.py            # Nạp cấu hình, đường dẫn storage và xác thực SHA-256 mô hình
│   │   ├── main.py              # Điểm khởi chạy FastAPI, cấu hình CORS và định tuyến
│   │   └── routers/             # Các API Endpoint RESTful phân theo phân hệ nghiệp vụ
│   │       ├── admin.py         # Quản trị hệ thống và cấu hình
│   │       ├── auth.py          # Xác thực bác sĩ / người dùng lâm sàng
│   │       ├── cases.py         # Quản lý danh sách ca bệnh và ảnh siêu âm
│   │       ├── evaluation.py    # Truy vấn kết quả đánh giá thực nghiệm
│   │       ├── health.py        # Endpoint kiểm tra trạng thái dịch vụ (Health check)
│   │       ├── inference.py     # Endpoint suy luận AI (phân đoạn tổn thương buồng trứng)
│   │       ├── reviews.py       # Endpoint lưu trữ phản hồi Human-in-the-Loop từ bác sĩ
│   │       └── v1_endpoints.py  # Hợp nhất các router phiên bản v1
│   ├── core/
│   │   └── image_utils.py       # Xử lý đồ họa y tế (CLAHE, Letterbox, giải mã ảnh)
│   ├── db/
│   │   └── database.py          # Khởi tạo SQLAlchemy Session và kết nối SQLite
│   ├── models/                  # Định nghĩa cấu trúc mạng nơ-ron và bảng dữ liệu DB
│   │   ├── attention_unet.py    # Kiến trúc mạng Attention U-Net
│   │   ├── losses.py            # Hàm mất mát Combo Loss (Dice Loss + BCE Loss)
│   │   ├── metrics.py           # Metric tính toán trong quá trình huấn luyện
│   │   └── unet.py              # Kiến trúc Standard U-Net chuẩn
│   ├── schemas/
│   │   └── schemas.py           # Pydantic Schemas kiểm thực dữ liệu vào/ra (Contract)
│   └── services/                # Các dịch vụ xử lý nghiệp vụ CDSS
│       ├── backup_service.py    # Sao lưu cơ sở dữ liệu định kỳ
│       ├── inference_engine.py  # Động cơ suy luận chạy mô hình PyTorch
│       ├── model_service.py     # Registry quản lý tải và giải phóng trọng số mô hình
│       ├── morphology_extractor.py # Đo kích thước Caliper (d1, d2), chu vi, diện tích theo ISUOG
│       ├── preprocessor.py      # Tiền xử lý ảnh (Letterbox 512x512, CLAHE 2.0, chia tỷ lệ)
│       ├── report_generator.py  # Sinh phiếu kết quả siêu âm chuyên nghiệp
│       └── review_validation.py # Xác thực dữ liệu hiệu chỉnh đường viền từ bác sĩ
│
├── frontend/                    # GIAO DIỆN WEB WORKSTATION LÂM SÀNG (HTML5 / CANVAS)
│   ├── index.html               # Trang làm việc chính của bác sĩ chẩn đoán hình ảnh
│   ├── css/style.css            # Giao diện y tế Dark Mode tối ưu cho phòng đọc ảnh
│   └── js/
│       ├── app.js               # Điểm khởi tạo và điều phối các module Frontend
│       └── modules/             # Các module xử lý logic phía client
│           ├── api.js           # Giao tiếp HTTP với FastAPI Backend
│           ├── canvas.js        # Canvas tương tác đa lớp (ảnh gốc, overlay, công cụ vẽ/tẩy)
│           ├── cases.js         # Quản lý danh sách ca khám và hiển thị thumbnail
│           ├── hitl.js          # Xử lý quy trình phản hồi Human-in-the-Loop (Bác sĩ duyệt/sửa)
│           ├── morphology.js    # Trực quan hóa đo đạc hình thái tổn thương
│           └── ui.js            # Điều khiển giao diện người dùng (nút bấm, thanh trượt độ mờ)
│
├── dataset/                     # DỮ LIỆU SIÊU ÂM GỐC (CHỈ ĐỌC - READ ONLY)
│   ├── 2d/                      # Tập ảnh siêu âm 2D B-mode
│   │   ├── images/              # 1,469 tệp ảnh siêu âm gốc
│   │   └── masks/               # Mặt nạ nhãn phân đoạn tổn thương (Binary PNG)
│   ├── 3d/                      # Tập ảnh siêu âm 3D bổ trợ
│   │   ├── images/              # 170 tệp ảnh siêu âm 3D
│   │   └── masks/               # 170 tệp mặt nạ tổn thương 3D
│   └── index.csv                # Chỉ mục liên kết toàn bộ mẫu ảnh, nhãn và nguồn gốc dữ liệu
│
├── metadata/                    # METADATA BỘ CHUẨN VÀ TẬP PHÂN CHIA (SINGLE SOURCE OF TRUTH)
│   ├── kltn_ground_truth_307.csv # Tập Ground Truth 307 ca được bác sĩ thẩm định chính thức
│   ├── train.csv                # Tập huấn luyện (215 ca)
│   ├── val.csv                  # Tập thẩm định (46 ca)
│   ├── test.csv                 # Tập kiểm thử độc lập (46 ca)
│   └── thesis_exports/          # Bản sao lưu tên tiếng Việt phục vụ nộp báo cáo Khóa luận
│       ├── Tap_Huan_Luyen_Train_215.csv
│       ├── Tap_Tham_Dinh_Val_46.csv
│       └── Tap_Kiem_Thu_Test_46.csv
│
├── checkpoints/                 # TRỌNG SỐ MÔ HÌNH HỌC SÂU (MODEL WEIGHTS)
│   ├── unified_vinmec_refine_2026-10-06/ # MÔ HÌNH PRODUCTION CHÍNH THỨC HIỆN TẠI
│   │   └── lr_3e-04/baseline_unet_best.pth # Checkpoint chính thức phục vụ suy luận
│   ├── baseline_unet_best.pth   # Trọng số Standard U-Net Baseline gốc
│   ├── unetplusplus_resnet34_2026-10-06/ # Checkpoint mô hình đối chuẩn U-Net++
│   ├── retrain_2d_2026-10-03_stable/     # Checkpoint chuẩn kiểm định tính ổn định
│   └── archive_milestone_1/     # Lưu trữ trọng số các mốc nghiên cứu trước
│
├── evaluation/                  # KẾT QUẢ ĐÁNH GIÁ THỰC NGHIỆM LÂM SÀNG
│   ├── selected_model.json      # Bản kê khai mô hình chính thức kèm mã băm SHA-256
│   ├── milestone_3_2026-10-06/  # Kết quả đánh giá độc lập của Mốc 3 (Test Set)
│   ├── milestone_3_audit_2026-10-06/ # Bằng chứng kiểm toán số liệu và đối chuẩn
│   ├── unified_vinmec_2026-10-06/    # Báo cáo đánh giá tập hợp dữ liệu Vinmec hợp nhất
│   ├── baseline_visualizations/      # Ảnh minh họa phân đoạn đối chứng
│   └── archive/                 # Kho lưu trữ các báo cáo và kết quả thực nghiệm M1 & M2
│
├── reports/                     # BÁO CÁO KIỂM TOÁN VÀ LÀM SẠCH DỮ LIỆU
│   ├── dataset_deduplication_report.csv       # Chi tiết khử trùng lặp dữ liệu
│   ├── dataset_deduplication_summary.json     # Tổng kết tỷ lệ trùng lặp
│   ├── dataset_validation.csv                 # Tóm tắt kết quả kiểm thực bộ dữ liệu
│   └── dataset_validation_split_conflicts.csv # Đối soát rò rỉ dữ liệu giữa các tập
│
├── scripts/                     # CÔNG CỤ XỬ LÝ DỮ LIỆU, ĐÁNH GIÁ & TẠO BÁO CÁO
│   ├── build_unified_vinmec_splits.py         # Xây dựng phân chia tập dữ liệu hợp nhất
│   ├── build_vinmec_clean_dataset.py          # Chuẩn hóa cấu trúc thư mục dữ liệu sạch
│   ├── refine_unified_vinmec_unet.py          # Tinh chỉnh U-Net và chọn mô hình tốt nhất
│   ├── evaluate_unified_vinmec.py             # Đánh giá độc lập trên tập Test
│   ├── render_unified_vinmec_error_analysis.py # Xuất bảng phân tích ca lỗi lâm sàng
│   ├── validate_vinmec_datasets.py            # Kiểm toán toàn vẹn nhãn và ảnh
│   ├── verify_milestone3_validation.py        # Thẩm định kết quả Mốc 3
│   ├── audit_milestone3_evidence.py           # Khóa bằng chứng kiểm toán Mốc 3
│   ├── finalize_milestone3_audit.py           # Hoàn tất văn bản kiểm toán
│   ├── export_milestone_1_report.py           # Xuất báo cáo Mốc 1 ra định dạng Word (.docx)
│   ├── export_milestone2_report.py            # Xuất báo cáo Mốc 2 ra định dạng Word (.docx)
│   └── generate_humanized_docx_report.py      # Sinh báo cáo tiến độ chuẩn học thuật
│
├── docs/                        # TÀI LIỆU KHÓA LUẬN & ĐẶC TẢ HỆ THỐNG
│   ├── reports/                 # Các báo cáo tiến độ Mốc 1, Mốc 2, Mốc 3 (Word & Markdown)
│   └── superpowers/             # Kế hoạch phát triển, đặc tả yêu cầu kỹ thuật & ITBA
│       ├── plans/               # Các bản kế hoạch thực thi từng giai đoạn
│       └── specs/               # Đặc tả ca sử dụng, luồng nghiệp vụ và giao diện CDSS
│
├── templates/                   # MẪU TÀI LIỆU XUẤT BẢN
│   └── medical_report/          # Mẫu HTML/CSS sinh phiếu kết quả siêu âm cho bác sĩ
│
├── tests/                       # BỘ KIỂM THỬ TỰ ĐỘNG (PYTEST & PLAYWRIGHT)
│   ├── browser_hitl_smoke.js    # Kiểm thử luồng thao tác bác sĩ trên Canvas bằng trình duyệt
│   ├── test_hitl_contract.py    # Kiểm thử hợp đồng API Human-in-the-Loop
│   ├── test_model_selection.py  # Kiểm thử cơ chế chọn mô hình qua SHA-256
│   ├── test_unet_refinement.py  # Kiểm thử quy trình tinh chỉnh mạng U-Net
│   └── test_vinmec_pipeline.py  # Kiểm thử tích hợp toàn bộ pipeline
│
└── data/                        # THƯ MỤC RUNTIME CỤC BỘ (GIỮ BỞI .GITKEEP)
    ├── uploads/                 # Ảnh tạm bác sĩ tải lên khi dùng phần mềm
    └── reports/                 # Phiếu siêu âm sinh ra trong phiên làm việc
```

---

## 3. BẢNG PHÂN BỔ VAI TRÒ CHI TIẾT (ROLE MATRIX)

| Tên Module / Tệp | Vai trò Cụ thể (Purpose) | Phân loại Trạng thái |
|---|---|---|
| `backend/app/main.py` | Cổng REST API chính điều phối toàn bộ dịch vụ CDSS | `[Active Production]` |
| `backend/app/config.py` | Nạp cấu hình, quản lý đường dẫn và bảo mật băm SHA-256 của weights | `[Active Production]` |
| `backend/services/morphology_extractor.py` | Trích xuất thông số hình thái (d1, d2, diện tích) theo chuẩn y khoa ISUOG | `[Active Production]` |
| `backend/services/inference_engine.py` | Chạy mạng PyTorch U-Net với cơ chế tiền xử lý Letterbox và CLAHE | `[Active Production]` |
| `frontend/js/modules/canvas.js` | Canvas đa lớp hiển thị ảnh siêu âm và công cụ vẽ chỉnh viền Human-in-the-Loop | `[Active Production]` |
| `dataset/2d/images/` & `dataset/2d/masks/` | Tập dữ liệu siêu âm 2D gốc Vinmec phục vụ huấn luyện và kiểm thử | `[Read-Only Source]` |
| `metadata/kltn_ground_truth_307.csv` | Bảng Ground Truth 307 ca được bác sĩ Vinmec xác thực chính thức | `[Single Source of Truth]` |
| `checkpoints/unified_vinmec_refine_2026-10-06/...` | Trọng số mô hình Standard U-Net tốt nhất (Val Dice ~0.6724) đang phục vụ API | `[Active Production Checkpoint]` |
| `evaluation/selected_model.json` | Manifest chỉ định mô hình chính thức cho hệ thống | `[Active Production Manifest]` |
| `evaluation/archive/` | Kho lưu trữ toàn bộ dữ liệu thực nghiệm lịch sử M1 & M2 (tránh phình thư mục) | `[Historical Archive]` |
| `metadata/thesis_exports/` | Lưu trữ file CSV tên tiếng Việt phục vụ phụ lục báo cáo khóa luận | `[Thesis Reference]` |
| `data/uploads/` & `data/reports/` | Bộ nhớ đệm lưu trữ ảnh và báo cáo sinh trong lúc bác sĩ tương tác hệ thống | `[Runtime Data]` |

---

## 4. QUY ƯỚC BẢO TRÌ & LÀM SẠCH (HYGIENE GUIDELINES)
1. **Không tạo script phân mảnh ở thư mục gốc**: Mọi script mới phải đặt vào `scripts/` và có docstring giải thích mục đích rõ ràng.
2. **Khóa băm SHA-256 khi đổi mô hình**: Bất kỳ cập nhật checkpoint nào đều phải ghi nhận lại vào `evaluation/selected_model.json` kèm mã băm SHA-256.
3. **Thư mục Archive**: Dữ liệu thực nghiệm qua các mốc cũ không xóa bỏ mà di chuyển vào thư mục `archive/` tương ứng để bảo toàn khả năng tái hiện thực nghiệm (Reproducibility).
