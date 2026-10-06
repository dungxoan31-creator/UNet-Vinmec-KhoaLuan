# Stack kỹ thuật và cách chạy

Versions below were read from the repository `.venv` on 2026-10-05. `requirements.txt` contains minimum dependency constraints; `uv.lock` records the locked environment.

## Runtime chính

| Layer | Packages / version in `.venv` | Usage |
| --- | --- | --- |
| Python | 3.12.10 | Runtime |
| Deep learning | PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124 | Standard U-Net training and inference |
| API | FastAPI 0.141.1, Uvicorn 0.54.0, Starlette 1.7.0 | HTTP application and static UI hosting |
| Schema and persistence | Pydantic 2.13.5, SQLAlchemy 2.1.1, SQLite | Request validation and local case/review storage |
| Image processing | OpenCV 5.0.0.93, Pillow 12.3.0 | Grayscale decode, CLAHE, Letterbox and mask operations |
| Data | NumPy 2.5.2, pandas 3.0.6, Albumentations 2.0.8 | Training data loading and augmentation |
| Medical image input | pydicom 3.0.2 | DICOM decoding where supported by the backend |
| QA | pytest 9.1.1, Ruff 0.16.9 | Automated tests and lint checks |

## Application architecture

- **Frontend:** HTML, CSS and browser JavaScript with Canvas editing in `frontend/`.
- **Backend:** FastAPI routers in `backend/app/routers/`; inference and preprocessing services in `backend/services/`.
- **Model:** Standard U-Net at `backend/models/unet.py` is the default configured in `evaluation/selected_model.json`. Validation-selected U-Net++ uses Segmentation Models PyTorch 0.5.0 / ResNet34 and a separate model lock in `evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json`. `backend/app/config.py` verifies checkpoint SHA-256.
- **Persistence:** SQLAlchemy models with local SQLite database for prototype case and review records.
- **Training:** PyTorch training utilities under `ai_training/`; split CSVs and snapshots under `ai_training/splits/`.

## Inference contract

The selected model configuration uses one-channel grayscale input, CLAHE, 512×512 Letterbox, normalization by 255, threshold 0.5 and no morphology postprocessing. The training split and checkpoint evidence are recorded alongside the model artifacts. Do not compare the 382-image Test metrics for the 2026-10-03 retraining split with historical Mốc 1 metrics as if they came from one evaluation protocol.

The U-Net++ lock additionally applies grayscale mean 0.449 / std 0.226 after division by 255. The controlled Standard U-Net comparator uses that same normalization. Current runtime versions and benchmark commands are preserved in the model lock directory; the table above is a historical environment snapshot.

Latest full-suite verification on 2026-10-06: 67 passed / 8 failed because M1 data paths are absent. The isolated U-Net++ browser smoke passed. These observations do not constitute clinician usability or patient-level independence evidence.

Dice, IoU, Precision, Recall and Specificity describe pixel segmentation. They do not represent clinical diagnostic accuracy. No clinical category is inferred from the segmented region.

## Run from repository root

```powershell
$env:PYTHONPATH = "."
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the web prototype.

```powershell
$env:PYTHONPATH = "."
pytest -q
ruff check .
```

For dependency changes, update both `requirements.txt` and `uv.lock`, then verify the environment with the test and lint commands above.
