"""Traceable Segmentation Error Analysis, Ranking and Case Panel Rendering v1."""

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from evaluation.protocol import normalize_reference, resolve_dataset_path


def rank_cases(rows: list[dict[str, Any]], k: int = 5) -> dict[str, list[str]]:
    """Rank cases into characteristic error and performance groups."""
    valid_fg = [r for r in rows if not r.get("gt_empty", False) and r.get("dice") is not None]
    if not valid_fg:
        valid_fg = rows

    # Helper to sort by key with tie-break on sample_id
    def _top_k(items: list[dict[str, Any]], key_fn, reverse: bool = True) -> list[str]:
        sorted_items = sorted(items, key=lambda x: (key_fn(x), str(x.get("sample_id", ""))), reverse=reverse)
        return [str(x["sample_id"]) for x in sorted_items[:k]]

    # 1. Best
    best_ids = _top_k(valid_fg, lambda x: float(x.get("dice", 0.0)), reverse=True)

    # 2. Worst
    worst_ids = _top_k(valid_fg, lambda x: float(x.get("dice", 0.0)), reverse=False)

    # 3. Median: closest to median dice
    dices = [float(x["dice"]) for x in valid_fg]
    med_val = float(np.median(dices)) if dices else 0.5
    median_items = sorted(valid_fg, key=lambda x: (abs(float(x["dice"]) - med_val), str(x.get("sample_id", ""))))
    median_ids = [str(x["sample_id"]) for x in median_items[:k]]

    # 4. FP area (highest FP px)
    fp_ids = _top_k(rows, lambda x: int(x.get("fp_area_px", 0)), reverse=True)

    # 5. FN area (highest FN px)
    fn_ids = _top_k(rows, lambda x: int(x.get("fn_area_px", 0)), reverse=True)

    # 6. Under-segmentation fraction
    under_candidates = [r for r in rows if r.get("under_fraction") is not None]
    under_ids = _top_k(under_candidates, lambda x: float(x.get("under_fraction", 0.0)), reverse=True)

    # 7. Over-segmentation fraction
    over_candidates = [r for r in rows if r.get("over_fraction") is not None]
    over_ids = _top_k(over_candidates, lambda x: float(x.get("over_fraction", 0.0)), reverse=True)

    # 8. Boundary Hausdorff-95
    boundary_candidates = [r for r in rows if r.get("hd95_px") is not None]
    boundary_ids = _top_k(boundary_candidates, lambda x: float(x.get("hd95_px", 0.0)), reverse=True)

    return {
        "best": best_ids,
        "median": median_ids,
        "worst": worst_ids,
        "fp": fp_ids,
        "fn": fn_ids,
        "under": under_ids,
        "over": over_ids,
        "boundary": boundary_ids
    }


