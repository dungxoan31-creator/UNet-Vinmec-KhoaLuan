# CLINICAL KNOWLEDGE BASE: OVARIAN ULTRASOUND ANALYSIS & CDSS
## Comprehensive Diagnostic Lexicon, Morphology, IOTA & ACR O-RADS v2022 Mapping
**Document Version:** 2.0 (Medical AI SaMD Benchmark Standard)
**Clinical Standards:** ACR O-RADS US v2022 / 2023 Update, IOTA Lexicon/ADNEX/Simple Rules, ISUOG Consensus, ESGO/ISUOG/IOTA/ESGE 2021
**Intended Application:** Machine Learning Feature Engineering, Deterministic CDSS Rule Engine, and Clinical Verification

---

# SECTION 1: NORMAL OVARY & PHYSIOLOGICAL FINDINGS

## 1.1. Normal Ovary (Premenopausal / Postmenopausal)
1. **Ultrasound Appearance**: Homogeneous, intermediate-to-low ground echogenicity stroma containing multiple peripheral or scattered small hypo/anechoic developing follicles in premenopausal women; smaller, retracted, follicle-depleted hypoechoic stroma in postmenopausal women.
2. **Shape**: Ovoid, ellipsoid, almond-shaped with clear demarcated borders against surrounding pelvic fat.
3. **Size**:
   - *Premenopausal volume*: 3 - 10 cm^3 (Typical dimensions: 3.0 x 2.0 x 1.5 cm, D_max approx 25 - 40 mm).
   - *Postmenopausal volume*: < 3 cm^3 (Typical dimensions: 2.0 x 1.0 x 1.0 cm, D_max < 20 mm).
