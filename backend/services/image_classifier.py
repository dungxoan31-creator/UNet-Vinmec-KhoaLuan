"""Hash-verified, image-level MMOTU research classification. Never assigns O-RADS."""
import hashlib
import io
import threading
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision.models import resnet34

from backend.core.mmotu_labels import MMOTU_8_CLASSES

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / 'checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_02_balanced_256_finetune_lr5e5/mmotu_resnet34_8class_best.pth'
CHECKSUM = '35737b75c89b983a5b51846aba45aebea3144b8d09f70f1e3cfc1f08b1118a92'


def classification_tensor(image):
    if not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8:
        raise ValueError('Expected nonempty uint8 image')
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('Unsupported image channels')
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    h, w = rgb.shape[:2]
    scale = min(256 / w, 256 / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    canvas = np.zeros((256, 256, 3), dtype=np.uint8)
    x, y = (256 - nw) // 2, (256 - nh) // 2
    canvas[y:y+nh, x:x+nw] = resized
    tensor = torch.from_numpy(canvas.transpose(2, 0, 1).copy()).float() / 255
    return ((tensor - torch.tensor([.485, .456, .406])[:, None, None]) / torch.tensor([.229, .224, .225])[:, None, None]).unsqueeze(0)


class ResearchImageClassifier:
    def __init__(self, checkpoint_path=None):
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path is not None else None
        self.model = None
        self.lock = threading.Lock()

    def predict(self, image):
        # CPU and a single bounded critical section avoid competing for segmentation VRAM.
        if not self.lock.acquire(timeout=2):
            return {'status': 'UNAVAILABLE', 'reason': 'CLASSIFIER_BUSY', 'research_use_only': True}
        try:
            if self.model is None:
                snapshot = (self.checkpoint_path or CHECKPOINT).read_bytes()
                if hashlib.sha256(snapshot).hexdigest() != CHECKSUM:
                    raise ValueError('Checkpoint checksum mismatch')
                model = resnet34(weights=None)
                model.fc = torch.nn.Linear(model.fc.in_features, 8)
                model.load_state_dict(torch.load(io.BytesIO(snapshot), map_location='cpu', weights_only=True), strict=True)
                self.model = model.eval()
            with torch.inference_mode():
                probs = self.model(classification_tensor(image)).softmax(dim=1)[0]
            if not torch.isfinite(probs).all():
                raise ValueError('Nonfinite classifier output')
            values, indices = probs.topk(2)
            abstain = values[0].item() < .60 or (values[0] - values[1]).item() < .15
            return {
                'status': 'ABSTAIN' if abstain else 'PREDICTED',
                'suggested_label': None if abstain else MMOTU_8_CLASSES[indices[0].item()],
                'probabilities': dict(zip(MMOTU_8_CLASSES, probs.tolist(), strict=True)),
                'research_use_only': True,
                'score_type': 'uncalibrated_image_class_probability',
                'requires_clinician_confirmation': True,
                'provenance': {'model': 'MMOTU ResNet34 8-class', 'checkpoint_sha256': CHECKSUM,
                               'preprocessing': 'rgb-lab-clahe-letterbox256-imagenet-v1', 'device': 'cpu'},
            }
        except (OSError, ValueError, RuntimeError):
            return {'status': 'UNAVAILABLE', 'reason': 'CLASSIFIER_LOAD_OR_INFERENCE_FAILED', 'research_use_only': True}
        finally:
            self.lock.release()


image_classifier = ResearchImageClassifier()
