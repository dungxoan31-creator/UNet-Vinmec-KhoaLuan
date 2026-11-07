"""Write a patient-free AUD-020 comparison of current policy and ACR sizing."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# noqa: E402 - make the repository package importable when invoked as a script.
from backend.services.cdss_engine import CDSSReasoningEngine


def _follicle_case(diameter_mm: float) -> dict:
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": diameter_mm,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "physiologic_lesion_type": "follicle",
        "physiologic_morphology_confirmed": True,
    }


def build_rows() -> list[dict[str, str]]:
    engine = CDSSReasoningEngine()
    rows = []
    for diameter in (29.9, 30.0, 30.1):
        result = engine.evaluate_case(_follicle_case(diameter), {"is_premenopausal": True})
        if diameter <= 30.0:
            acr_descriptor = "Premenopausal physiologic follicle ≤3 cm; O-RADS 1 descriptor"
            proposed_effect = (
                "Eligible only for the existing clinician-confirmed follicle path after local sign-off; "
                "size alone does not establish morphology"
            )
        else:
            acr_descriptor = "Beyond the physiologic follicle size descriptor; morphology-based assessment required"
            proposed_effect = "No inclusive-boundary change; do not infer another O-RADS category from size alone"
        rows.append(
            {
                "diameter_mm": f"{diameter:.1f}",
                "current_project_status": result["status"],
                "current_project_category": result["orads_stratification"].get("category") or "",
                "acr_v2022_descriptor": acr_descriptor,
                "proposed_effect_if_signed_off": proposed_effect,
                "fixture_type": "synthetic_boundary_case_no_patient_data",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New CSV path; existing files are never overwritten")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "diameter_mm",
        "current_project_status",
        "current_project_category",
        "acr_v2022_descriptor",
        "proposed_effect_if_signed_off",
        "fixture_type",
    ]
    try:
        rows = build_rows()
        with output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except FileExistsError:
        parser.error(f"Refusing to overwrite existing output: {output}")
    print(f"Wrote {len(rows)} synthetic boundary rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
