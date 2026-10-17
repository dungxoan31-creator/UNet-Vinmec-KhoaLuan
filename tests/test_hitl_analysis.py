"""
Tests for HITL Session Analysis, Monotonic Timings, and Paired Segmentation Quality (Task 14).
"""

import numpy as np
import pytest

from evaluation.hitl_analysis import (
    analyze_hitl,
    summarize_timeline,
)


def test_timing_and_edit_oracle():
    events = [
        {"event_type": "INFERENCE_START", "elapsed_ms": 10.0, "seq": 1},
        {"event_type": "INFERENCE_END", "elapsed_ms": 110.0, "seq": 2},
        {"event_type": "PREDICTION_VIEWED", "elapsed_ms": 120.0, "seq": 3},
        {"event_type": "CORRECTION_START", "elapsed_ms": 200.0, "seq": 4},
        {
            "event_type": "EDIT_COMMITTED",
            "elapsed_ms": 240.0,
            "seq": 5,
            "payload": {"tool": "brush", "changed_pixels": 45},
        },
        {"event_type": "CONFIRM_ATTEMPT", "elapsed_ms": 700.0, "seq": 6},
        {"event_type": "CONFIRM_ACK", "elapsed_ms": 750.0, "seq": 7, "payload": {"batch_request_id": "req-1"}},
    ]
    summary = summarize_timeline(events)
    assert summary["roundtrip_ms"] == 100.0
    assert summary["active_edit_ms"] == 40.0
    assert summary["review_elapsed_ms"] == 630.0
    assert summary["correction_elapsed_ms"] == 500.0
    assert summary["task_total_ms"] == 750.0
    assert summary["edit_count"] == 1
    assert summary["is_complete"] is True


def test_incomplete_timeline_is_not_zero_duration():
    events = [
        {"event_type": "PREDICTION_VIEWED", "elapsed_ms": 100.0, "seq": 1},
        {"event_type": "EDIT_COMMITTED", "elapsed_ms": 200.0, "seq": 2, "payload": {"tool": "brush"}},
    ]
    summary = summarize_timeline(events)
    assert summary["is_complete"] is False
    assert summary["review_elapsed_ms"] is None
    assert summary["null_reason"] == "INCOMPLETE_TIMELINE"
    assert summary["review_elapsed_ms"] != 0.0


def test_hitl_pairs_exact_prediction():
    pred_mask_1 = np.zeros((512, 512), dtype=np.uint8)
    pred_mask_1[100:150, 100:150] = 1

    pred_mask_2 = np.zeros((512, 512), dtype=np.uint8)
    pred_mask_2[200:250, 200:250] = 1

    final_reviewed_mask = np.zeros((512, 512), dtype=np.uint8)
    final_reviewed_mask[100:160, 100:160] = 1

    sessions = [
        {
            "id": "sess-1",
            "study_id": "study-1",
            "participant_code": "DR_A",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "created_at": "2026-10-16T12:00:00Z",
            "completed_at": "2026-10-16T12:05:00Z",
            "wall_time_ms": 300000.0,
            "tasks": [
                {
                    "task_id": "task-1",
                    "image_id": "img-1",
                    "prediction_id": "pred-1",
                    "doctor_action": "MODIFIED",
                    "pre_mask": pred_mask_1,
                    "post_mask": final_reviewed_mask,
                    "events": [
                        {"event_type": "PREDICTION_VIEWED", "elapsed_ms": 10.0, "seq": 1},
                        {"event_type": "CONFIRM_ACK", "elapsed_ms": 5000.0, "seq": 2, "payload": {"batch_request_id": "req-1"}},
                    ],
                }
            ],
        }
    ]

    analysis = analyze_hitl(sessions, references=None)
    assert len(analysis["per_task"]) == 1
    task_res = analysis["per_task"][0]
    assert task_res["prediction_id"] == "pred-1"
    assert task_res["doctor_action"] == "MODIFIED"


def test_reference_is_independent():
    mask = np.zeros((512, 512), dtype=np.uint8)
    sessions = [
        {
            "id": "sess-1",
            "study_id": "study-1",
            "participant_code": "DR_A",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "wall_time_ms": 5000.0,
            "tasks": [
                {
                    "task_id": "task-1",
                    "image_id": "img-1",
                    "prediction_id": "pred-1",
                    "doctor_action": "ACCEPTED_RAW",
                    "pre_mask": mask,
                    "post_mask": mask,
                    "events": [
                        {"event_type": "PREDICTION_VIEWED", "elapsed_ms": 10.0, "seq": 1},
                        {"event_type": "CONFIRM_ACK", "elapsed_ms": 1000.0, "seq": 2, "payload": {"batch_request_id": "r"}},
                    ],
                }
            ],
        }
    ]
    # Without references -> metrics null
    res = analyze_hitl(sessions, references=None)
    t = res["per_task"][0]
    assert t["dice_pre"] is None
    assert t["dice_post"] is None
    assert t["delta_dice"] is None
    assert t["quality_null_reason"] == "NO_INDEPENDENT_REFERENCE"
    assert t["task_total_ms"] == 1000.0


