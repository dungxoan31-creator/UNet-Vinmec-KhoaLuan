"""Compatibility entry point for the Milestone 1 Validation sanity check."""

import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from scripts.sanity_check_m1_validation import run

    result = run(root, root / "evaluation/m1_validation_sanity_check.json")
    print(f"{result['status']}: {result['validation_count']} Validation images")
