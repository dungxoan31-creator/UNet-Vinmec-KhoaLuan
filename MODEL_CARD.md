# AI MODEL CARD: OVARIAN ULTRASOUND ATTENTION U-NET
**Model Name:** Attention U-Net Ovarian Lesion Segmentation Engine  
**Version:** v1.2.0  
**Authors:** Nguyễn Hữu Dũng (MIS 65A - National Economics University)  
**Supervisor:** TS. Trần Triệu Hải  
**Context & Partner:** Vinmec Healthcare System (Times City) / VinSmart Future  

---

## 1. MODEL OVERVIEW
* **Model Architecture:** Attention U-Net (Deep convolutional encoder-decoder with Attention Gates at skip connections).
* **Target Modality:** 2D Transvaginal (TVUS) & Transabdominal (TAUS) Ultrasound Images.
* **Clinical Task:** Automated Ovarian Lesion Semantic Segmentation & Caliper Extraction ($D_{\max}, D_{\text{orth}}$, Area).
* **Input:** $1\times 512 \times 512$ single-channel grayscale ultrasound tensor (Letterbox padded with aspect ratio preservation).
* **Output:** $1\times 512 \times 512$ binary lesion segmentation mask (RLE encoded) + Caliper crosshair endpoints.

---

## 2. TRAINING & VALIDATION DATASET
* **Dataset Scale:** Toàn bộ **1,372 cặp ảnh & mặt nạ Ground Truth thực tế** (100% paired).
  * `OTU_2D/train`: 820 cặp ảnh siêu âm 2D B-mode.
  * `OTU_2D/test`: 382 cặp ảnh siêu âm 2D kiểm thử độc lập.
  * `OTU_CEUS`: 170 cặp ảnh siêu âm cản âm (Contrast-Enhanced Ultrasound).
* **Multi-Modal Splitting Protocol:**
  * **Unified Training Pool:** 1,098 ca (80%).
  * **Unified Validation Set:** 137 ca (10%) - Validation Dice đạt 0.7887, IoU 0.6830.
  * **Hold-out Test Set:** 137 ca (10%) - Phân tầng đại diện 2D & CEUS, không rò rỉ dữ liệu (Zero Data Leakage).

---

## 3. LOSS FUNCTION & OPTIMIZATION
* **Combo Loss Formulation:**
  $$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{Dice}} + 0.3 \cdot \mathcal{L}_{\text{Focal}} + 0.2 \cdot \mathcal{L}_{\text{BCE}}$$
* **Optimizer:** AdamW ($\text{LR} = 1\times 10^{-4}$, Weight Decay $= 1\times 10^{-4}$).
* **LR Scheduler:** CosineAnnealingLR ($T_{\max} = 4, \eta_{\min} = 1\times 10^{-6}$).
* **Data Augmentation:** Random Horizontal Flip, Rotation ($\pm 10^\circ$), CLAHE contrast equalization, Speckle noise injection, Letterboxing aspect ratio preservation.
* **Test-Time Augmentation (TTA):** Ensembling original & horizontally flipped tensors for smooth boundary extraction.

---

## 4. BENCHMARK PERFORMANCE (INDEPENDENT TEST SET)
* **Dice Similarity Coefficient (DSC):** $0.7404 \pm 0.2508$ (Đạt $0.978$ trên các ca điển hình).
* **Intersection over Union (IoU):** $0.6406 \pm 0.2694$.
* **95% Hausdorff Distance ($HD_{95}$):** $3.38\text{ mm}$.
* **Inference Latency (TTA):** $\approx 215\text{ ms}$ on CPU ($< 35\text{ ms}$ on GPU).
* **True Negative & Boundary Safeguards:** Morphological close & open filtering, Connected Component noise rejection ($<100\text{ px}$).


---

## 5. INTENDED USE & CLINICAL SAFEGUARDS
* **Intended Use:** Clinical Decision Support System (CDSS) for sonographers and radiologists in gynecological imaging.
* **Human-in-the-Loop Requirement:** Model predictions are presented as transparent visual overlays. The doctor has full interactive brush/eraser controls to adjust boundaries before formal medical sign-off.
