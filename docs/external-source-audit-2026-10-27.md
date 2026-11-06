# External source and data audit — 2026-10-27

## Scope and handling

All 15 repositories named in the integration request were shallow-cloned under the Git-ignored `external_sources/` directory. Commits below pin the exact inspected snapshots. No upstream training scripts were run, and no external code was installed with `pip install -e`. A local scan found no `.pth`, `.pt`, `.ckpt`, `.safetensors`, or `.onnx` model checkpoints and no Git LFS-managed files in the clones. `MONAI` and `timm` were already available in `.venv`; `einops` was installed there.

Repository code licensing is not treated as a license for images, annotations, or trained weights. Dataset terms remain unverified where the upstream repository does not state them. The downloaded files remain local and are not redistributed.

- **[VERIFIED]** Clone presence, commit IDs, and license-file presence were checked locally.
- **[PARTIALLY VERIFIED]** Dataset and checkpoint reuse rights remain unresolved unless explicitly stated by a separate upstream data/weight license.

## Repository inventory

| Repository | Inspected commit | Code license in clone | Integration decision |
| --- | --- | --- | --- |
| `cv516Buaa/MMOTU_DS2Net` | `be8455e` | Apache-2.0 | Use only the local OTU_2d image/mask pairs and official image-level train/validation lists for research segmentation. Dataset redistribution terms are not established by the code license. |
| `SonBH0410/SovaSeg-Net` | `fdb5ec3` | No license file | Excluded as a training source. Its README points to the same 1,469-image OTU-2D collection; it is not additional independent data. |
| `phamthiloanhd/CSA-SegNet` | `7a719e9` | No license file | Code not incorporated; reuse permission is not established. |
| `ShaunSpinelli/ultrasound_ovarian_seg` | `3cddd76` | No license file | Excluded pending rights and image-level SHA-256 overlap audit; no incremental images were assumed. |
| `openmedlab/USFM` | `960a1e1` | No license file | Not loaded: no checkpoint was present, and its architecture is not a drop-in ResNet34 encoder state dict. |
| `MacDunno/TinyUSFM` | `f3096e9` | No license file | Not loaded: no checkpoint was present; no weights were imported. |
| `CAMMA-public/UltraSam` | `ff3157b` | CC BY-NC-SA 4.0 | Excluded from the model pipeline because the license is non-commercial/share-alike and this hospital deployment context has not had legal clearance. |
| `xianlin7/SAMUS` | `030ed07` | MIT | Code is available locally, but no checkpoint was present and the SAM-style weights are not a compatible ResNet34 encoder state dict. |
| `XZheng0427/OpenUS` | `b6508c8` | No license file | Not incorporated; no checkpoint was present and reuse rights were not established. |
| `bowang-lab/MedSAM` | `d71e8a1` | Apache-2.0 | Framework code was inspected but not loaded; no local checkpoint was present. |
| `haidary99/PCOS_classification` | `bef3e76` | No license file | Excluded from segmentation: classification labels do not provide pixel masks, and reuse rights are not established. |
| `sarah-antillia/EfficientDet-Augmented-Ovarian-Ultrasound-Images` | `ffb633c` | Apache-2.0 | Excluded from segmentation: the repository is detection/augmentation-oriented, and code license does not establish rights or label compatibility for its images. |
| `MIC-DKFZ/nnUNet` | `1489d74` | Apache-2.0 | Benchmark framework only; not trained in this run. |
| `Project-MONAI/MONAI` | `76015b5` | Apache-2.0 | Existing installed library; no external repository code was imported into the trainer. |
| `Xiaotong66/ORADS-LLM-Pipeline` | `950a5f9` | No license file | Excluded from CDSS. It is not used to infer O-RADS or malignancy risk. |

## Data verification and training boundary

- Local `dataset/2d` contains 1,469 JPG images and 2,938 PNG masks, with canonical and `_binary` variants.
- `scripts/prepare_mmotu_segmentation_splits.py` selects the binary mask variant and checks dimensions, decodability, binary values, variant agreement, source label coverage, file hashes, and image SHA-256 separation.
- The generated image-level split contains 1,000 training and 469 validation pairs, matching the upstream label lists. Patient identity is unavailable; this is not patient-independent validation.
- SovaSeg's published description references the same OTU-2D cohort, so its records are not counted again. No unverified external images were mixed into training.
- The Vinmec split manifest exists, but its image and mask paths are absent in this workspace. Stage 2 co-training and Stage 3 Vinmec-only fine-tuning therefore cannot run here. The trainer refuses those stages when the files are absent or invalid and does not open the Vinmec test split.
- The repository has a legacy path resolver that can map Vinmec path aliases to `dataset/2d`. Since `dataset/2d` is MMOTU in this workspace, the new training pipeline bypasses that alias when checking Vinmec provenance; same-named files are rejected as Vinmec evidence.
- The current research model uses an ImageNet ResNet34 initialization because no compatible, licensed ultrasound checkpoint is locally available. Results from MMOTU must not be described as Vinmec clinical performance.
- Stage 1 completed 10 epochs on the MMOTU training split and selected epoch 8 by validation Dice (0.8312; IoU 0.7472). The checkpoint SHA-256 is recorded in `checkpoints/boosted_unetplusplus_multi_source_2026-10-27/stage1_mmotu/run_config.json`; this is a research pretraining artifact, not the selected inference model.
