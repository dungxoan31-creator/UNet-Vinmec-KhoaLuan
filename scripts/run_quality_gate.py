"""
Automated Quality Gate Runner for Ultrasound AI Pipeline:
Executes all verification tests and outputs structured validation results.
"""

import os
import sys
import traceback

if sys.stdout.encoding != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

# Ensure root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_ai_pipeline_integrity import (
    test_dataset_audit_completeness,
    test_patient_level_splits_zero_leakage,
    test_preprocessing_and_normalization_consistency,
    test_label_mapping_consistency,
    test_caliper_geometry_formulas,
    test_uncertainty_quantification_entropy,
    test_anti_fake_no_hardcoded_predictions
)

def run_all_quality_gate_tests():
    print("=" * 70)
    print("       RUNNING AUTOMATED QUALITY GATE & PIPELINE INTEGRITY TESTS       ")
    print("=" * 70)

    tests = [
        ("Dataset Audit Completeness (1,372 cases)", test_dataset_audit_completeness),
        ("Patient-Level Zero Data Leakage Verification", test_patient_level_splits_zero_leakage),
        ("Preprocessing & Normalization Consistency", test_preprocessing_and_normalization_consistency),
        ("Strict Label Mapping (0=Background, 1=Lesion)", test_label_mapping_consistency),
        ("Caliper Geometry & ISUOG Volume Mathematics", test_caliper_geometry_formulas),
        ("Uncertainty Shannon Entropy Quantification", test_uncertainty_quantification_entropy),
        ("Anti-Fake Dynamic Neural Pass Verification", test_anti_fake_no_hardcoded_predictions),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1

    print("-" * 70)
    print(f"QUALITY GATE RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed/len(tests)*100:.1f}%)")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_quality_gate_tests()
