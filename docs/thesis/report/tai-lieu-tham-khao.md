# TÀI LIỆU THAM KHẢO

[1] O. Ronneberger, P. Fischer và T. Brox, “U-Net: Convolutional Networks for Biomedical Image Segmentation,” 2015, arXiv:1505.04597. [VERIFIED] [Bài báo gốc](https://arxiv.org/abs/1505.04597). Kiểm tra ngày 13/10/2026.

[2] Z. Zhou, M. M. R. Siddiquee, N. Tajbakhsh và J. Liang, “UNet++: A Nested U-Net Architecture for Medical Image Segmentation,” 2018, arXiv:1807.10165. [VERIFIED] [Bài báo gốc](https://arxiv.org/abs/1807.10165). Kiểm tra ngày 13/10/2026.

[3] Q. Zhao và cộng sự, “MMOTU: A Multi-Modality Ovarian Tumor Ultrasound Image Dataset for Unsupervised Cross-Domain Semantic Segmentation,” 2022, bản cập nhật 2023, arXiv:2207.06799. [VERIFIED] [Công bố tác giả](https://arxiv.org/abs/2207.06799). Nguồn công bố được xác minh; quan hệ với tệp dữ liệu dự án và quyền sử dụng tệp hiện hữu vẫn [PARTIALLY VERIFIED].

[4] A. Diaz-Pinto và cộng sự, “MONAI Label: A framework for AI-assisted Interactive Labeling of 3D Medical Images,” 2022, bản cập nhật 2023, arXiv:2203.12362. [VERIFIED] [Công bố tác giả](https://arxiv.org/abs/2203.12362).

[5] American College of Radiology, “O-RADS Ultrasound,” tài liệu chính thức và bộ tài nguyên thuật ngữ O-RADS US. [VERIFIED] [Trang tài nguyên ACR](https://www.acr.org/Clinical-Resources/Clinical-Tools-and-Reference/Reporting-and-Data-Systems/O-RADS/Ultrasound). Dùng định vị thuật ngữ và giới hạn phạm vi; không xác nhận prototype thực hiện đầy đủ hệ thống phân tầng nguy cơ.

[6] FastAPI, “Tutorial – User Guide,” tài liệu chính thức. [VERIFIED] [Hướng dẫn FastAPI](https://fastapi.tiangolo.com/tutorial/). Kiểm tra ngày 13/10/2026.

[7] PyTorch, “Learn the Basics,” tài liệu chính thức. [VERIFIED] [Hướng dẫn PyTorch](https://docs.pytorch.org/tutorials/beginner/basics/intro.html). Phiên bản thư viện chạy dự án lấy từ môi trường/run config, không suy từ phiên bản website.

[8] SQLAlchemy, “Transactions and Connection Management,” tài liệu ORM 2.0. [VERIFIED] [Tài liệu transaction](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).

[9] MDN Web Docs, “Transformations – Canvas API Tutorial.” [VERIFIED] [Tài liệu Canvas](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Transformations). Implementation và phép biến đổi cụ thể đối chiếu mã nguồn [18].

[10] World Wide Web Consortium, “Web Content Accessibility Guidelines (WCAG) 2.2.” [VERIFIED] [Tiêu chuẩn WCAG](https://www.w3.org/TR/WCAG22/). Tham chiếu tiêu chí thiết kế, không phải chứng nhận ứng dụng đã đạt AA.

[11] SQLite, “SQLite Is Transactional,” tài liệu chính thức. [VERIFIED] [Tài liệu SQLite](https://www.sqlite.org/transactional.html).

[12] Nguyễn Hữu Dũng, “Đề cương sơ bộ khóa luận tốt nghiệp,” tệp MSV_11235559_NguyenHuuDung_DeCuongSoBo.docx, tài liệu sinh viên cung cấp. [VERIFIED: tài liệu hiện hữu] Các số liệu 307 ảnh/185 bệnh nhân, phê duyệt nhãn và ẩn danh trong kế hoạch là [PARTIALLY VERIFIED] khi đối chiếu hồ sơ nguồn hiện trạng.

[13] Khoa Hệ thống Thông tin Quản lý, Đại học Kinh tế Quốc dân, “Hướng dẫn viết chuyên đề thực tập/khóa luận tốt nghiệp,” tệp K.HTTTQL.HƯỚNG-DẪN-VIẾT-KHÓA-LUẬN-TỐT-NGHIỆP-1.docx, tài liệu được cung cấp. [VERIFIED: đã đọc toàn bộ tệp].

[14] Đinh Mạnh Hòa, “Xây dựng ứng dụng web quản lý cho thuê xe máy tại Công ty TNHH BIGTOWN Việt Nam,” khóa luận mẫu, 12/2025, tệp Khóa luận - Đinh Mạnh Hòa - 11222416 - final.docx. [VERIFIED: đã đọc toàn bộ tệp] Chỉ dùng làm mẫu kết cấu, bố trí chương mục và trình bày, không làm nguồn dữ liệu y tế.

[15] Dự án UNet-Vinmec-KhoaLuan, manifest unified_vinmec_clean_2026-10-06, danh mục Train/Validation/Test, hồ sơ kiểm toán ảnh gần trùng; M3_Bang_Chung_Du_Lieu_2026-10-08.md và workbook Mau_Xin_Danh_Muc_Anh_Patient_Case_ID_2026-10-07.xlsx. [VERIFIED: artifact và phép đối chiếu chuỗi mã/tệp] [PARTIALLY VERIFIED: tính ổn định mã bệnh nhân nguồn, provenance và quyền sử dụng] Đường dẫn tái lập ở Phụ lục A.

[16] Dự án UNet-Vinmec-KhoaLuan, run config/training history Standard U-Net comparator và U-Net++/ResNet34 ngày 06/10/2026; model_comparison_validation.json, test_summary.json, test_per_image.csv và predictions thuộc evaluation/milestone_3_2026-10-06; error_analysis_summary.json và api_latency_summary.json thuộc evaluation/milestone_3_audit_2026-10-06/validation_lock/. [VERIFIED: số liệu trích từ artifact] [PARTIALLY VERIFIED: diễn giải hiệu năng lâm sàng].

[17] Dự án UNet-Vinmec-KhoaLuan, mã backend: backend/models/unet.py, backend/services/preprocessor.py, backend/services/inference_engine.py, backend/services/source_measurements.py, backend/app/routers/, backend/schemas/schemas.py và backend/db/database.py; đọc trong phiên biên soạn ngày 13/10/2026. [VERIFIED: implementation được đối chiếu].

[18] Dự án UNet-Vinmec-KhoaLuan, frontend/app, frontend/css, frontend/README.md, Workspace_V2_Design_and_API.md và ảnh chụp artifacts/workspace-v2. [VERIFIED: giao diện và nguồn demo] [PARTIALLY VERIFIED: tính hữu dụng thực địa và backend của các chức năng mở rộng].

[19] Dự án UNet-Vinmec-KhoaLuan, mã tests và các log backend-verification.log, frontend-verification.log, runtime-live-verification.log, kết quả lưu ngày 11/10/2026. [VERIFIED: log hiện hữu] Không trình bày như lượt test mới ngày biên soạn; chưa có dữ liệu đánh giá người dùng lâm sàng.