4. **Echogenicity**: Intermediate echogenicity central stroma with anechoic round sub-centimeter cystic follicles.
5. **Wall Characteristics**: Smooth outer ovarian capsule, regular margins, no focal exophytic buds or capsular thickening.
6. **Septations**: Absent (parenchymal stroma bridges between follicles are not true pathological septa).
7. **Solid Components**: None.
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1 (No flow within follicular fluid; normal low-to-moderate physiological stromal parenchymal flow on color Doppler).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent (minimal physiological pouch of Douglas fluid <= 5 - 10 mL is normal in premenopausal females).
12. **IOTA Terminology**: Normal ovarian parenchyma / Physiological tissue.
13. **O-RADS Category**: **O-RADS 1** (Normal premenopausal or postmenopausal ovary; 0% risk of malignancy).
14. **Reference Source**: ACR O-RADS US v2022 (Strachowski et al., Radiology 2023; DOI: 10.1148/radiol.230685); IOTA Consensus (Timmerman et al., UOG 2000).
15. **Example Image / Source**: MMOTU 2D `normal_ovary` class; Radiopaedia [Ovary Ultrasound (rID: 10834)](https://radiopaedia.org/articles/ovary-ultrasound).

---

## 1.2. Normal Follicles (Antral / Dominant Graafian Follicle)
1. **Ultrasound Appearance**: Crisp, thin-walled, completely anechoic round or oval fluid-filled cavity situated within the peripheral ovarian cortex.
2. **Shape**: Round or oval with sharp acoustic margins.
3. **Size**:
   - *Antral follicles*: 2 - 9 mm.
   - *Dominant (Graafian) follicle*: 10 - 29 mm (premenopausal). Note: Any anechoic cystic structure <= 30 mm in a premenopausal woman is clinically categorized as a physiological follicle, not a true neoplasm.
4. **Echogenicity**: Purely anechoic (jet black) with pronounced posterior acoustic enhancement.
5. **Wall Characteristics**: Smooth, uniform, paper-thin wall (< 1 mm).
6. **Septations**: Absent (strictly unilocular).
7. **Solid Components**: None (Cumulus oophorus may appear as a tiny <= 2 mm eccentric isoechoic mural papilla indicating imminent ovulation).
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1 (No blood flow in cavity; occasional delicate peripheral vascular arch).
10. **Acoustic Shadow**: Absent; distinct posterior acoustic enhancement.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular cyst, anechoic cyst fluid, smooth inner wall.
13. **O-RADS Category**: **O-RADS 1** (Follicle <= 30 mm in premenopausal female; 0% risk of malignancy).
14. **Reference Source**: ACR O-RADS US v2022; ISUOG Practice Guidelines.
15. **Example Image / Source**: Kaggle Ovarian Ultrasound Image Dataset (`Dominant follicle`); Radiopaedia [Ovarian Follicle (rID: 12891)](https://radiopaedia.org/articles/ovarian-follicle).

---

## 1.3. Corpus Luteum / Hemorrhagic Corpus Luteum
1. **Ultrasound Appearance**: Unilocular thick-walled cyst with crenulated or scalloped inner margins, variable internal echogenicity (spider-web reticular fibrinous strands or jelly-like clot), and a distinctive circumferential hypervascular peripheral rim ("Ring of Fire").
2. **Shape**: Round, oval, or mildly collapsed/crenulated contour.
3. **Size**: Usually 15 - 30 mm (spontaneously involutes over 1-2 menstrual cycles).
4. **Echogenicity**: Heterogeneous internal echoes with non-shadowing fine lace-like fibrinous strands (reticular pattern) or retracting isoechoic/hyperechoic blood clot.
5. **Wall Characteristics**: Thickened (2 - 4 mm), hypervascular, often crenulated or scalloped inner margin.
6. **Septations**: Incomplete fibrin strands (pseudoseptations; compressible, avascular on Doppler).
7. **Solid Components**: Retracting avascular fibrin clot (must be verified avascular by Color Doppler to distinguish from true solid neoplasm).
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 3-4 along the outer capsule ("Ring of Fire" rim vascularity with low-impedance flow), Color Score 1 within internal fibrin/clot.
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent (minimal localized cul-de-sac fluid on rupture).
12. **IOTA Terminology**: Unilocular cyst with mixed/internal echoes (reticular pattern), peripheral vascular flow.
13. **O-RADS Category**: **O-RADS 2** (Classic benign corpus luteum <= 30 mm in premenopausal woman; < 1% risk).
14. **Reference Source**: ACR O-RADS US v2022; Andreotti et al., Radiology 2020 (DOI: 10.1148/radiol.2019191150).
15. **Example Image / Source**: Radiopaedia [Corpus Luteum Cyst (rID: 14782)](https://radiopaedia.org/articles/corpus-luteum-cyst).

---

## 1.4. Physiological Findings (Polycystic Ovarian Morphology - PCOM)
1. **Ultrasound Appearance**: Enlarged ovary with >= 20 small peripheral antral follicles (2 - 9 mm) arranged along the periphery like a "string of pearls", surrounding a prominent, dense, hyperechoic central stroma.
2. **Shape**: Globular, rounded, enlarged ovary.
3. **Size**: Ovarian volume > 10 cm^3 in premenopausal women (in absence of a dominant follicle or corpus luteum).
4. **Echogenicity**: Hyper-reflective central fibrous stroma surrounded by multiple peripheral anechoic micro-cysts.
5. **Wall Characteristics**: Smooth, intact ovarian capsule.
6. **Septations**: Absent.
7. **Solid Components**: None.
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1-2 (Increased intra-stromal arterial flow with high velocity, normal resistance).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Multicystic / Multifollicular normal architecture with hypertrophic stroma.
13. **O-RADS Category**: **O-RADS 1** (Physiological variant / PCOM; 0% risk of malignancy).
14. **Reference Source**: International PCOS Guideline (Monash/ASRM/ESHRE 2023 update); Rotterdam Consensus.
15. **Example Image / Source**: PCOSGen Benchmark (`PCOS-positive`); Kaggle PCOS Image Dataset.

---

# SECTION 2: BENIGN LESIONS (O-RADS 2 & BENIGN O-RADS 3)

## 2.1. Simple Ovarian Cyst
1. **Ultrasound Appearance**: Anechoic, thin-walled, round or oval cystic lesion with imperceptible smooth inner lining and distinct acoustic enhancement.
2. **Shape**: Round or oval.
3. **Size**: > 30 mm to 100 mm in premenopausal; > 10 mm to 100 mm in postmenopausal.
4. **Echogenicity**: Completely anechoic (pure black fluid) without internal debris.
5. **Wall Characteristics**: Smooth, uniform, paper-thin wall (< 1 mm).
6. **Septations**: None (strictly unilocular).
7. **Solid Components**: None.
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1 (No blood flow in cyst cavity or wall).
10. **Acoustic Shadow**: Absent; clean posterior acoustic enhancement.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular cyst with anechoic cyst fluid and smooth inner walls.
13. **O-RADS Category**:
   - **O-RADS 2**: Premenopausal > 30 - 50 mm or postmenopausal <= 30 mm (< 1% risk).
   - **O-RADS 3**: Premenopausal > 50 - 100 mm or postmenopausal > 30 - 100 mm (1 - 9% risk).
14. **Reference Source**: ACR O-RADS US v2022; IOTA Simple Rules (Rule B1).
15. **Example Image / Source**: MMOTU `simple_cyst` class; Radiopaedia [Ovarian Simple Cyst (rID: 15420)](https://radiopaedia.org/articles/simple-ovarian-cyst).

---

## 2.2. Hemorrhagic Ovarian Cyst
1. **Ultrasound Appearance**: Unilocular cyst with classic reticular fine internal echoes ("fishnet", "spider-web", "lace-like") or a retracting triangular/curvilinear avascular clot with concave borders.
2. **Shape**: Round, oval.
3. **Size**: Usually 30 - 50 mm, occasionally up to 80 mm.
4. **Echogenicity**: Reticular lace-like fibrinous strands, moving gelatinous debris on probe pressure, or solid-appearing hyperechoic retracting clot.
5. **Wall Characteristics**: Thin to mildly thickened smooth outer wall.
6. **Septations**: Absent (internal strands are fibrin mesh, not true vascular septa).
7. **Solid Components**: None (Retracting clot mimics solid mass but demonstrates **no vascularity on Doppler** and concave outer margin).
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1 (Strictly avascular internal clot; no internal flow).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular cyst with internal reticular echoes / jelly-like clot.
13. **O-RADS Category**:
   - **O-RADS 2**: Classic hemorrhagic cyst < 50 mm in premenopausal female (< 1% risk).
   - **O-RADS 3**: Classic hemorrhagic cyst >= 50 mm in premenopausal female or any hemorrhagic cyst in postmenopausal female.
14. **Reference Source**: ACR O-RADS US v2022; Andreotti et al., Radiology 2020.
15. **Example Image / Source**: Radiopaedia [Hemorrhagic Ovarian Cyst (rID: 18931)](https://radiopaedia.org/articles/hemorrhagic-ovarian-cyst).

---

## 2.3. Endometrioma ("Chocolate Cyst")
1. **Ultrasound Appearance**: Unilocular (or unilocular with <= 2 septations) cyst containing homogeneous, diffuse, low-level internal echoes ("ground-glass" echogenicity) without internal flow.
2. **Shape**: Round, oval, frequently adherent or kissing ovaries in bilateral disease.
3. **Size**: Typically 20 - 100 mm.
4. **Echogenicity**: Homogeneous low-level "ground-glass" echoes throughout the cyst lumen. Hyperechoic wall foci (cholesterol/hemosiderin punctate wall spots) may be present.
5. **Wall Characteristics**: Smooth, thickened fibrotic capsule (2 - 3 mm); may have hyperechoic wall punctate foci.
6. **Septations**: Typically none (unilocular) or occasional complete non-vascular thin septation (< 3 mm).
7. **Solid Components**: None (sludge or mural clot must have no Color Doppler signal).
8. **Papillary Projections**: None (if vascular papillary projection is detected, reclassify to O-RADS 4/5 - suspect clear cell or endometrioid malignancy).
9. **Doppler Vascularity**: Color Score 1 (Strictly avascular lumen; mild peripheral capsular flow only).
10. **Acoustic Shadow**: Absent (may exhibit small hyperechoic mural spots without acoustic shadow).
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular cyst with homogeneous low-level ("ground glass") internal echoes.
13. **O-RADS Category**:
   - **O-RADS 2**: Classic endometrioma < 100 mm in premenopausal women (< 1% risk).
   - **O-RADS 3**: Classic endometrioma >= 100 mm in premenopausal or any endometrioma in postmenopausal women.
14. **Reference Source**: ACR O-RADS US v2022; IOTA Simple Rules (Rule B2); Van Calster et al., BMJ 2014.
15. **Example Image / Source**: MMOTU `chocolate_cyst` class; Radiopaedia [Ovarian Endometrioma (rID: 11043)](https://radiopaedia.org/articles/ovarian-endometrioma).

---

## 2.4. Dermoid Cyst (Mature Cystic Teratoma)
1. **Ultrasound Appearance**: Cystic mass containing highly echogenic non-shadowing lines/dots ("dermoid mesh"), focal intensely hyperechoic mural nodule with dense distal acoustic shadowing ("Rokitansky nodule" or "dermoid plug"), or "tip of the iceberg" sign where deep posterior wall is obscured by dense shadow.
2. **Shape**: Round, oval, or lobulated.
3. **Size**: Highly variable (20 - 150 mm).
4. **Echogenicity**: Intensely hyperechoic mural component (sebaceous/hair plug), fluid-fluid lipid-aqueous interfaces, dot-dash dermoid lines.
5. **Wall Characteristics**: Smooth outer boundary, well-circumscribed.
6. **Septations**: Rare; internal linear echoes correspond to hair fibers.
7. **Solid Components**: Hyperechoic Rokitansky nodule (calcification, sebaceous material, hair).
8. **Papillary Projections**: None (Rokitansky nodule is an echogenic plug with acoustic shadowing, distinguishable from vascular papillary projection).
9. **Doppler Vascularity**: Color Score 1 (Avascular internal components and avascular Rokitansky nodule).
10. **Acoustic Shadow**: **Prominent, dense acoustic shadowing** cast by sebaceous debris, tooth, or calcification.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular or multilocular lesion with mixed echogenicity, dermoid mesh, and acoustic shadowing.
13. **O-RADS Category**:
   - **O-RADS 2**: Classic dermoid < 100 mm with acoustic shadowing in premenopausal woman (< 1% risk).
   - **O-RADS 3**: Classic dermoid >= 100 mm in premenopausal or any dermoid in postmenopausal woman.
14. **Reference Source**: ACR O-RADS US v2022; IOTA Simple Rules (Rule B3).
15. **Example Image / Source**: MMOTU `teratoma` class; Radiopaedia [Ovarian Mature Cystic Teratoma (rID: 10452)](https://radiopaedia.org/articles/mature-cystic-ovarian-teratoma).

---

## 2.5. Other Benign Lesions (Serous/Mucinous Cystadenoma, Thecoma/Fibroma, Hydrosalpinx)
1. **Ultrasound Appearance**:
   - *Serous Cystadenoma*: Large, thin-walled, unilocular or paucilocular cyst with purely anechoic fluid and no solid tissue.
   - *Mucinous Cystadenoma*: Large multilocular cyst with numerous thin smooth septations and low-level internal mucus echogenicity.
   - *Thecoma / Ovarian Fibroma*: Solid, well-demarcated hypoechoic mass with smooth contours, low vascularity, and prominent dense acoustic posterior shadowing.
   - *Hydrosalpinx*: Elongated, tubular, fluid-filled structure with incomplete septa ("waist sign") and mucosal folds ("beads-on-a-string").
2. **Shape**: Ovoid, multiloculated, or tubular/sausage-shaped (hydrosalpinx).
3. **Size**: 30 - 200 mm.
4. **Echogenicity**: Anechoic (serous), low-level gelatinous (mucinous), or solid hypoechoic (thecoma/fibroma).
5. **Wall Characteristics**: Thin (< 3 mm), smooth outer and inner contours.
6. **Septations**: Thin (< 3 mm), smooth, regular partitions.
7. **Solid Components**: None in cystadenomas; 100% solid in thecoma/fibroma (distinguished by smooth border and posterior acoustic shadowing).
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 1-2 (Minimal to mild flow in thin septa).
10. **Acoustic Shadow**: Present in ovarian thecoma/fibroma (benign solid sign); absent in simple cystadenomas.
11. **Ascites**: Absent (except in rare Meigs syndrome associated with benign fibroma).
12. **IOTA Terminology**: Multilocular cyst with smooth walls / Benign solid tumor with acoustic shadowing.
13. **O-RADS Category**:
   - **O-RADS 2**: Hydrosalpinx / Peritoneal inclusion cyst (< 1% risk).
   - **O-RADS 3**: Multilocular cyst < 100 mm with thin smooth septa, Color Score 1-3 (1 - 9% risk); Solid lesion with smooth contour and acoustic shadowing, any size (1 - 9% risk).
14. **Reference Source**: ACR O-RADS US v2022 (Strachowski et al., 2023); IOTA Simple Rules (Rule B4, B5).
15. **Example Image / Source**: MMOTU `serous_cystadenoma`, `mucinous_cystadenoma`, `theca_cell_tumor` classes.

---

# SECTION 3: SUSPICIOUS LESIONS (O-RADS 4: INTERMEDIATE RISK 10% - <50%)

## 3.1. Complex Cystic Lesion / Multilocular Cyst with Solid Component
1. **Ultrasound Appearance**: Multilocular cystic mass containing >= 10 locules or thick, irregular internal septations (>= 3 mm) and focal solid nodules.
2. **Shape**: Multilobulated, complex irregular contours.
3. **Size**: Often > 50 - 100 mm.
4. **Echogenicity**: Mixed anechoic, ground-glass, and echogenic solid parenchyma.
5. **Wall Characteristics**: Irregular thickened wall (>= 3 mm) with nodular internal margins.
6. **Septations**: Multiple thick, irregular septations (>= 3 mm) with detectable internal vascularity.
7. **Solid Components**: Present (1 - 3 discrete solid components without acoustic shadowing).
8. **Papillary Projections**: Absent or 1 - 3 small projections (< 3 mm height).
9. **Doppler Vascularity**: Color Score 2-3 (Moderate flow within thick septa and solid elements).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Multilocular-solid tumor with thick irregular septa.
13. **O-RADS Category**: **O-RADS 4** (Multilocular cyst with solid component, Color Score 1-3, or multilocular cyst > 100 mm with Color Score 4; Risk 10 - 49%).
14. **Reference Source**: ACR O-RADS US v2022; IOTA ADNEX Model (Van Calster et al., BMJ 2014).
15. **Example Image / Source**: Radiopaedia [Borderline Ovarian Tumor (rID: 35128)](https://radiopaedia.org/articles/borderline-ovarian-tumours); MMOTU complex cases.

---

## 3.2. Cystic Lesion with 1-3 Papillary Projections
1. **Ultrasound Appearance**: Unilocular or multilocular cyst exhibiting 1 to 3 distinct solid fleshy papillary buds projecting from the cyst wall or septa into the lumen.
2. **Shape**: Cystic cavity containing focal endocystic projections.
3. **Size**: Variable (30 - 120 mm); papillary projection height >= 3 mm.
4. **Echogenicity**: Anechoic or low-level fluid containing intermediate/hyperechoic mural projections.
5. **Wall Characteristics**: Smooth outer wall with 1-3 focal internal papillary excrescences.
6. **Septations**: Variable (0 to few).
7. **Solid Components**: Papillary projections (defined by IOTA as solid outgrowth >= 3 mm height extending into cyst cavity).
8. **Papillary Projections**: **1 to 3 distinct projections** (demonstrating internal vessel flow on Color Doppler).
9. **Doppler Vascularity**: Color Score 2-3 (Color signal detectable inside papillary stalk).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Absent.
12. **IOTA Terminology**: Unilocular-solid tumor with 1-3 papillary projections.
13. **O-RADS Category**: **O-RADS 4** (Unilocular cyst with 1-3 papillary projections, any size, Color Score 1-3; Risk 10 - 49%).
14. **Reference Source**: ACR O-RADS US v2022; IOTA Simple Rules (Rule M3).
15. **Example Image / Source**: Radiopaedia [Ovarian Serous Borderline Neoplasm (rID: 29812)](https://radiopaedia.org/articles/ovarian-serous-borderline-tumour).

---

## 3.3. Solid Lesion with Smooth Contour (No Shadowing)
1. **Ultrasound Appearance**: Homogeneous or heterogeneous purely solid mass (>= 80% solid tissue) with a well-defined smooth outer contour, but **lacking acoustic posterior shadowing**.
2. **Shape**: Round, oval, or lobulated with sharp, smooth margins.
3. **Size**: Any size.
4. **Echogenicity**: Intermediate to hypoechoic solid tissue.
5. **Wall / Outer Margin**: Smooth, well-circumscribed.
6. **Septations**: N/A (entirely solid).
7. **Solid Components**: Entirely solid (>= 80% volume).
8. **Papillary Projections**: N/A.
9. **Doppler Vascularity**: Color Score 2-3 (Moderate internal vascular flow).
10. **Acoustic Shadow**: **Absent** (Crucial discriminator: presence of shadow classifies solid mass as O-RADS 3; absence elevates to O-RADS 4).
11. **Ascites**: Absent.
12. **IOTA Terminology**: Solid tumor with smooth outline, no acoustic shadows.
13. **O-RADS Category**: **O-RADS 4** (Solid tumor with smooth contour, no shadowing, Color Score 2-3; Risk 10 - 49%).
14. **Reference Source**: ACR O-RADS US v2022 (Strachowski et al., Radiology 2023 update).
15. **Example Image / Source**: Radiopaedia [Ovarian Dysgerminoma / Stromal Tumor (rID: 41203)](https://radiopaedia.org/articles/ovarian-dysgerminoma).

---

# SECTION 4: MALIGNANT LESIONS (O-RADS 5: HIGH RISK >= 50%)

## 4.1. High-Grade Serous Ovarian Carcinoma (Epithelial Carcinoma)
1. **Ultrasound Appearance**: Highly heterogeneous multilocular-solid or purely solid mass with markedly irregular borders, multiple fleshy vascular papillary fronds (>= 4), necrotic cystic spaces, chaotic branching internal neovascularization, and associated peritoneal carcinomatosis / ascites.
2. **Shape**: Highly irregular, nodular, poorly circumscribed.
3. **Size**: Usually large (> 60 - 200 mm).
4. **Echogenicity**: Inhomogeneous, mixed hypoechoic solid elements with anechoic hemorrhagic/necrotic debris.
5. **Wall Characteristics**: Irregular, thick, nodular, ill-defined outer margins infiltrating adjacent pelvic structures.
6. **Septations**: Thick, irregular, disorganized septa (>= 3 mm) with rich vascularity.
7. **Solid Components**: Extensive irregular solid components (>= 80% volume or large nodular components).
8. **Papillary Projections**: **>= 4 prominent papillary projections** with irregular surface and rich vascular flow.
9. **Doppler Vascularity**: **Color Score 4** (Strong, chaotic vascular flow with multiple color pixels, low-resistance high-velocity spectral Doppler).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: **Present** (Peritoneal fluid extending beyond pelvis, omental cake, peritoneal nodular implants).
12. **IOTA Terminology**: Multilocular-solid / Solid tumor with irregular contour, >= 4 papillary projections, Color Score 4, ascites present.
13. **O-RADS Category**: **O-RADS 5** (High risk of malignancy >= 50%; immediate gynecologic oncologist referral).
14. **Reference Source**: ACR O-RADS US v2022; IOTA Simple Rules (Rules M1, M2, M3, M4, M5); ESGO/ISUOG/IOTA/ESGE 2021 Consensus.
15. **Example Image / Source**: MMOTU `high-grade_serous` class; Radiopaedia [Ovarian Carcinoma (rID: 17290)](https://radiopaedia.org/articles/ovarian-carcinoma).

---

## 4.2. Metastatic Ovarian Carcinoma (Krukenberg Tumor)
1. **Ultrasound Appearance**: Bilateral, large, solid lobulated ovarian masses with well-demarcated bosselated margins, containing internal cystoid necrotic "moth-eaten" spaces and strong penetrating vascularity, typically secondary to gastric, colorectal, or breast adenocarcinoma.
2. **Shape**: Bilateral, multinodular, lobulated solid masses.
3. **Size**: 50 - 150 mm bilaterally.
4. **Echogenicity**: Heterogeneous solid stroma with discrete mucin-filled cystic honeycomb cavities.
5. **Wall Characteristics**: Bosselated, lobulated, intact fibrous capsule.
6. **Septations**: N/A (predominantly solid with necrotic cystic cavities).
7. **Solid Components**: >= 80% solid tissue.
8. **Papillary Projections**: None.
9. **Doppler Vascularity**: Color Score 3-4 (Rich central penetrating radial flow).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Frequently present (positive cytology).
12. **IOTA Terminology**: Solid tumor with irregular cystic degeneration, bilateral masses, ascites.
13. **O-RADS Category**: **O-RADS 5** (Solid tumor with irregular contour / Color Score 4 / ascites; > 50% risk).
14. **Reference Source**: ACR O-RADS US v2022; IOTA ADNEX Model (Secondary metastatic subgroup).
15. **Example Image / Source**: Radiopaedia [Krukenberg Tumor (rID: 12154)](https://radiopaedia.org/articles/krukenberg-tumour).

---

## 4.3. Other Malignant Ovarian Neoplasms (Endometrioid, Clear Cell, Granulosa Cell)
1. **Ultrasound Appearance**:
   - *Clear Cell Carcinoma*: Unilocular cyst with a large, solitary, highly vascular round solid mural nodule arising within a pre-existing endometrioma.
   - *Endometrioid Carcinoma*: Mixed complex cystic-solid mass with low-level background echogenicity, thick irregular septations, and papillary vascular projections.
   - *Adult Granulosa Cell Tumor*: Large, multilocular-solid mass with "Swiss-cheese" or "sponge-like" appearance due to multiple fluid-filled locules interspersed in solid cellular stroma, often with thickened endometrium due to hyperestrogenism.
2. **Shape**: Complex, lobulated, cystic-solid.
3. **Size**: 50 - 180 mm.
4. **Echogenicity**: Mixed heterogeneous tissue with solid vascular components.
5. **Wall Characteristics**: Irregular, thickened.
6. **Septations**: Multiple irregular thick septations.
7. **Solid Components**: Dominant vascular solid components.
8. **Papillary Projections**: Variable (1 - >= 4).
9. **Doppler Vascularity**: Color Score 3-4 (Abundant internal vascular signals).
10. **Acoustic Shadow**: Absent.
11. **Ascites**: Variable (Present in advanced stages).
12. **IOTA Terminology**: Unilocular-solid or Multilocular-solid with strong vascularization.
13. **O-RADS Category**: **O-RADS 5** (Unilocular cyst with >= 4 papillary projections, or solid irregular mass with Color Score 3-4; >= 50% risk).
14. **Reference Source**: ACR O-RADS US v2022; WHO Classification of Female Genital Tumours (5th Ed).
15. **Example Image / Source**: Radiopaedia [Ovarian Clear Cell Carcinoma (rID: 48920)](https://radiopaedia.org/articles/ovarian-clear-cell-carcinoma).

---

# SECTION 5: SUMMARY COMPARISON: MORPHOLOGICAL FEATURES & MACHINE LEARNING UTILITY

| Feature Name | Clinical Definition (IOTA / O-RADS) | Diagnostic Significance | AI / ML Extracted Feature | Feature Value for ML Model |
|---|---|---|---|---|
| **Max Caliper (D_max)** | Largest lesion diameter across orthogonal planes | Differentiates physiological follicle (< 30 mm) vs cyst (> 30 mm) | Euclidean bounding distance from segmentation mask | **High (P0)**: Threshold-based stratification |
| **Solid Component Volume** | Non-cystic tissue with acoustic impedance of parenchymal tissue | Strongest predictor of malignancy (> 0 mm increases risk) | Segmented solid sub-region mask ratio (V_solid / V_total) | **Critical (P0)**: Directly separates O-RADS 2/3 from 4/5 |
| **Papillary Projection Count** | Solid outgrowth >= 3 mm height into cyst cavity | >= 4 projections triggers O-RADS 5 / IOTA M-rule | Morphological peak detection on inner boundary contour | **Critical (P0)**: Key biomarker for borderline/malignant tumors |
| **Wall & Septal Regularity** | Thickness >= 3 mm vs < 3 mm; smooth vs nodular | Thin smooth = Benign; Thick irregular = Malignant | Edge gradient variance & curvature derivative along boundary | **High (P1)**: Strong discriminative texture feature |
| **Acoustic Shadowing** | Distal attenuation behind dense tissue | Pathognomonic for Benign Dermoid / Fibroma / Thecoma | Ray-casting posterior column intensity drop behind lesion | **Critical (P0)**: Prevents false positive malignancy classification |
| **Color Score (1-4)** | 1=No flow, 2=Minimal, 3=Moderate, 4=Chaotic/Strong | High flow (CS 3-4) indicates tumor angiogenesis | Color pixel density / Power Doppler histogram entropy | **High (P1)**: Multi-modal fusion input (Doppler/CEUS) |
| **Internal Echogenicity** | Anechoic, Ground-glass, Reticular, Dermoid mesh | Separates simple cyst vs endometrioma vs dermoid | Gray-Level Co-occurrence Matrix (GLCM) & Deep Texture Embeddings | **High (P1)**: Sub-typing benign pathological classes |
| **Ascites & Free Fluid** | Fluid outside pouch of Douglas / omental cake | Secondary sign of peritoneal malignancy | Pelvic fluid segmentation outside ovarian boundary | **High (P1)**: Triggers immediate O-RADS 5 alert |
