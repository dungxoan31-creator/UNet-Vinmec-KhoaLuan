# BÁO CÁO CẤU TRÚC PHÂN CHIA BỘ DỮ LIỆU KHÓA LUẬN TỐT NGHIỆP (KLTN)
> **Đề tài**: Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop.  
> **Sinh viên thực hiện**: Nguyễn Hữu Dũng — MSV: 11235559 — Lớp: HTTTQL K65, NEU.  
> **Giảng viên hướng dẫn**: ThS. Trần Thanh Hải.  
> **Đơn vị cung cấp dữ liệu lâm sàng**: Bệnh viện Đa khoa Quốc tế Vinmec Times City.  
> **Căn cứ pháp lý & học thuật**: Đề cương sơ bộ KLTN (Bảng 1 & Mục 6.2).

---

## 1. TỔNG QUAN PHÂN VÙNG DỮ LIỆU THEO ĐỀ CƯƠNG SƠ BỘ (BẢNG 1)

| Phân nhóm dữ liệu | Số lượng ảnh | Tỷ lệ (%) | Số bệnh nhân (PID) | Số lượng Empty Mask (Đcontrol âm tính) | Mục đích sử dụng lâm sàng & AI |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Tổng kho ảnh thu nhận** | **1.387** | **100,0%** | — | **48** | Tổng thể dữ liệu hình ảnh siêu âm buồng trứng tiếp nhận từ Vinmec Times City |
| **Ảnh có mặt nạ ban đầu** | **417** | **30,1%** | — | **48** | Toàn bộ ảnh đã được gán nhãn sơ bộ hoặc mặt nạ đối chứng âm tính |
| **1. Tập Ground Truth chuẩn hóa** | **307** | **22,1%** *(73,6% tập mask)* | **185** | **35** *(11,4%)* | Bác sĩ chuyên khoa chẩn đoán hình ảnh Vinmec Times City đã nghiệm thu và xác thực 100% |
| **2. Tập chờ duyệt (Pending Review)** | **110** | **7,9%** *(26,4% tập mask)* | **110** | **13** *(11,8%)* | Lưu riêng phục vụ quy trình Human-in-the-Loop (Bác sĩ review/edit/confirm trên Web GUI) |
| **3. Tập ảnh thô chưa gán nhãn (Raw)** | **970** | **69,9%** | — | — | Dữ liệu thô dùng cho bài toán mở rộng Semi-Supervised Learning & Active Learning tương lai |

---

## 2. CHI TIẾT PHÂN CHIA PATIENT-LEVEL ZERO-LEAKAGE TẬP GROUND TRUTH (307 ẢNH)

Theo chuẩn quốc tế về trí tuệ nhân tạo trong y tế (STARD-AI / CLAIM) và Mục 6.2 của Đề cương sơ bộ:
- Việc phân chia bắt buộc thực hiện ở **cấp độ Bệnh nhân (Patient-Level Partitioning)** thay vì cấp độ từng ảnh đơn lẻ.
- Tuyệt đối **không có rò rỉ dữ liệu (Strict Zero Leakage)**: Bệnh nhân đã xuất hiện ở tập Train sẽ không bao giờ xuất hiện ở tập Validation hoặc Test.

### Bảng phân bổ chi tiết tỷ lệ 70% - 15% - 15%:

| Tập dữ liệu | Số bệnh nhân | Tỷ lệ BN | Số lượng ảnh | Tỷ lệ ảnh | Số Empty Mask | File phân vùng lưu trữ |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Huấn luyện (Train)** | **130** | 70,27% | **215** | **70,03%** | 25 *(11,6%)* | `ai_training/splits/train.csv` <br> `ai_training/splits/kltn_train_307.csv` |
| **Thẩm định (Validation)**| **27** | 14,59% | **46** | **14,98%** | 5 *(10,9%)* | `ai_training/splits/val.csv` <br> `ai_training/splits/kltn_val_307.csv` |
| **Kiểm thử độc lập (Test)**| **28** | 15,14% | **46** | **14,98%** | 5 *(10,9%)* | `ai_training/splits/test.csv` <br> `ai_training/splits/kltn_test_307.csv` |
| **TỔNG CỘNG GROUND TRUTH**| **185** | **100%** | **307** | **100%** | **35** *(11,4%)* | `ai_training/splits/kltn_ground_truth_307.csv` |

---

## 3. Ý NGHĨA LÂM SÀNG CỦA MẶT NẠ RỖNG (EMPTY MASK CONTROLS)

Trong chẩn đoán hình ảnh siêu âm phụ khoa thực tế, buồng trứng bình thường không chứa u nang hay tổn thương ác tính. Nếu mô hình phân đoạn AI chỉ được học trên 100% ảnh có tổn thương, mô hình sẽ mắc hiện tượng **Over-segmentation / False Positive Bias** (cố gắng tìm và vẽ tổn thương ngay cả trên buồng trứng hoàn toàn khỏe mạnh).

- **Ground Truth 307**: Tích hợp đúng **35 ảnh đối chứng âm tính** (11,4%), gồm 25 ảnh trong tập Train, 5 ảnh trong tập Val và 5 ảnh trong tập Test.
- **Tập chờ duyệt (110)**: Chứa **13 ảnh đối chứng âm tính** (11,8%).
- **Toàn bộ 48 mặt nạ rỗng nhị phân ($512 \times 512$, pixel = 0)** đã được tạo chuẩn tại:
  `dataset/vinmec_ovarian/empty_masks/empty_mask_001.png` đến `empty_mask_048.png`.

---

## 4. TÍNH TOÀN VẸN VÀ KHẢ NĂNG KIỂM CHỨNG TỰ ĐỘNG (VERIFICATION)

Toàn bộ cấu trúc phân chia đã được kiểm chứng tự động bằng bộ test suite:
- `tests/test_dataset_splits_leakage.py`: 5/5 tests PASS xanh (kiểm tra rò rỉ bệnh nhân, rò rỉ ảnh, kiểm tra số lượng bản ghi Bảng 1, kiểm tra file tồn tại trên đĩa).
- `tests/test_milestone_1_audit.py`: 16/16 tests PASS xanh (kiểm tra đầy đủ quy trình 16 mục Mốc 1 Đề cương sơ bộ).
- Toàn bộ test suite hệ thống: **89/89 tests PASS 100%**.
