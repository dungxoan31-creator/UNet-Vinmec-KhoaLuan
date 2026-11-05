"""Compatibility exports for training; label order is owned by the runtime core."""

from backend.core.mmotu_labels import MMOTU_8_CLASSES, mmotu_class_name

__all__ = ["MMOTU_8_CLASSES", "mmotu_class_name"]
