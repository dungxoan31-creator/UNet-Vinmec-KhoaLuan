# v2.1 Acceptance Baseline — 2026-10-26

## Release scope

The accepted v2.1 production scope is research-use-only ovarian ultrasound lesion segmentation, source-coordinate geometric measurement, and clinician-controlled HITL review. Model outputs in the production path remain segmentation masks and measurements. An experimental image-level MMOTU 8-class classifier was implemented and trained on 2026-10-27; it remains outside the production inference path and does not provide malignancy probabilities or model-generated O-RADS/PCOS diagnoses.

`ai_training/train_classifier_8class.py` trains the separate research classifier from official image-level MMOTU global-category labels. Its validation partition is used for model selection, patient identity is unavailable, and its results must not be represented as patient-independent or clinical performance. A checkpoint copied into the segmentation weights directory does not activate this classifier. O-RADS US and IOTA checks consume clinician-entered descriptors only; image heuristics do not mark an examination complete or convert unavailable observations into negative findings.

## Closed review items

| ID | Review item | Baseline decision / implementation | Verification |
|---|---|---|---|
| R02 | Box Prompt Letterbox scale | Measurement uses `measure_source_mask` and the source image calibration after inverse Letterbox mapping. | Current API probe compares endpoint diameter and area with source-coordinate measurements. |
| R03 | Diagnosis-only Active Learning feedback | New or changed lesion type, O-RADS, and morphology text are sent and persisted as clinician overrides; the server independently detects changes against the previous saved review. | API probe and review-batch regression test verify queue insertion with unchanged mask. |
| R04 | Invented PCOS probability | No default probability. A valid finite source probability is printed; when absent, the report uses a qualitative count-based suggestion without a percentage. Invalid probabilities are omitted. | Report tests and API probe. |
| R05 | Watershed border peaks | `exclude_border=False`; every connected component above the minimum area receives a marker before watershed. | Border-plus-interior synthetic mask test and clinical probe. |
| R06 | Missing/inapplicable findings | Missing follicle input stays `None`; subthreshold follicle count without volume remains incomplete; empty-mask descriptors are `not_applicable` or `unavailable`; CDSS runs only on explicit clinician findings and remains incomplete when required inputs are absent. | Clinical probe and CDSS integration tests. |
| R07 | Invalid probability vectors | Non-finite, out-of-range, unknown-class, or non-normalized vectors abstain without a benign label or malignancy result. | Parameterized diagnostic-engine tests and clinical probe. |
| R08 | CDSS abort button state | Cancellation restores the idle RUO button text and current editability state. | Frontend cancellation test. |
| R09 | Same-side reselection | Selecting the already active side/image returns without resetting clinical inputs. | Chrome workstation E2E asserts all active-side inputs survive L→L. |
| R10 | CDSS missing-field labels | Known O-RADS, IOTA, and patient-context field/status values render in Vietnamese clinical language; unknown values are rendered as readable text. | Frontend panel tests. |
| R11 | Numeric semantic guard | `numbers_match` preserves numeric value/unit pairs and multiplicity, preventing values such as 2 mm and 25 mm from swapping while retaining the same token set. | Unit-pair regression test. |
| R12 | Model/CLI scope conflict | Production remains segmentation-only RUO; research classifier training is separate and is not activated by weights. | `MODEL_CARD.md`, classifier isolation and provenance. |
| R13 | Test oracle and upload concurrency | Browser `ERR_ABORTED` is accepted only when the page's fetch `AbortSignal` was observed aborting the same URL/method. Upload preflight read state is released before decode to avoid holding SQLite snapshots at a concurrency barrier. | Comprehensive E2E and full duplicate-upload tests. |
| R14 | Lease expiry semantics | Lease is revalidated and renewed after decode, before upload DB mutation. Expiry at that gate returns HTTP 423 and removes the staged file. After renewal, lease, image, and audit writes remain in one transaction through commit/rollback. | Lease-expiry-during-decode regression test. |

## Verification record

