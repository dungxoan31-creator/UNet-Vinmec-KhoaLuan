"""
HITL Session & Timeline Analysis Service and CLI (Task 14).
Evaluates clinical review timelines, monotonic timings, and before/after paired mask quality.
"""

import argparse
import csv
import json
import os
from typing import Any

import numpy as np

from evaluation.segmentation_metrics import score_masks


def summarize_timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Reconstructs task timeline from sequential HITL events.
    Calculates exact arithmetic timings: roundtrip, active edit, review elapsed, correction elapsed.
    """
    sorted_events = sorted(events, key=lambda e: e.get("seq", 0))

    inference_start = None
    inference_end = None
    viewed_time = None
    first_edit_time = None
    last_edit_time = None
    active_edit_ms = 0.0
    active_stroke_start = None
    confirm_attempt_time = None
    confirm_ack_time = None
    paused_ms = 0.0
    pause_start = None

    edit_count = 0
    reset_count = 0
    save_failed = False
    is_complete = False

    for ev in sorted_events:
        t = float(ev.get("elapsed_ms", 0.0))
        etype = ev.get("event_type")

        if etype == "INFERENCE_START":
            inference_start = t
        elif etype == "INFERENCE_END":
            inference_end = t
        elif etype == "PREDICTION_VIEWED":
            if viewed_time is None:
                viewed_time = t
        elif etype == "CORRECTION_START":
            if first_edit_time is None:
                first_edit_time = t
            active_stroke_start = t
        elif etype == "EDIT_COMMITTED":
            edit_count += 1
            if first_edit_time is None:
                first_edit_time = t
            last_edit_time = t
            if active_stroke_start is not None:
                active_edit_ms += max(0.0, t - active_stroke_start)
                active_stroke_start = None
        elif etype == "RESET_AI":
            reset_count += 1
        elif etype == "PAUSE":
            pause_start = t
        elif etype == "RESUME":
            if pause_start is not None:
                paused_ms += max(0.0, t - pause_start)
                pause_start = None
        elif etype == "CONFIRM_ATTEMPT":
            confirm_attempt_time = t
        elif etype == "CONFIRM_ACK":
            confirm_ack_time = t
            is_complete = True
        elif etype == "SAVE_FAILED":
            save_failed = True

    roundtrip_ms = None
    if inference_start is not None and inference_end is not None:
        roundtrip_ms = max(0.0, inference_end - inference_start)

    review_elapsed_ms = None
    task_total_ms = None
    null_reason = None

    if is_complete and confirm_ack_time is not None:
        task_total_ms = confirm_ack_time
        if viewed_time is not None:
            review_elapsed_ms = max(0.0, confirm_ack_time - viewed_time)
    else:
        null_reason = "INCOMPLETE_TIMELINE"
        task_total_ms = sorted_events[-1].get("elapsed_ms") if sorted_events else None

    correction_elapsed_ms = None
    if first_edit_time is not None and confirm_attempt_time is not None:
        correction_elapsed_ms = max(0.0, confirm_attempt_time - first_edit_time)

    return {
        "roundtrip_ms": roundtrip_ms,
        "active_edit_ms": active_edit_ms,
        "review_elapsed_ms": review_elapsed_ms,
        "correction_elapsed_ms": correction_elapsed_ms,
        "task_total_ms": task_total_ms,
        "edit_count": edit_count,
        "reset_count": reset_count,
        "paused_ms": paused_ms,
        "save_failed": save_failed,
        "is_complete": is_complete,
        "null_reason": null_reason,
        "is_raw_accepted": edit_count == 0 and reset_count == 0,
    }


def analyze_hitl(
    sessions: list[dict[str, Any]],
    references: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Analyzes multiple HITL sessions, task timelines, and paired mask metrics.
    """
    per_task = []
    per_session = []

    total_sessions = len(sessions)
    clinician_sessions = 0
    technical_sessions = 0
    demo_sessions = 0
    completed_sessions = 0

    clinician_review_times = []
    clinician_deltas = []

    for s in sessions:
        role = s.get("participant_role", "technical_tester")
        origin = s.get("data_origin", "live")
        is_clinician = bool(role == "clinician" and origin == "live")

        if origin == "demo":
            demo_sessions += 1
        elif role == "technical_tester":
            technical_sessions += 1
        elif is_clinician:
            clinician_sessions += 1

        sess_status = s.get("status", "IN_PROGRESS")
        if sess_status == "COMPLETED":
            completed_sessions += 1

        wall_time_ms = s.get("wall_time_ms")
        tasks = s.get("tasks", [])
        sum_task_time_ms = 0.0

        for t in tasks:
            img_id = t.get("image_id", "")
            events = t.get("events", [])
            t_summary = summarize_timeline(events)

            if t_summary["task_total_ms"] is not None:
                sum_task_time_ms += t_summary["task_total_ms"]

            pre_mask = t.get("pre_mask")
            post_mask = t.get("post_mask")

            dice_pre = None
            dice_post = None
            delta_dice = None
            quality_null_reason = None

            if references is not None and img_id in references:
                ref_info = references[img_id]
                gt = ref_info.get("gt_mask")
                if gt is not None and pre_mask is not None and post_mask is not None:
                    res_pre = score_masks(pre_mask, gt)
                    res_post = score_masks(post_mask, gt)
                    dice_pre = res_pre["dice"]
                    dice_post = res_post["dice"]
                    delta_dice = dice_post - dice_pre
                    if is_clinician and delta_dice is not None:
                        clinician_deltas.append(delta_dice)
                else:
                    quality_null_reason = "GT_MASK_MISSING"
            else:
                quality_null_reason = "NO_INDEPENDENT_REFERENCE"

            if is_clinician and t_summary["review_elapsed_ms"] is not None:
                clinician_review_times.append(t_summary["review_elapsed_ms"])

            row = {
                "session_id": s.get("id"),
                "task_id": t.get("task_id"),
                "image_id": img_id,
                "prediction_id": t.get("prediction_id"),
                "participant_code": s.get("participant_code"),
                "participant_role": role,
                "data_origin": origin,
                "doctor_action": t.get("doctor_action"),
                "roundtrip_ms": t_summary["roundtrip_ms"],
                "active_edit_ms": t_summary["active_edit_ms"],
                "review_elapsed_ms": t_summary["review_elapsed_ms"],
                "correction_elapsed_ms": t_summary["correction_elapsed_ms"],
                "task_total_ms": t_summary["task_total_ms"],
                "edit_count": t_summary["edit_count"],
                "reset_count": t_summary["reset_count"],
                "is_complete": t_summary["is_complete"],
                "timeline_null_reason": t_summary["null_reason"],
                "dice_pre": dice_pre,
                "dice_post": dice_post,
                "delta_dice": delta_dice,
                "quality_null_reason": quality_null_reason,
            }
            per_task.append(row)

        per_session.append({
            "session_id": s.get("id"),
            "study_id": s.get("study_id"),
            "participant_code": s.get("participant_code"),
            "participant_role": role,
            "data_origin": origin,
            "status": sess_status,
            "wall_time_ms": wall_time_ms,
            "sum_task_time_ms": sum_task_time_ms,
            "task_count": len(tasks),
            "completed_task_count": sum(1 for t in tasks if summarize_timeline(t.get("events", []))["is_complete"]),
        })

    summary = {
        "total_sessions": total_sessions,
        "clinician_sessions": clinician_sessions,
        "technical_sessions": technical_sessions,
        "demo_sessions": demo_sessions,
        "completed_sessions": completed_sessions,
        "total_tasks": len(per_task),
        "clinician_median_review_ms": float(np.median(clinician_review_times)) if clinician_review_times else None,
        "clinician_median_delta_dice": float(np.median(clinician_deltas)) if clinician_deltas else None,
    }

    return {
        "per_task": per_task,
        "per_session": per_session,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze measured HITL sessions and paired mask quality.")
    parser.add_argument("--input", required=True, help="Input directory containing raw exported HITL sessions")
    parser.add_argument("--references", default=None, help="Optional validated reference ground truth manifest")
    parser.add_argument("--output", required=True, help="Output directory for HITL analysis artifacts")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting output directory")
    args = parser.parse_args()

    if os.path.exists(args.output) and not args.overwrite:
        raise FileExistsError(f"Output directory exists: {args.output}. Use --overwrite to replace.")
    os.makedirs(args.output, exist_ok=True)

    sessions_file = os.path.join(args.input, "sessions.json")
    if not os.path.isfile(sessions_file):
        raise FileNotFoundError(f"Missing {sessions_file}")

    with open(sessions_file, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    references = None
    if args.references and os.path.isfile(args.references):
        references = {}
        # Support loading reference manifest if provided
        with open(args.references, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                references[row.get("image_id", "")] = row

    results = analyze_hitl(sessions, references=references)

    # Save summary.json
    summary_path = os.path.join(args.output, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results["summary"], f, indent=2)

    # Save per_task.csv
    per_task_path = os.path.join(args.output, "per_task.csv")
    if results["per_task"]:
        fieldnames = list(results["per_task"][0].keys())
        with open(per_task_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results["per_task"])

    # Save per_session.csv
    per_session_path = os.path.join(args.output, "per_session.csv")
    if results["per_session"]:
        fieldnames = list(results["per_session"][0].keys())
        with open(per_session_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results["per_session"])

    print(f"[HITL Analysis] Analysis complete. Output written to {args.output}")


if __name__ == "__main__":
    main()
