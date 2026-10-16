"""
Read-Only SQLite HITL Session Exporter (Task 14).
Safely extracts authenticated sessions, timelines, and before/after paired mask representations
into research JSON/CSV bundles without PHI or user credentials.
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.inference_engine import InferenceEngine


def export_hitl_sessions(
    db_path: str,
    output_dir: str,
    session_ids: list[str] | None = None,
    overwrite: bool = False,
):
    if os.path.exists(output_dir) and not overwrite:
        raise FileExistsError(f"Output directory exists: {output_dir}. Use --overwrite to replace.")
    os.makedirs(output_dir, exist_ok=True)

    abs_db = os.path.abspath(db_path)
    if not os.path.isfile(abs_db):
        raise FileNotFoundError(f"Database not found at {abs_db}")

    # Read-only SQLite URI connection (mode=ro)
    uri = f"file:{abs_db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Fetch sessions
        query = "SELECT id, study_id, participant_code, participant_role, data_origin, status, review_batch_id, created_at, completed_at FROM hitl_sessions"
        params = []
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            query += f" WHERE id IN ({placeholders})"
            params = session_ids

        cursor.execute(query, params)
        session_rows = cursor.fetchall()

        sessions_data = []
        all_events_for_jsonl = []
        sessions_csv_rows = []

        engine = InferenceEngine(architecture="standard_unet")

        for s in session_rows:
            sess_id = s["id"]
            study_id = s["study_id"]
            p_code = s["participant_code"]
            p_role = s["participant_role"]
            origin = s["data_origin"]
            status = s["status"]
            batch_id = s["review_batch_id"]
            created_at = s["created_at"]
            completed_at = s["completed_at"]

            sessions_csv_rows.append({
                "session_id": sess_id,
                "study_id": study_id,
                "participant_code": p_code,
                "participant_role": p_role,
                "data_origin": origin,
                "status": status,
                "review_batch_id": batch_id,
                "created_at": created_at,
                "completed_at": completed_at,
            })

            # Fetch events for this session
            cursor.execute(
                "SELECT event_id, task_id, image_id, prediction_id, seq, event_type, client_utc, elapsed_ms, session_elapsed_ms, payload "
                "FROM hitl_events WHERE session_id = ? ORDER BY task_id, seq ASC",
                (sess_id,),
            )
            event_rows = cursor.fetchall()

            # Group events by task_id
            tasks_map = {}
            for ev in event_rows:
                task_id = ev["task_id"]
                if task_id not in tasks_map:
                    tasks_map[task_id] = {
                        "task_id": task_id,
                        "image_id": ev["image_id"],
                        "prediction_id": ev["prediction_id"],
                        "events": [],
                    }
                payload_val = None
                if ev["payload"]:
                    try:
                        payload_val = json.loads(ev["payload"]) if isinstance(ev["payload"], str) else ev["payload"]
                    except Exception:
                        payload_val = ev["payload"]

                event_dict = {
                    "event_id": ev["event_id"],
                    "session_id": sess_id,
                    "task_id": task_id,
                    "image_id": ev["image_id"],
                    "prediction_id": ev["prediction_id"],
                    "seq": ev["seq"],
                    "event_type": ev["event_type"],
                    "client_utc": ev["client_utc"],
                    "elapsed_ms": ev["elapsed_ms"],
                    "session_elapsed_ms": ev["session_elapsed_ms"],
                    "payload": payload_val,
                }
                tasks_map[task_id]["events"].append(event_dict)
                all_events_for_jsonl.append(event_dict)

            # Reconstruct tasks with pre/post masks
            tasks_list = []
            for t_id, t_data in tasks_map.items():
                img_id = t_data["image_id"]
                pred_id = t_data["prediction_id"]

                pre_mask_np = None
                post_mask_np = None
                doctor_action = "UNREVIEWED"

                # Fetch AI prediction
                if pred_id:
                    cursor.execute("SELECT raw_mask_rle FROM predictions WHERE id = ?", (pred_id,))
                    p_row = cursor.fetchone()
                    if p_row and p_row["raw_mask_rle"]:
                        try:
                            rle_dict = json.loads(p_row["raw_mask_rle"]) if isinstance(p_row["raw_mask_rle"], str) else p_row["raw_mask_rle"]
                            pre_mask_np = engine.rle_to_mask(rle_dict)
                        except Exception:
                            pass

                # Fetch Doctor Review
                cursor.execute(
                    "SELECT doctor_action, verified_mask_rle FROM reviews WHERE image_id = ? ORDER BY created_at DESC LIMIT 1",
                    (img_id,),
                )
                r_row = cursor.fetchone()
                if r_row:
                    doctor_action = r_row["doctor_action"]
                    if r_row["verified_mask_rle"]:
                        try:
                            rle_dict = json.loads(r_row["verified_mask_rle"]) if isinstance(r_row["verified_mask_rle"], str) else r_row["verified_mask_rle"]
                            post_mask_np = engine.rle_to_mask(rle_dict)
                        except Exception:
                            pass

                tasks_list.append({
                    "task_id": t_id,
                    "image_id": img_id,
                    "prediction_id": pred_id,
                    "doctor_action": doctor_action,
                    "pre_mask": pre_mask_np.tolist() if pre_mask_np is not None else None,
                    "post_mask": post_mask_np.tolist() if post_mask_np is not None else None,
                    "events": t_data["events"],
                })

            sessions_data.append({
                "id": sess_id,
                "study_id": study_id,
                "participant_code": p_code,
                "participant_role": p_role,
                "data_origin": origin,
                "status": status,
                "review_batch_id": batch_id,
                "created_at": created_at,
                "completed_at": completed_at,
                "tasks": tasks_list,
            })

        # Save sessions.csv
        csv_path = os.path.join(output_dir, "sessions.csv")
        if sessions_csv_rows:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(sessions_csv_rows[0].keys()))
                writer.writeheader()
                writer.writerows(sessions_csv_rows)

        # Save events.jsonl
        jsonl_path = os.path.join(output_dir, "events.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for ev in all_events_for_jsonl:
                f.write(json.dumps(ev) + "\n")

        # Save sessions.json
        sessions_json_path = os.path.join(output_dir, "sessions.json")
        with open(sessions_json_path, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f)

        print(f"[Export HITL] Exported {len(sessions_data)} sessions and {len(all_events_for_jsonl)} events to {output_dir}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Export HITL sessions and events from read-only SQLite database.")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--session-ids", default=None, help="Comma-separated session IDs to export")
    parser.add_argument("--output", required=True, help="Output directory for raw export files")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting output directory")
    args = parser.parse_args()

    s_ids = [s.strip() for s in args.session_ids.split(",") if s.strip()] if args.session_ids else None
    export_hitl_sessions(args.db, args.output, session_ids=s_ids, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