All evidence must be read from the same source snapshot as this baseline. Historical results in `docs/multi-role-review-v21-2026-10-26.md` describe the pre-fix review snapshot and are not acceptance evidence.

| Command / probe | Result |
|---|---|
| `.venv/Scripts/python.exe artifacts/v21-review-2026-10-26/current-api-probes.py` | PASS — 200 review saves; diagnosis-only edit queued; source and endpoint measurement both 19.9 mm / 3.114 cm²; 85% absent; swapped number/unit rejected; role transition denied with 403. |
| `.venv/Scripts/python.exe artifacts/v21-review-2026-10-26/clinical-probe.py` | PASS — NaN/Inf/range/class/total guards abstain; border component counted; missing follicle stays unavailable; incomplete clinician descriptors stay incomplete. |
| Targeted backend regression set | PASS — 72 tests (including all `test_duplicate_upload.py` and `test_review_batch.py`) in 10.23 s. |
| `npm test` | PASS — 87 tests. |
| `npm run syntax-check` | PASS — 49 JavaScript modules. |
| Full backend suite (`.venv/Scripts/python.exe -m pytest tests/ -q --tb=short`) | PASS — 1,114 passed, 2 skipped in 142.46 s. The skips remain explicit. |
| Five Google Chrome Playwright scripts | PASS — 5/5 exit code 0 in `artifacts/v21-review-2026-10-26/acceptance-r02-r14-final-pcos/browser-results.json`; per-script logs are in the same directory. |

## Workstation implementation update — 2026-10-27

- Intake accepts up to 20 static images per ovary, confirms laterality per image, and permits a one-sided study only after the contralateral status is recorded. Cine-loop review is outside this prototype scope.
- Clinicians can place D1/D2 calipers with two source-image points. The report uses saved calipers ahead of mask proxies, keeps area separately mask-derived, and uses pixels when calibration is unavailable.
- O-RADS/IOTA remain clinician-entered. B-mode-only input does not supply Doppler Color Score; the production path does not infer malignancy, PCOS, or a complete examination from a mask.
- The report is RUO, discloses the lack of clinical validation and digital signature, and prints one summary page plus one evidence page per image.
- E2E verification: `npm run test:e2e:roundtrip` PASS (two synthetic images, persisted caliper, 3-page A4, 0 pageerror); `npm run test:e2e:safety` PASS (15 checks, 0 pageerror). Full suites: 1,122 Python passed / 2 skipped and 90 frontend passed.
- The original QA snapshot's dataset gate remains a historical `BLOCKED` result; it was not a prerequisite for exploratory image-level training. No patient-level independence or clinical performance claim is made.

## Classifier research training — 2026-10-27

- Implemented the separate ResNet34 training pipeline using the official MMOTU 2D global-category labels: 1,000 training images and 469 validation images. Patient IDs are unavailable; filenames and image hashes were checked for train/validation overlap.
- Initial class-weighted run: accuracy 0.4499. Balanced-sampling run: accuracy 0.5821. The accuracy search's best observed trial (trial 2, epoch 21) reached accuracy 0.6844, macro-F1 0.6056, balanced accuracy 0.5996; high-grade serous support 15 (recall 0.6000, precision 0.4091). It has a substantial train/validation macro-F1 gap (0.9552 vs 0.6056). Five additional trials used the same image-level validation partition; this is a repeatedly tuned model-selection score, not an independent test result.
- The weights are not loaded by the clinical workstation. No malignancy probability, O-RADS category, calibration, patient-independent result, or clinical effectiveness claim is produced.

## Remaining limits

- Verification uses synthetic images, synthetic records, and isolated test databases. It does not validate clinical accuracy or usability with patients or clinicians.
- The segmentation checkpoint's historical validation metrics do not establish independent patient-level performance; independent test and clinician-validation gates remain blocked as stated in the model card.
- The research classifier has no independent evaluation, calibration evidence, or diagnostic release gate; it is not accepted for clinical use.
- This baseline closes the listed review items only. It is not a claim that no other defects remain.