def test_demo_and_technical_not_clinician():
    sessions = [
        {
            "id": "s-demo",
            "study_id": "c-demo",
            "participant_code": "DEMO_USER",
            "participant_role": "clinician",
            "data_origin": "demo",
            "status": "COMPLETED",
            "wall_time_ms": 1000.0,
            "tasks": [],
        },
        {
            "id": "s-tech",
            "study_id": "c-tech",
            "participant_code": "QA_ENGINEER",
            "participant_role": "technical_tester",
            "data_origin": "live",
            "status": "COMPLETED",
            "wall_time_ms": 2000.0,
            "tasks": [],
        },
        {
            "id": "s-doc",
            "study_id": "c-doc",
            "participant_code": "DR_VINMEC_01",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "wall_time_ms": 3000.0,
            "tasks": [],
        },
    ]
    registry = [
        {"participant_code": "DR_VINMEC_01", "role_verified": "verified_clinician", "consent_status": "CONSENTED", "data_origin": "live"},
        {"participant_code": "QA_ENGINEER", "role_verified": "verified_technical", "consent_status": "EXEMPT", "data_origin": "live"},
        {"participant_code": "DEMO_USER", "role_verified": "technical_fixture", "consent_status": "EXEMPT", "data_origin": "demo"},
    ]
    res = analyze_hitl(sessions, references=None, participant_registry=registry)
    assert res["summary"]["total_sessions"] == 3
    assert res["summary"]["clinician_sessions"] == 1
    assert res["summary"]["technical_sessions"] == 1
    assert res["summary"]["demo_sessions"] == 1


def test_self_declared_clinician_is_not_verified_participant():
    sessions = [
        {
            "id": "s-unverified",
            "study_id": "c-1",
            "participant_code": "SELF_DECLARED_DR",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "tasks": [],
        }
    ]
    registry = [
        {
            "participant_code": "SELF_DECLARED_DR",
            "role_verified": "unverified",
            "consent_status": "NONE",
            "source_evidence": "none",
            "data_origin": "test_fixture",
            "disposition": "quarantine",
        }
    ]
    res = analyze_hitl(sessions, references=None, participant_registry=registry)
    assert res["summary"]["clinician_sessions"] == 0
    assert res["summary"]["verified_clinician_sessions"] == 0
    assert res["summary"]["unverified_sessions"] == 1
    assert res["summary"]["quarantined_sessions"] == 1
    assert res["summary"]["participant_counts"]["verified_clinicians"] == 0
    assert res["per_session"][0]["session_classification"] == "unverified"
    assert res["per_session"][0]["provenance_disposition"] == "quarantine"


def test_missing_registry_quarantines_clinician_sessions():
    sessions = [
        {
            "id": "s-no-reg",
            "study_id": "c-2",
            "participant_code": "CLINICIAN_01",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "IN_PROGRESS",
            "tasks": [],
        }
    ]
    res = analyze_hitl(sessions, references=None, participant_registry=None)
    assert res["summary"]["clinician_sessions"] == 0
    assert res["summary"]["verified_clinician_sessions"] == 0
    assert res["summary"]["unverified_sessions"] == 1
    assert res["summary"]["quarantined_sessions"] == 1
    assert res["summary"]["participant_counts"]["verified_clinicians"] == 0
    assert res["per_session"][0]["session_classification"] == "unverified"
    assert res["per_session"][0]["provenance_disposition"] == "quarantine"


def test_repeated_sessions_count_one_participant():
    sessions = [
        {"id": f"s-{i}", "study_id": f"c-{i}", "participant_code": "DR_VERIFIED", "participant_role": "clinician", "data_origin": "live", "status": "COMPLETED", "tasks": []}
        for i in range(5)
    ]
    registry = [
        {
            "participant_code": "DR_VERIFIED",
            "role_verified": "verified_clinician",
            "consent_status": "CONSENTED",
            "source_evidence": "hospital_irb",
            "data_origin": "live",
            "disposition": "included",
        }
    ]
    res = analyze_hitl(sessions, references=None, participant_registry=registry)
    assert res["summary"]["total_sessions"] == 5
    assert res["summary"]["clinician_sessions"] == 5
    assert res["summary"]["verified_clinician_sessions"] == 5
    assert res["summary"]["participant_counts"]["total_unique"] == 1
    assert res["summary"]["participant_counts"]["verified_clinicians"] == 1


