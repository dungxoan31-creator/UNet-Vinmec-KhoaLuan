# CLINICAL VALIDATION & MEDICAL AI SAFETY STANDARDS
## Ovarian Ultrasound AI Decision Support System (Vinmec Times City Clinical Context)

> **Khóa luận Tốt nghiệp**: *“Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”*  
> **Sinh viên**: Nguyễn Hữu Dũng — MSV: 11235559 — Lớp: HTTTQL 65A, Trường Công nghệ & Kinh tế số, ĐH Kinh tế Quốc dân  
> **Cán bộ hướng dẫn**: ThS. Trần Thanh Hải  
> **Bối cảnh lâm sàng & Dữ liệu**: Bệnh viện Đa khoa Quốc tế Vinmec Times City  
> **Bản chất phần mềm**: Bản mẫu nghiên cứu thực nghiệm (Academic Research Prototype) — Không phải hệ thống thương mại chính thức đã triển khai tại Vinmec

This document establishes the clinical governance, AI validation standards, and safety guardrails implemented within the Ovarian Ultrasound AI Decision Support System research prototype.

---

## 1. Clinical Decision Support System (CDSS) Framing
- **Role of AI**: The system operates strictly as an **Academic Research Prototype for Lesion Segmentation Assist (Class II SaMD-oriented)**. It provides preliminary mass localization, boundary segmentation, and automated caliper measurements ($D_1, D_2, D_3$, Volume).
- **Human-in-the-Loop (HITL) Protocol**: AI outputs are strictly suggestions requiring the 5-step clinical workflow:
  $$\text{Ultrasound Image} \longrightarrow \text{Pre-IQA} \longrightarrow \text{AI Segmentation} \longrightarrow \text{Doctor Review/Edit} \longrightarrow \text{Doctor Confirmation}$$
- **Clinician Supremacy**: AI inference outputs are explicitly flagged as `ANALYZED — REQUIRES CLINICIAN REVIEW`. Final diagnostic conclusions, O-RADS categorization, and medical reports require active verification, editing (if necessary), and formal sign-off by a credentialed Specialist Physician. AI never autonomously diagnoses pathologies.
- **Safety Precedence**: `Clinical Safety > Diagnostic Accuracy > Traceability > Reliability > Usability > UI Aesthetics`.

---

## 2. Pre-Inference Medical Image Quality Assessment (IQA)
To prevent garbage-in-garbage-out and ensure patient safety, all input images must pass a 4-tier automated IQA screening before reaching the neural network:

| Check | Clinical Requirement | Rejection Rationale |
|---|---|---|
| **Resolution & Matrix** | Width $\ge 128$ px, Height $\ge 128$ px | Sub-resolution images lack histological grain for tissue characterization. |
| **Aspect Ratio** | $0.3 \le \text{AR} \le 3.5$ | Rejects corrupted or distorted scan geometries. |
| **Ultrasound Modality** | Grayscale B-Mode (Saturation $\le 35$, High Saturation Area $\le 18\%$) | Rejects natural/color photos, clinical camera selfies, or non-medical graphics. |
| **Dynamic Range & Exposure** | $8.0 \le \text{Mean} \le 242.0$, $\text{Std} \ge 16.0$ | Rejects blank, completely dark (acoustic dropout), or overexposed/white frames. |
| **Focus & Sharpness** | Laplacian Variance $\ge 18.0$ | Rejects severe probe motion blur or out-of-focus captures. |

---

## 3. Uncertainty & Out-of-Distribution (OOD) Quantification
Medical AI must never convert ambiguity into false certainty. The system computes Shannon Binary Entropy across predicted probability maps:
$$H(p) = -p \log_2(p) - (1-p) \log_2(1-p)$$

- **Low Uncertainty ($H < 0.35$)**: Clear lesion margins, well-defined acoustic boundaries.
- **Moderate Uncertainty ($0.35 \le H < 0.55$)**: Moderate boundary ambiguity; clinician is advised to inspect orthogonal views.
- **High Uncertainty ($H \ge 0.55$)**: Flagged with explicit alert: *"Độ bất định mô hình cao. Tổn thương ranh giới mờ — Bác sĩ cần đối chiếu ảnh gốc và hiệu chỉnh Caliper thủ công."*

---

## 4. Model Versioning, Provenance & Reproducibility
Every inference result, database prediction record, and exported report is permanently stamped with model metadata:
- **Baseline Architecture**: `Standard U-Net (Ronneberger et al., 2015)` (`checkpoints/baseline_unet_best.pth`)
- **Comparative Architecture**: `Attention U-Net Dual Attention Gates` (`checkpoints/best_attention_unet.pth`)
- **Model Version**: `v1.2.0-clinical` / `v1.0-baseline`
- **Inference Hardware**: `CPU` / `CUDA GPU`
- **Inference Latency**: Exact millisecond execution timer
- **Preprocessing Version**: `UltrasoundPreprocessor-v1.2` (Letterbox 512x512, Normalization [0, 1])

---

## 5. Patient-Level Data Stratification (Zero Leakage)
Official model training and evaluation partitions (`ai_training/splits/` and `dataset/vinmec_ovarian/`) strictly enforce **patient-level separation**:
- **Dataset Niêm phong (5 số liệu cốt lõi)**:
  - **1.387 ảnh tiếp nhận tổng cộng** từ Vinmec Times City
  - **417 ảnh có mask sơ bộ**
  - **307 ảnh Ground Truth** (từ **185 bệnh nhân**, gồm 35 empty masks)
  - **110 ảnh pending review**
  - **970 ảnh thô chưa gán nhãn**
- **Cấu hình Phân vùng Đánh giá (Evaluation Partitions)**:
  - **Training Set (`train.csv` / `train_v2.csv`)**: 700 ảnh (OTU_2D Train)
  - **Validation Set (`val.csv` / `val_v2.csv`)**: 120 ảnh (OTU_2D Validation)
  - **Independent Test Set (`test.csv` / `test_v2.csv`)**: 382 ảnh (OTU_2D Test)
  - **CEUS Extended Test Set (`ceus_test.csv`)**: 170 ảnh (OTU_CEUS)
  - **Total Evaluated**: 1,372 clinical images without patient cross-contamination (Zero Data Leakage).

---

## 6. Audit Trail & Regulatory Compliance
The SQLite database logs an immutable audit trail (`audit_logs` table) for all clinical events:
- `UPLOAD_IMAGE`: Timestamp, sanitized filename, dimensions, study association.
- `VALIDATE_IQA`: Quality score, sharpness, contrast std, validation status.
- `RUN_PREDICTION`: Model version, checksum, confidence, uncertainty level, lesion count.
- `DOCTOR_ACCEPTED_RAW` / `DOCTOR_MODIFIED` / `DOCTOR_REJECTED`: Clinician ID, time spent, verified RLE mask, final pathology.
- `GENERATE_PDF_REPORT`: Export timestamp, recipient study.
