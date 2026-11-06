# Model Card — Ovarian Ultrasound RUO Research Prototype

**Repository scope checked:** 2026-10-29. This card describes repository configuration; it is not a clinical performance claim.

## Intended use

Research-only segmentation of ovarian ultrasound images to support a clinician-reviewed Human-in-the-Loop workflow. The model produces a pixel mask. It does not diagnose a cyst, malignancy, cancer, or treatment need. A qualified clinician retains decision authority.

## v2.1 acceptance scope

The current v2.1 software acceptance baseline covers **RUO lesion segmentation and clinician-controlled geometric measurement**. An image-level MMOTU 8-class research classifier has since been implemented and trained, but it is separate from the production inference path and does not emit a diagnosis, malignancy probability, O-RADS category, or treatment recommendation. The classifier has no patient identity mapping, independent diagnostic validation, calibration evidence, or clinical release approval.

O-RADS US and IOTA outputs require applicable descriptors entered and confirmed by a clinician. Pixel-derived heuristics are not treated as clinician observations or as a completed ultrasound examination. Unknown, unavailable, and not-applicable findings remain distinct from negative findings.

## Selected candidate

| Field | Repository value |
|---|---|
| Architecture | U-Net++ with ResNet34 encoder + scSE attention (Spatial & Channel Squeeze-and-Excitation) |
| Checkpoint | `checkpoints/boosted_unetplusplus_scse_2026-10-27/boosted_resnet34_scse_best.pth` |
| SHA-256 | `67624bbb0e50e236df7b5c82736eaadab1ff1fff5547c5e813bca545c2dd2045` |
| Pretraining source | Stage 1 ultrasound domain pretraining on MMOTU 2D pairs (1,000 pairs, zero-shot transfer) |
| Loss function | Advanced Hybrid Loss (0.5 Focal-Tversky [α=0.3, β=0.7, γ=0.75] + 0.3 SoftDice + 0.2 BCE) |
| Input | Grayscale, Letterbox 512×512; CLAHE clip 2.0, grid 8×8 |
| Inference | Horizontal-flip TTA; probability threshold 0.4; no morphology post-processing |
| Training selection | Two-stage fine-tuned candidate, converged at epoch 7 (early stopped epoch 13), seed 42 |

Source of these values: [`evaluation/selected_model.json`](evaluation/selected_model.json).

## Reported validation-set pixel-mask metrics

The selected-model metadata reports segmentation pixel-mask metrics evaluated on 541 images in the image-level validation selection split:
- **Recall-oriented validation operating point (Flip TTA, threshold 0.40)**:
  - Mean Dice: **0.8351** (+1.66% over historical baseline 0.8185)
  - Mean IoU: **0.7526** (+1.88% over historical baseline 0.7338)
  - Mean segmentation recall (pixel masks): **0.8726** (+1.93% over historical baseline 0.8533)
  - Mean Precision: **0.8430** (+0.95% over historical baseline 0.8335)
  - Mean Specificity: **0.9810**
- **Peak Standalone Configuration (Flip TTA, Threshold 0.50)**:
  - Mean Dice: **0.8356** (+1.71% over historical baseline)
  - Mean IoU: **0.7538** (+2.00% over historical baseline)
  - Mean Recall: **0.8650**
  - Mean Precision: **0.8508**
- **Native Checkpoint (No TTA, Threshold 0.50)**:
  - Mean Dice: **0.8313**, IoU: **0.7471**, Recall: **0.8714**, Precision: **0.8364**
- **Multi-Model Upper-Bound Ensemble (0.5 Boosted scSE + 0.5 Baseline, Threshold 0.45)**:
  - Mean Dice: **0.8431** (+2.46% over historical baseline)
  - Mean IoU: **0.7622** (+2.84% over historical baseline)
  - Mean Recall: **0.8752** (+2.19% over historical baseline)
  - Mean Precision: **0.8533** (+1.98% over historical baseline)

These are image-level pixel metrics for the validation selection set. They are not patient-level sensitivity, specificity, or independent test results.

The repository records source patient identity as unverified, the independent test gate as `BLOCKED`, and clinician validation as not conducted. The 402-image technical benchmark is marked simulated and does not establish independent patient performance. Do not present either set of values as clinical effectiveness.

The selected checkpoint's legacy `run_summary.json` has no split directory, split-integrity result, or train/validation/test CSV and manifest hashes. Its `test_split_accessed: false` field does not identify whether test files were read for integrity checking or whether they were used for training/selection. The current generic trainer verifies image-level integrity by reading and decoding all three partitions, then trains on train and uses validation for checkpoint selection; current run summaries now record the exact split-file hashes and separate test integrity inspection from test use. This change cannot reconstruct the selected checkpoint's historical input split. Treat its exact training-data provenance and test-use semantics as **unverified**.

The selected checkpoint records Advanced Hybrid Loss, whereas the project master scope requires Dice + BCE Combo Loss. This is an unresolved scope-compliance blocker; neither the manifest nor checkpoint should be relabeled to conceal the difference. Selection or retraining of a compliant candidate requires separate evidence.

