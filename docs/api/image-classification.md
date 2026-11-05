# Phân loại ảnh nghiên cứu

POST `/api/predict/{image_id}` chạy thêm MMOTU ResNet34 8-class trên ảnh nguồn. Kết quả trong `ai_diagnosis` được lưu trong prediction extras, trả lại khi replay và khi GET `/api/cases/{study_id}`. Không cần migration DB.

Viewer hiển thị mục “Phân loại ảnh AI · Nghiên cứu RUO”, nhãn đề xuất và ba lớp có điểm cao nhất. Ảnh cũ cần chạy phân tích AI lại để tạo kết quả. Không tự ghi kết quả vào chẩn đoán, O-RADS hoặc review của bác sĩ.

Model cố định: trial_02_balanced_256_finetune_lr5e5, checkpoint best SHA-256 `35737b75c89b983a5b51846aba45aebea3144b8d09f70f1e3cfc1f08b1118a92`. Nạp snapshot được hash trước khi deserialize, strict state dict, CPU, lazy load và serialize inference. Thiếu/sai checkpoint trả UNAVAILABLE; phân đoạn vẫn được giữ. Không download trọng số tự động.

Tiền xử lý riêng của classifier: ảnh màu nguồn → LAB CLAHE luminance → RGB → letterbox 256 → ImageNet normalization. Segmentation vẫn dùng pipeline 512 riêng. Test đối chiếu tensor với training loader.

Status: PREDICTED, ABSTAIN, UNAVAILABLE. Chỉ đề xuất nhãn khi top1 >=0.60 và top1-top2 >=0.15; đây là ngưỡng thận trọng kỹ thuật, chưa được xác thực lâm sàng hay hiệu chuẩn. Điểm softmax không phải xác suất mắc bệnh. Nhãn là category ảnh MMOTU, không xác lập mô bệnh học. Không suy O-RADS, mức nguy cơ ác tính hoặc PCOS từ classifier. Patient-level independence chưa xác minh.

Kiểm thử: `pytest tests/test_image_classifier_serving.py`; `node tests/test_image_classification_ui.mjs`; `node scripts/type_check.js`.
