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
* **Dataset Scale:** 120+ clinical ultrasound cases across 60 patients.
* **Pathology Distribution:**
  1. *Simple Serous Cysts (U nang thanh dịch):* Anechoic, thin-walled, posterior acoustic enhancement.
  2. *Dermoid Cysts (U quái / U bì):* Heterogeneous, hyperechoic Rokitansky nodule with acoustic shadowing.
  3. *Endometriomas (U lạc nội mạc tử cung):* Homogeneous ground-glass low-level echoes.
  4. *Hemorrhagic Cysts (Nang xuất huyết):* Spiderweb / reticular fibrin strands.
  5. *Normal Controls (Buồng trứng bình thường - Empty Mask):* True Negative cases with physiological follicles $<8\text{mm}$.
* **Splitting Protocol:** Strict **Patient-Level Split (70% Train - 15% Validation - 15% Test)**. Zero data leakage across splits.

---

## 3. LOSS FUNCTION & OPTIMIZATION
* **Combo Loss Formulation:**
  $$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{Dice}} + 0.3 \cdot \mathcal{L}_{\text{Focal}} + 0.2 \cdot \mathcal{L}_{\text{BCE}}$$
* **Optimizer:** AdamW ($\text{LR} = 3\times 10^{-4}$, Weight Decay $= 1\times 10^{-4}$).
* **LR Scheduler:** CosineAnnealingLR ($T_{\max} = 15, \eta_{\min} = 1\times 10^{-6}$).

---

## 4. BENCHMARK PERFORMANCE (TEST SET)
* **Dice Similarity Coefficient (DSC):** $\ge 0.88 \pm 0.04$
* **Intersection over Union (IoU):** $\ge 0.79 \pm 0.05$
* **95% Hausdorff Distance ($HD_{95}$):** $\le 3.2\text{ mm}$
* **Inference Latency:** $< 450\text{ ms}$ on CPU ($< 45\text{ ms}$ on GPU).
* **True Negative Accuracy (Empty Masks):** $100\%$ (No spurious false positive masks).

---

## 5. INTENDED USE & CLINICAL SAFEGUARDS
* **Intended Use:** Clinical Decision Support System (CDSS) for sonographers and radiologists in gynecological imaging.
* **Human-in-the-Loop Requirement:** Model predictions are presented as transparent visual overlays. The doctor has full interactive brush/eraser controls to adjust boundaries before formal medical sign-off.