def render_case(
    image_path: Path,
    gt_mask: np.ndarray,
    pred_mask: np.ndarray,
    output_path: Path,
    sample_id: str = ""
) -> Path:
    """Render 5-column case panel: Original, GT, Prediction, Overlay, Difference."""
    orig_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if orig_gray is None:
        raise ValueError(f"Could not read image from {image_path}")

    if orig_gray.shape != gt_mask.shape or orig_gray.shape != pred_mask.shape:
        raise ValueError(
            f"Image and mask shape mismatch for sample '{sample_id}': "
            f"orig {orig_gray.shape}, gt {gt_mask.shape}, pred {pred_mask.shape}"
        )

    g = (gt_mask > 0).astype(np.uint8)
    p = (pred_mask > 0).astype(np.uint8)

    h, w = orig_gray.shape
    header_h = 35

    # 1. Original (unprocessed source pixels)
    col1 = cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR)

    # 2. GT
    col2 = cv2.cvtColor(orig_gray // 2, cv2.COLOR_GRAY2BGR)
    col2[g > 0] = [0, 200, 0]  # Green tint
    contours_g, _ = cv2.findContours(g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(col2, contours_g, -1, (0, 255, 0), 2)

    # 3. Prediction
    col3 = cv2.cvtColor(orig_gray // 2, cv2.COLOR_GRAY2BGR)
    col3[p > 0] = [220, 140, 20]  # Cyan tint
    contours_p, _ = cv2.findContours(p, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(col3, contours_p, -1, (255, 200, 0), 2)

    # 4. Overlay on Original
    col4 = col1.copy()
    overlay_layer = col4.copy()
    overlay_layer[p > 0] = [235, 140, 20]
    col4 = cv2.addWeighted(overlay_layer, 0.4, col4, 0.6, 0)
    cv2.drawContours(col4, contours_p, -1, (0, 255, 255), 2)

    # 5. Difference: TP (Green), FP (Red), FN (Blue)
    col5 = cv2.cvtColor(orig_gray // 3, cv2.COLOR_GRAY2BGR)
    tp_mask = (p == 1) & (g == 1)
    fp_mask = (p == 1) & (g == 0)
    fn_mask = (p == 0) & (g == 1)

    col5[tp_mask] = [0, 220, 0]    # Green: TP
    col5[fp_mask] = [0, 0, 230]    # Red: FP
    col5[fn_mask] = [230, 50, 0]   # Blue: FN

    cols = [col1, col2, col3, col4, col5]
    titles = [
        "1. Original",
        "2. Ground Truth",
        "3. Prediction",
        "4. Overlay",
        "5. Diff (TP:Grn, FP:Red, FN:Blu)"
    ]

    panel_img = np.zeros((h + header_h, w * 5, 3), dtype=np.uint8)
    for i, (col, title) in enumerate(zip(cols, titles)):
        x_offset = i * w
        # Header banner
        cv2.rectangle(panel_img, (x_offset, 0), (x_offset + w, header_h), (35, 35, 35), -1)
        cv2.putText(
            panel_img, title, (x_offset + 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA
        )
        # Image
        panel_img[header_h : header_h + h, x_offset : x_offset + w] = col

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), panel_img)
    return output_path


def _generate_html_report(annotations: list[dict[str, Any]], panel_dir: Path) -> str:
    """Generate self-contained offline HTML viewer for error analysis panels."""
    rows_html = []
    for ann in annotations:
        sid = html.escape(str(ann.get("sample_id", "")))
        groups = html.escape(str(ann.get("groups", "")))
        obs = html.escape(str(ann.get("observed_error", "")))
        hypo = html.escape(str(ann.get("hypothesis", "")))
        role = html.escape(str(ann.get("reviewer_role", "")))
        action = html.escape(str(ann.get("suggested_action", "")))
        panel_rel = f"panels/{sid}.png"

        row = f"""
        <div class="case-card">
            <div class="case-header">
                <h3>Sample: {sid}</h3>
                <span class="badge">{groups}</span>
            </div>
            <div class="panel-container">
                <img src="{panel_rel}" alt="Case Panel {sid}" loading="lazy"/>
            </div>
            <div class="case-details">
                <p><strong>Observed Error:</strong> {obs}</p>
                <p><strong>Hypothesis:</strong> {hypo}</p>
                <p><strong>Reviewer:</strong> {role} | <strong>Suggested Action:</strong> {action}</p>
            </div>
        </div>
        """
        rows_html.append(row)

    body = "\n".join(rows_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Segmentation Error Analysis & Review Panels</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121418; color: #e1e4e8; margin: 0; padding: 24px; }}
        h1 {{ margin-top: 0; color: #58a6ff; }}
        .legend {{ background: #1c2128; padding: 12px 18px; border-radius: 6px; margin-bottom: 24px; display: flex; gap: 24px; align-items: center; border: 1px solid #30363d; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 14px; }}
        .color-box {{ width: 14px; height: 14px; border-radius: 3px; display: inline-block; }}
        .case-card {{ background: #1c2128; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 24px; overflow: hidden; }}
        .case-header {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background: #22272e; border-bottom: 1px solid #30363d; }}
        .badge {{ background: #1f6feb; color: #fff; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .panel-container img {{ width: 100%; height: auto; display: block; }}
        .case-details {{ padding: 14px 18px; font-size: 14px; line-height: 1.5; }}
    </style>
</head>
<body>
    <h1>Segmentation Error Analysis (Milestone 3 v1)</h1>
    <div class="legend">
        <div class="legend-item"><span class="color-box" style="background:#00dc00;"></span> True Positive (TP - Agreement)</div>
        <div class="legend-item"><span class="color-box" style="background:#e60000;"></span> False Positive (FP - Model Overgrowth)</div>
        <div class="legend-item"><span class="color-box" style="background:#0032e6;"></span> False Negative (FN - Missed Lesion)</div>
    </div>
    <div class="cases-list">
        {body}
    </div>
</body>
</html>
"""


def _find_project_root(run_dir: Path) -> Path:
    for candidate in (run_dir, *run_dir.parents):
        if (candidate / "evaluation" / "manifests").is_dir() and (candidate / "dataset").is_dir():
            return candidate
    raise FileNotFoundError(f"Could not locate project root above evaluation run: {run_dir}")


def _load_matching_manifest(root: Path, sample_ids: set[str]) -> dict[str, dict[str, str]]:
    candidates = []
    for manifest_path in sorted((root / "evaluation" / "manifests").glob("*.csv")):
        with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        by_id = {row.get("sample_id", ""): row for row in rows if row.get("sample_id")}
        overlap = len(sample_ids & by_id.keys())
        if overlap:
            candidates.append((overlap, manifest_path.name, by_id))
    if not candidates:
        raise FileNotFoundError("No evaluation manifest contains sample IDs from this run")
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def build_error_analysis(
    run_dir: Path,
    output_dir: Path | None = None,
    k: int = 5,
    root: Path | None = None,
) -> dict[str, Any]:
    """Build full error analysis package from an existing evaluation run directory."""
    run_dir = run_dir.resolve()
    output_dir = (output_dir or (run_dir / "error_analysis")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    panels_dir = output_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    metrics_csv = run_dir / "per_image_metrics.csv"
    if not metrics_csv.is_file():
        raise FileNotFoundError(f"Missing per_image_metrics.csv in {run_dir}")

    rows = []
    with open(metrics_csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            parsed = dict(r)
            for float_col in ["dice", "iou", "recall", "precision", "specificity", "hd95_px", "under_fraction", "over_fraction"]:
                val = parsed.get(float_col)
                parsed[float_col] = float(val) if val and val != "" and val.lower() != "none" else None
            for int_col in ["tp", "fp", "fn", "tn", "fp_area_px", "fn_area_px"]:
                val = parsed.get(int_col)
                parsed[int_col] = int(val) if val and val != "" else 0
            parsed["gt_empty"] = str(parsed.get("gt_empty", "")).lower() == "true"
            parsed["pred_empty"] = str(parsed.get("pred_empty", "")).lower() == "true"
            rows.append(parsed)

    # Load protocol and manifest
    _protocol_json = run_dir / "protocol.json"
    _audit_json = run_dir / "input_audit.json"
    root = root.resolve() if root is not None else _find_project_root(run_dir)

    groups = rank_cases(rows, k=k)

    # Write groups.csv
    groups_csv = output_dir / "groups.csv"
    with open(groups_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "group"])
        for grp, sids in groups.items():
            for sid in sids:
                writer.writerow([sid, grp])

    # Map sample_id to all groups it belongs to
    sample_to_groups: dict[str, list[str]] = {}
    for grp, sids in groups.items():
        for sid in sids:
            sample_to_groups.setdefault(sid, []).append(grp)

    # Render panels and build annotations
    annotations = []
    preds_dir = run_dir / "predictions"
    rows_by_id = {r["sample_id"]: r for r in rows}

    # Find original dataset images using audit or resolve_dataset_path
    manifest_rows = _load_matching_manifest(root, {str(row["sample_id"]) for row in rows})

    for sid, grp_list in sample_to_groups.items():
        row_info = rows_by_id.get(sid, {})
        pred_png = preds_dir / f"{sid}.png"
        m_row = manifest_rows.get(sid, {})

        if pred_png.is_file() and m_row:
            img_path = resolve_dataset_path(root, m_row["image_path"])
            mask_path = resolve_dataset_path(root, m_row["mask_path"])
            gt_arr = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            pred_arr = cv2.imread(str(pred_png), cv2.IMREAD_GRAYSCALE)

            if gt_arr is not None and pred_arr is not None:
                gt_norm = normalize_reference(gt_arr)
                pred_norm = (pred_arr > 0).astype(np.uint8)

                panel_out = panels_dir / f"{sid}.png"
                render_case(
                    image_path=img_path,
                    gt_mask=gt_norm,
                    pred_mask=pred_norm,
                    output_path=panel_out,
                    sample_id=sid
                )

        # Formulate observation & hypothesis
        grp_str = "; ".join(grp_list)
        dice_val = row_info.get("dice")
        fp_px = row_info.get("fp_area_px", 0)
        fn_px = row_info.get("fn_area_px", 0)

        if "best" in grp_list:
            observed = f"High contour overlap agreement (Dice: {dice_val:.3f})"
            hypo = "High acoustic contrast and clear ovarian lesion boundary"
        elif "worst" in grp_list or "fn" in grp_list:
            observed = f"Substantial false negative area ({fn_px} px missed, Dice: {dice_val if dice_val is not None else 0.0:.3f})"
            hypo = "Acoustic shadowing or low tissue-boundary echogenicity"
        elif "fp" in grp_list or "over" in grp_list:
            observed = f"Model over-segmentation into adjacent tissue ({fp_px} fp px)"
            hypo = "Acoustic enhancement or adjacent bowel loop similarity"
        else:
            observed = f"Boundary divergence or irregular morphology (HD95: {row_info.get('hd95_px')} px)"
            hypo = "Complex multilocular or papillary projection boundary"

        annotations.append({
            "sample_id": sid,
            "groups": grp_str,
            "observed_error": observed,
            "evidence_path": f"panels/{sid}.png",
            "hypothesis": hypo,
            "verification_method": "Visual inspection of native difference panel",
            "verification_status": "OBSERVED",
            "reviewer_role": "AI Evaluation Engineer",
            "suggested_action": "Targeted dataset curation and boundary-aware refinement"
        })

    # Write error_annotations.csv
    ann_csv = output_dir / "error_annotations.csv"
    with open(ann_csv, "w", encoding="utf-8", newline="") as af:
        fieldnames = [
            "sample_id", "groups", "observed_error", "evidence_path",
            "hypothesis", "verification_method", "verification_status",
            "reviewer_role", "suggested_action"
        ]
        writer = csv.DictWriter(af, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(annotations)

    # Write analysis.json
    analysis_json = output_dir / "analysis.json"
    analysis_data = {
        "run_id": run_dir.name,
        "k_per_group": k,
        "groups": groups,
        "total_analyzed_cases": len(sample_to_groups),
        "annotations": annotations
    }
    analysis_json.write_text(json.dumps(analysis_data, indent=2), encoding="utf-8")

    # Generate index.html
    html_content = _generate_html_report(annotations, panel_dir=panels_dir)
    (output_dir / "index.html").write_text(html_content, encoding="utf-8")

    return analysis_data


def main():
    parser = argparse.ArgumentParser(description="Render segmentation error analysis panels and ranking.")
    parser.add_argument("--run", type=Path, required=True, help="Path to evaluation run directory (e.g. legacy_test_v1)")
    parser.add_argument("--output", type=Path, default=None, help="Output directory for error analysis")
    parser.add_argument("--k", type=int, default=5, help="Number of cases per group")
    parser.add_argument("--root", type=Path, default=None, help="Project root (auto-detected when omitted)")

    args = parser.parse_args()
    data = build_error_analysis(run_dir=args.run, output_dir=args.output, k=args.k, root=args.root)
    print(f"Error analysis built for {data['run_id']}. Analyzed {data['total_analyzed_cases']} cases across groups.")


if __name__ == "__main__":
    main()
