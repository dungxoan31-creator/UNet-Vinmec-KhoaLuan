"""
HITL Session & Timeline Analysis Service and CLI (Task 14).
Evaluates clinical review timelines, monotonic timings, and before/after paired mask quality.
"""

import argparse
import csv
import html
import json
import os
from typing import Any

import numpy as np

from evaluation.segmentation_metrics import score_masks


def summarize_questionnaire(
    responses: list[dict[str, Any]],
    participants: list[dict[str, Any]],
    study_status: str | None = None,
) -> dict[str, Any]:
    """
    Summarizes clinician and technical user study questionnaire responses.
    Strictly distinguishes clinician vs technical testers.
    Computes exact median and IQR on Likert scales.
    Escapes all qualitative feedback against HTML/XSS injection.
    """
    unique_participants: dict[str, dict[str, Any]] = {}
    for p in participants:
        code = p.get("participant_code")
        if code and code not in unique_participants:
            unique_participants[code] = p

    clinician_codes = {
        code for code, p in unique_participants.items()
        if str(p.get("role", "")).lower() == "clinician"
    }
    technical_codes = {
        code for code, p in unique_participants.items()
        if str(p.get("role", "")).lower() == "technical_tester"
    }

    clinician_count = len(clinician_codes)
    technical_count = len(technical_codes)
    total_unique = len(unique_participants)
    other_count = total_unique - (clinician_count + technical_count)

    if study_status is not None:
        effective_status = study_status
    elif clinician_count > 0 and len(responses) > 0:
        effective_status = "CONDUCTED"
    else:
        effective_status = "NOT_CONDUCTED"

    if effective_status == "NOT_CONDUCTED" or (clinician_count == 0 and len(responses) == 0):
        return {
            "study_status": effective_status,
            "participant_counts": {
                "total_unique": total_unique,
                "clinicians": clinician_count,
                "technical_testers": technical_count,
                "other": other_count,
            },
            "participants": list(unique_participants.values()),
            "items": {},
            "overall_clinician_median": None,
            "overall_clinician_iqr": None,
            "feedback": [],
        }

    items_map: dict[str, list[int]] = {}
    items_na: dict[str, int] = {}
    all_clinician_ratings: list[int] = []
    feedback_entries: list[dict[str, Any]] = []

    for r in responses:
        item_id = r.get("item_id")
        p_code = r.get("participant_code")
        rating_raw = r.get("rating")
        fb = r.get("feedback")

        if fb:
            feedback_entries.append({
                "participant_code": p_code,
                "session_id": r.get("session_id"),
                "item_id": item_id,
                "feedback": html.escape(str(fb)),
            })

        if not item_id:
            continue

        if item_id not in items_map:
            items_map[item_id] = []
            items_na[item_id] = 0

        if rating_raw is not None and str(rating_raw).strip() != "" and str(rating_raw).lower() != "nan":
            try:
                rating = int(rating_raw)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid rating value {rating_raw} for item {item_id}")

            if rating < 1 or rating > 5:
                raise ValueError(f"Rating {rating} out of range [1, 5] for item {item_id}")

            if p_code in clinician_codes:
                items_map[item_id].append(rating)
                all_clinician_ratings.append(rating)
        else:
            if p_code in clinician_codes:
                items_na[item_id] += 1

    items_summary: dict[str, Any] = {}
    for item_id, ratings in items_map.items():
        n_valid = len(ratings)
        n_na = items_na.get(item_id, 0)
        if n_valid > 0:
            median_val = float(np.median(ratings))
            iqr_val = float(np.percentile(ratings, 75) - np.percentile(ratings, 25))
            mean_val = float(np.mean(ratings))
        else:
            median_val = None
            iqr_val = None
            mean_val = None

        items_summary[item_id] = {
            "n_valid": n_valid,
            "n_na": n_na,
            "median": median_val,
            "iqr": iqr_val,
            "mean": mean_val,
        }

    overall_median = float(np.median(all_clinician_ratings)) if all_clinician_ratings else None
    overall_iqr = (
        float(np.percentile(all_clinician_ratings, 75) - np.percentile(all_clinician_ratings, 25))
        if all_clinician_ratings
        else None
    )

    return {
        "study_status": effective_status,
        "participant_counts": {
            "total_unique": total_unique,
            "clinicians": clinician_count,
            "technical_testers": technical_count,
            "other": other_count,
        },
        "participants": list(unique_participants.values()),
        "items": items_summary,
        "overall_clinician_median": overall_median,
        "overall_clinician_iqr": overall_iqr,
        "feedback": feedback_entries,
    }



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
    parser = argparse.ArgumentParser(description="Analyze measured HITL sessions and questionnaire responses.")
    parser.add_argument("--input", default=None, help="Input directory containing raw exported HITL sessions")
    parser.add_argument("--references", default=None, help="Optional validated reference ground truth manifest")
    parser.add_argument("--output", default=None, help="Output directory for HITL analysis artifacts")
    parser.add_argument("--questionnaire", default=None, help="Optional path to questionnaire responses CSV")
    parser.add_argument("--participants", default=None, help="Optional path to participant metadata CSV")
    parser.add_argument("--user-study-output", default=None, help="Optional directory for user study artifacts")
    parser.add_argument("--study-status", default=None, help="Optional explicit study status (PLANNED, CONDUCTED, NOT_CONDUCTED)")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting output directory")
    args = parser.parse_args()

    # 1. Process HITL sessions if --input is provided
    if args.input:
        if not args.output:
            raise ValueError("--output is required when --input is provided")

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

    # 2. Process Questionnaire / User Study if provided
    if args.questionnaire or args.participants or args.user_study_output:
        user_study_dir = args.user_study_output
        if not user_study_dir and args.output:
            user_study_dir = os.path.join(args.output, "user_study")
        elif not user_study_dir:
            user_study_dir = "evaluation/milestone_3_final/user_study"

        if os.path.exists(user_study_dir) and not args.overwrite:
            raise FileExistsError(f"User study directory exists: {user_study_dir}. Use --overwrite to replace.")
        os.makedirs(user_study_dir, exist_ok=True)

        responses: list[dict[str, Any]] = []
        if args.questionnaire and os.path.isfile(args.questionnaire):
            with open(args.questionnaire, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                responses = list(reader)

        participants: list[dict[str, Any]] = []
        if args.participants and os.path.isfile(args.participants):
            with open(args.participants, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                participants = list(reader)

        study_summary = summarize_questionnaire(
            responses=responses,
            participants=participants,
            study_status=args.study_status,
        )

        # Save summary.json
        with open(os.path.join(user_study_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(study_summary, f, indent=2)

        # Save study_status.json
        status_payload = {
            "study_status": study_summary["study_status"],
            "clinician_count": study_summary["participant_counts"]["clinicians"],
            "technical_count": study_summary["participant_counts"]["technical_testers"],
            "total_participants": study_summary["participant_counts"]["total_unique"],
            "has_clinician_validation": study_summary["study_status"] == "CONDUCTED" and study_summary["participant_counts"]["clinicians"] > 0,
        }
        with open(os.path.join(user_study_dir, "study_status.json"), "w", encoding="utf-8") as f:
            json.dump(status_payload, f, indent=2)

        # Save feedback.md
        feedback_lines = ["# User Study Qualitative Feedback\n\n"]
        if study_summary["feedback"]:
            for fb_item in study_summary["feedback"]:
                feedback_lines.append(
                    f"### Participant: {fb_item.get('participant_code')} (Item: {fb_item.get('item_id')})\n"
                    f"> {fb_item.get('feedback')}\n\n"
                )
        else:
            feedback_lines.append("_No qualitative feedback recorded._\n")

        with open(os.path.join(user_study_dir, "feedback.md"), "w", encoding="utf-8") as f:
            f.writelines(feedback_lines)

        print(f"[User Study] Summary complete. Status: {study_summary['study_status']}. Output written to {user_study_dir}")


if __name__ == "__main__":
    main()

