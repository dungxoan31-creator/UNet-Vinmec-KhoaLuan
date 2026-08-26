# CLINICAL VALIDATION & MEDICAL AI SAFETY STANDARDS
## Ovarian Ultrasound AI Decision Support System (Vinmec Healthcare Protocol)

This document establishes the clinical governance, AI validation standards, and safety guardrails implemented within the Ovarian Ultrasound AI Decision Support System.

---

## 1. Clinical Decision Support System (CDSS) Framing
- **Role of AI**: The system operates strictly as a **Class II SaMD (Software as a Medical Device) Clinical Decision Support Assistant**. It provides preliminary mass localization, boundary segmentation, and automated caliper measurements (D1, D2, D3, Volume).
- **Clinician Supremacy**: AI inference outputs are explicitly flagged as `ANALYZED — REQUIRES CLINICIAN REVIEW`. Final diagnostic conclusions, O-RADS categorization, and medical reports require active verification, editing (if necessary), and formal sign-off by a credentialed Specialist Physician.
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
Every inference result, database prediction record, and exported report is permanently stamped with:
- **Model Name**: `Attention U-Net Dual Attention Gates`
- **Model Version**: `v1.2.0-clinical`
- **Checkpoint SHA-256 Checksum**: `81dcac9db4c5feb3ddfc82325bcfab95e4b6fc92e39f133640b6e5bfeb5dd668`
- **Inference Hardware**: `CPU` / `CUDA GPU`
- **Inference Latency**: Exact millisecond execution timer
- **Preprocessing Version**: `UltrasoundPreprocessor-v1.2`

---

## 5. Patient-Level Data Stratification (Zero Leakage)
Official model training and evaluation partitions (`ai_training/splits/`) strictly enforce **patient-level separation**:
- **Training Set (`train.csv`)**: 700 images (OTU_2D Train)
- **Validation Set (`val.csv`)**: 120 images (OTU_2D Validation)
- **Independent Test Set (`test.csv`)**: 382 images (OTU_2D Test)
- **CEUS Extended Test Set (`ceus_test.csv`)**: 170 images (OTU_CEUS)
- **Total Evaluated**: 1,372 clinical images without patient cross-contamination.

---

## 6. Audit Trail & Regulatory Compliance
The SQLite/PostgreSQL database logs an immutable audit trail (`audit_logs` table) for all clinical events:
- `UPLOAD_IMAGE`: Timestamp, sanitized filename, dimensions, study association.
- `VALIDATE_IQA`: Quality score, sharpness, contrast std, validation status.
- `RUN_PREDICTION`: Model version, checksum, confidence, uncertainty level, lesion count.
- `DOCTOR_ACCEPTED_RAW` / `DOCTOR_MODIFIED` / `DOCTOR_REJECTED`: Clinician ID, time spent, verified RLE mask, final pathology.
- `GENERATE_PDF_REPORT`: Export timestamp, recipient study.