## Experimental image-level classifier

| Field | Value |
|---|---|
| Task | MMOTU 2D image-level global-category classification across 8 dataset classes |
| Architecture | ResNet34 with ImageNet initialization |
| Training / validation | Official 1,000-image train and 469-image validation partitions |
| Input | RGB, 384×384 aspect-preserving letterbox, luminance CLAHE, ImageNet normalization; no manual masks |
| Best checkpoint | `checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_02_balanced_256_finetune_lr5e5/mmotu_resnet34_8class_best.pth` |
| Checkpoint SHA-256 | `35737b75c89b983a5b51846aba45aebea3144b8d09f70f1e3cfc1f08b1118a92` |
| Best observed validation selection | Trial 2, epoch 21; accuracy 0.6844, macro-F1 0.6056, balanced accuracy 0.5996 |
| Training strategy | 256×256, balanced sampler with replacement, CrossEntropyLoss, encoder LR 0.00005, classifier-head LR 0.0005 |
| High-grade serous class | Validation support 15; recall 0.6000, precision 0.4091 |

The prior best run scored accuracy 0.5821 and macro-F1 0.5517. The accuracy search tested five additional configurations and stopped after three consecutive trials failed to beat the observed best. Trial 2 reached training macro-F1 0.9552 versus validation macro-F1 0.6056, a substantial generalization gap. Repeated selection on this same validation partition makes 0.6844 a tuning score, not an unbiased performance estimate. MMOTU patient IDs are unavailable in this local dataset, so image-level separation does not establish patient-independent results. These exploratory metrics are not evidence for clinical diagnosis or malignancy risk. See `checkpoints/mmotu_8class_accuracy_search_2026-10-27/search_results.json` and the run directories for full provenance. The dataset redistribution license has not been established by the code repository license; confirm data terms before redistribution.

## Experimental segmentation pretraining — MMOTU Stage 1

| Field | Value |
|---|---|
| Task | Binary pixel-mask segmentation on MMOTU OTU_2d |
| Architecture | U-Net++ with ResNet34 encoder initialized from ImageNet |
| Split | Official image-level lists: 1,000 train / 469 validation; SHA-256 overlap 0 |
| Training | 10 epochs, seed 42, batch size 2, AdamW 2e-4 / weight decay 1e-4 |
| Loss | 0.5 Focal-Tversky (alpha 0.3, beta 0.7, gamma 0.75) + 0.3 SoftDice + 0.2 BCEWithLogits |
| Input | Grayscale, Letterbox 512×512, CLAHE clip 2.0, ImageNet grayscale normalization |
| Best checkpoint | `checkpoints/boosted_unetplusplus_multi_source_2026-10-27/stage1_mmotu/boosted_unetplusplus_mmotu_stage1_best.pth` |
| Checkpoint SHA-256 | `095f80479e31798bc62721eb17c21f99c70079d694277f0fd987c92cfa75333f` |
| Best epoch | 8 of 10 |
| Best validation metrics | Dice 0.8312, IoU 0.7472, recall 0.8867, precision 0.8275, specificity 0.9832 |

These are image-level pixel-overlap metrics on the MMOTU validation split at threshold 0.5. They are not diagnostic accuracy, patient-independent validation, or Vinmec results. No test partition was accessed. The classifier categories were not used as segmentation diagnoses. Dataset redistribution terms remain unverified; this checkpoint is research-only and is not the selected inference checkpoint.

Stage 2 MMOTU/Vinmec co-training and Stage 3 Vinmec target fine-tuning are blocked because the source-specific Vinmec image/mask files are absent. The legacy path resolver can alias Vinmec paths into the local MMOTU folder; the new trainer rejects that alias and refuses to treat matching filenames as Vinmec provenance. See [`docs/external-source-audit-2026-10-27.md`](docs/external-source-audit-2026-10-27.md) and `checkpoints/boosted_unetplusplus_multi_source_2026-10-27/pipeline_status.json`.

## Important limitations and safeguards

- Patient identity linkage and independent external evaluation have not been verified; patient-independent and clinical performance claims remain blocked.
- Pixel overlap metrics do not establish diagnostic accuracy or histopathology.
- Input quality, laterality, calibration, segmentation boundaries, and report content require human review.
- Physical measurements are unavailable unless valid image calibration is present; pixel units must not be presented as mm or cm.
- O-RADS US and IOTA classification require their applicable clinical descriptors and scope. A segmentation mask alone is insufficient.
- Prototype operation is not approved for patient-care decisions, surgery, or treatment planning.

## Source records

- [`evaluation/selected_model.json`](evaluation/selected_model.json)
- [`evaluation/milestone_3_final/report/limitations.md`](evaluation/milestone_3_final/report/limitations.md)
- [`evaluation/milestone_3_final/report/release_status.json`](evaluation/milestone_3_final/report/release_status.json)