def test_missing_gt_preserves_null_delta():
    mask = np.ones((50, 50), dtype=np.uint8)
    sessions = [
        {
            "id": "s-nogt",
            "study_id": "c-nogt",
            "participant_code": "TECH_01",
            "participant_role": "technical_tester",
            "data_origin": "live",
            "status": "COMPLETED",
            "tasks": [
                {
                    "task_id": "t-1",
                    "image_id": "img-no-reference",
                    "pre_mask": mask,
                    "post_mask": mask,
                    "events": [{"event_type": "CONFIRM_ACK", "elapsed_ms": 1000.0, "seq": 1}],
                }
            ],
        }
    ]
    res = analyze_hitl(sessions, references=None)
    t = res["per_task"][0]
    assert t["delta_dice"] is None
    assert t["delta_dice"] != 0.0
    assert t["quality_null_reason"] == "NO_INDEPENDENT_REFERENCE"



def test_paired_deltas_include_negative():
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[20:60, 20:60] = 1

    # AI prediction is perfect: Dice = 1.0
    pred_perfect = gt.copy()
    # User makes it worse: Dice = 0.5
    user_worse = np.zeros((100, 100), dtype=np.uint8)
    user_worse[20:60, 20:40] = 1  # half size -> tp=800, fp=0, fn=800 -> dice=1600/2400 = 0.6667

    # Positive improvement: AI is worse, User makes it perfect
    pred_poor = user_worse.copy()
    user_better = pred_perfect.copy()

    references = {"img-pos": {"gt_mask": gt}, "img-neg": {"gt_mask": gt}}
    sessions = [
        {
            "id": "s-1",
            "study_id": "case-1",
            "participant_code": "DR_01",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "wall_time_ms": 2000.0,
            "tasks": [
                {
                    "task_id": "t-pos",
                    "image_id": "img-pos",
                    "prediction_id": "p-1",
                    "pre_mask": pred_poor,
                    "post_mask": user_better,
                    "events": [
                        {"event_type": "CONFIRM_ACK", "elapsed_ms": 500.0, "seq": 1, "payload": {"batch_request_id": "b"}},
                    ],
                },
                {
                    "task_id": "t-neg",
                    "image_id": "img-neg",
                    "prediction_id": "p-2",
                    "pre_mask": pred_perfect,
                    "post_mask": user_worse,
                    "events": [
                        {"event_type": "CONFIRM_ACK", "elapsed_ms": 500.0, "seq": 1, "payload": {"batch_request_id": "b"}},
                    ],
                },
            ],
        }
    ]

    res = analyze_hitl(sessions, references=references)
    t_pos = next(t for t in res["per_task"] if t["task_id"] == "t-pos")
    t_neg = next(t for t in res["per_task"] if t["task_id"] == "t-neg")

    assert t_pos["delta_dice"] > 0, f"Expected positive delta, got {t_pos['delta_dice']}"
    assert t_neg["delta_dice"] < 0, f"Expected negative delta, got {t_neg['delta_dice']}"


def test_case_wall_time_not_sum_of_images():
    sessions = [
        {
            "id": "s-wall",
            "study_id": "case-wall",
            "participant_code": "DR_02",
            "participant_role": "clinician",
            "data_origin": "live",
            "status": "COMPLETED",
            "wall_time_ms": 10000.0,
            "tasks": [
                {
                    "task_id": "t-1",
                    "image_id": "img-1",
                    "prediction_id": "p-1",
                    "events": [{"event_type": "CONFIRM_ACK", "elapsed_ms": 3000.0, "seq": 1, "payload": {"batch_request_id": "x"}}],
                },
                {
                    "task_id": "t-2",
                    "image_id": "img-2",
                    "prediction_id": "p-2",
                    "events": [{"event_type": "CONFIRM_ACK", "elapsed_ms": 4000.0, "seq": 1, "payload": {"batch_request_id": "x"}}],
                },
            ],
        }
    ]
    res = analyze_hitl(sessions, references=None)
    sess_summary = res["per_session"][0]
    assert sess_summary["wall_time_ms"] == 10000.0
    assert sess_summary["sum_task_time_ms"] == 7000.0
    assert sess_summary["wall_time_ms"] != sess_summary["sum_task_time_ms"]
