# CLINICAL KNOWLEDGE CONFLICTS & RECONCILIATION MATRIX
## Ovarian Ultrasound AI Decision Support System

This document tracks identified discrepancies between major international clinical consensus systems (**IOTA** vs. **ACR O-RADS US** vs. **ESGO/ISUOG**) and establishes strict reconciliation rules for automated AI Clinical Decision Support.

---

### Conflict ID: KC-001
* **Topic**: Solid Component Definition & Cutoff for Benignity
* **Source A (IOTA Simple Rules 2016)**:
  * *Rule B2*: Defines a solid component with largest diameter $< 7\text{ mm}$ as a Benign Feature ($B$-rule).
* **Source B (ACR O-RADS US v2022)**:
  * *O-RADS 4*: Any cyst containing a solid component or papillary projection $\ge 3\text{ mm}$ with height $\ge 3\text{ mm}$ without acoustic shadowing is upgraded to **O-RADS 4** (Intermediate Risk, 10% to <50% malignancy risk), unless it is a classic dermoid Rokitansky nodule with acoustic shadowing.
* **Clinical Difference & Rationale**:
  * IOTA Simple Rules uses a 7 mm cutoff to tolerate tiny mural nodularities in predominantly cystic benign lesions, whereas O-RADS uses a conservative 3 mm threshold for papillary projections to maximize sensitivity for early borderline and malignant tumors.
* **Resolution in CDSS Engine**:
  * For risk stratification and triage recommendations, **O-RADS US v2022 takes precedence** (flagging papillary projections $\ge 3\text{ mm}$ as O-RADS 4 to avoid missing early borderline neoplasms).
  * In the IOTA feature panel, the exact millimeter measurement is reported alongside both criteria.
* **Requires Clinician Review**: `YES (Marked with CDSS advisory)`

---

### Conflict ID: KC-002
* **Topic**: Multilocular Cyst Size Cutoff ($< 10\text{ cm}$ vs $\ge 10\text{ cm}$)
* **Source A (IOTA Simple Rules 2016)**:
  * *Rule B4*: Smooth multilocular tumor with largest diameter $< 100\text{ mm}$ is a Benign Feature ($B$-rule).
  * *Rule M4*: Irregular multilocular-solid tumor with largest diameter $\ge 100\text{ mm}$ is a Malignant Feature ($M$-rule).
* **Source B (ACR O-RADS US v2022)**:
  * *O-RADS 3*: Smooth multilocular cyst $< 10\text{ cm}$ with Color Score 1-3.
  * *O-RADS 4*: Smooth multilocular cyst $\ge 10\text{ cm}$ with Color Score 1-3.
* **Clinical Difference & Rationale**:
  * O-RADS upgrades smooth multilocular cysts $\ge 10\text{ cm}$ to O-RADS 4 solely due to size (increased statistical risk of large mucinous neoplasms / mucinous borderline tumors), even in the absence of solid components. IOTA Simple Rules only classifies $\ge 100\text{ mm}$ as malignant if solid components or irregularity are present ($M4$).
* **Resolution in CDSS Engine**:
  * If a multilocular cyst is $\ge 100\text{ mm}$ with completely smooth septa and no solid components:
    * Categorized as **O-RADS 4** per ACR guidelines.
    * Annotated with IOTA note: *"Smooth multilocular cyst $\ge 10\text{ cm}$; histology predominantly reveals benign large mucinous cystadenoma, but surgical excision recommended due to potential borderline histology."*
* **Requires Clinician Review**: `YES`

---

### Conflict ID: KC-003
* **Topic**: Solid Lesions with Acoustic Shadowing (Fibromas/Thecomas vs Malignancy)
* **Source A (IOTA ADNEX / Simple Rules)**:
  * Acoustic shadowing is an independent predictor strongly reducing malignancy risk ($B3$).
* **Source B (ACR O-RADS US v2020 vs v2022 Update)**:
  * In v2020, all solid masses without qualification were initially flagged as O-RADS 4/5.
  * In v2022, ACR updated the guideline: Solid lesions with smooth contours and definite acoustic shadowing are downgraded to **O-RADS 3** (or O-RADS 2 if classic), recognizing the benignity of ovarian fibromas and thecomas.
* **Resolution in CDSS Engine**:
  * The system applies the **v2022 ACR Update** and **IOTA B3** synergy: If acoustic shadowing is detected in a solid smooth-contoured mass with Color Score 1-2, it is stratified as **O-RADS 3 (Low Risk)** rather than O-RADS 4/5.
* **Requires Clinician Review**: `NO (Standardized consensus rule)`

---

### Conflict ID: KC-004
* **Topic**: CA-125 Biomarker Utility in Premenopausal vs Postmenopausal Women
* **Source A (ESGO/ISUOG/IOTA/ESGE 2021)**:
  * Discourages relying on serum CA-125 alone in premenopausal women due to high false-positive rates from endometriosis, adenomyosis, and pelvic inflammatory disease.
* **Source B (RMI - Risk of Malignancy Index)**:
  * Uses CA-125 linearly as a multiplicative multiplier in the formula $RMI = U \times M \times CA125$.
* **Resolution in CDSS Engine**:
  * The CDSS prioritizes **IOTA ADNEX and O-RADS US morphology** over RMI. In premenopausal patients, elevated CA-125 without suspicious ultrasound morphology generates a warning: *"CA-125 may be elevated due to benign gynecologic etiology (e.g., Endometrioma, Adenomyosis). Morphology-based IOTA/O-RADS risk takes clinical precedence."*
* **Requires Clinician Review**: `YES`
