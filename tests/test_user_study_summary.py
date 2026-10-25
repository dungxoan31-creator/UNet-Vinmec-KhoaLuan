"""
Tests for user study and questionnaire summarization.
Verifies honest handling of clinician vs technical participants,
non-fabrication of metrics, Likert statistics oracles, and HTML escaping.
"""

import csv
import json
import sys

import pytest

from evaluation import hitl_analysis
from evaluation.hitl_analysis import summarize_questionnaire


def test_questionnaire_medians_and_no_fake_participants():
    # 1. Likert stats oracle: ratings [1, 3, 5] -> median=3.0, IQR=2.0
    # Also verify N/A (None) is excluded and NOT treated as 0
    participants = [
        {"participant_code": "CLINICIAN-01", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"},
        {"participant_code": "CLINICIAN-02", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"},
        {"participant_code": "CLINICIAN-03", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"},
        {"participant_code": "TECH-01", "role": "technical_tester", "source": "lab", "consent_status": "EXEMPT"},
        # Duplicate participant row to verify deduplication
        {"participant_code": "CLINICIAN-01", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"},
    ]

    responses = [
        {"participant_code": "CLINICIAN-01", "session_id": "sess-1", "item_id": "learnability", "rating": 1, "na_reason": None},
        {"participant_code": "CLINICIAN-02", "session_id": "sess-2", "item_id": "learnability", "rating": 3, "na_reason": None},
        {"participant_code": "CLINICIAN-03", "session_id": "sess-3", "item_id": "learnability", "rating": 5, "na_reason": None},
        # N/A item for clinician 1: should not count as 0
        {"participant_code": "CLINICIAN-01", "session_id": "sess-1", "item_id": "clinical_utility", "rating": None, "na_reason": "Not applicable to pilot setting"},
        # Technical tester response: should be categorized under technical, not clinician
        {"participant_code": "TECH-01", "session_id": "sess-tech", "item_id": "learnability", "rating": 4, "na_reason": None},
    ]

    summary = summarize_questionnaire(responses, participants, study_status="CONDUCTED")

    # Participant counts
    assert summary["participant_counts"]["total_unique"] == 4
    assert summary["participant_counts"]["clinicians"] == 3
    assert summary["participant_counts"]["technical_testers"] == 1

    # Clinician Likert oracles for learnability: [1, 3, 5]
    learn_stats = summary["items"]["learnability"]
    assert learn_stats["n_valid"] == 3
    assert learn_stats["n_na"] == 0
    assert learn_stats["median"] == 3.0
    assert learn_stats["iqr"] == 2.0

    # N/A handling
    utility_stats = summary["items"]["clinical_utility"]
    assert utility_stats["n_valid"] == 0
    assert utility_stats["n_na"] == 1
    assert utility_stats["median"] is None
    assert utility_stats["iqr"] is None

    # Out of range rating rejection: 0 or 6 must raise ValueError
    invalid_responses = [
        {"participant_code": "CLINICIAN-01", "session_id": "sess-1", "item_id": "learnability", "rating": 6, "na_reason": None}
    ]
    with pytest.raises(ValueError, match="out of range"):
        summarize_questionnaire(invalid_responses, participants)

    invalid_responses_zero = [
        {"participant_code": "CLINICIAN-01", "session_id": "sess-1", "item_id": "learnability", "rating": 0, "na_reason": None}
    ]
    with pytest.raises(ValueError, match="out of range"):
        summarize_questionnaire(invalid_responses_zero, participants)


def test_empty_study_is_not_conducted():
    # If no responses and no clinicians, study_status is NOT_CONDUCTED and outcome metrics null
    summary = summarize_questionnaire([], [])
    assert summary["study_status"] == "NOT_CONDUCTED"
    assert summary["participant_counts"]["clinicians"] == 0
    assert summary["items"] == {}
    assert summary["overall_clinician_median"] is None


def test_feedback_html_escaped():
    participants = [
        {"participant_code": "CLINICIAN-01", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"}
    ]
    raw_feedback = '<script>alert("xss")</script> & "quotes"'
    responses = [
        {
            "participant_code": "CLINICIAN-01",
            "session_id": "sess-1",
            "item_id": "feedback_general",
            "rating": None,
            "na_reason": None,
            "feedback": raw_feedback,
        }
    ]

    summary = summarize_questionnaire(responses, participants, study_status="CONDUCTED")
    feedback_entries = summary["feedback"]
    assert len(feedback_entries) == 1
    escaped = feedback_entries[0]["feedback"]
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "&amp;" in escaped
    assert "&quot;" in escaped


def test_study_status_preservation():
    # Explicit study_status passed must be preserved
    summary_planned = summarize_questionnaire([], [], study_status="PLANNED")
    assert summary_planned["study_status"] == "PLANNED"

    summary_not_conducted = summarize_questionnaire([], [], study_status="NOT_CONDUCTED")
    assert summary_not_conducted["study_status"] == "NOT_CONDUCTED"


@pytest.mark.parametrize(
    "registry_row",
    [
        None,
        {
            "participant_code": "CL-01",
            "role_verified": "unverified",
            "consent_status": "CONSENTED",
            "source_evidence": "consent-record:1",
            "data_origin": "live",
            "disposition": "included",
        },
        {
            "participant_code": "CL-01",
            "role_verified": "verified_clinician",
            "consent_status": "NONE",
            "source_evidence": "consent-record:1",
            "data_origin": "live",
            "disposition": "included",
        },
        {
            "participant_code": "CL-01",
            "role_verified": "verified_clinician",
            "consent_status": "CONSENTED",
            "source_evidence": "developer_self_declared",
            "data_origin": "live",
            "disposition": "included",
        },
    ],
)
def test_questionnaire_cli_quarantines_unverified_clinician_roles(tmp_path, monkeypatch, registry_row):
    participants_path = tmp_path / "participants.csv"
    responses_path = tmp_path / "responses.csv"
    output_dir = tmp_path / "study_output"
    with participants_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["participant_code", "role", "source", "consent_status"])
        writer.writeheader()
        writer.writerow({
            "participant_code": "CL-01",
            "role": "clinician",
            "source": "hospital",
            "consent_status": "CONSENTED",
        })
    with responses_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["participant_code", "session_id", "item_id", "rating", "na_reason", "feedback"],
        )
        writer.writeheader()
        writer.writerow({
            "participant_code": "CL-01",
            "session_id": "S-01",
            "item_id": "usability",
            "rating": "5",
            "na_reason": "",
            "feedback": "self-declared feedback",
        })

    args = [
        "hitl_analysis",
        "--participants", str(participants_path),
        "--questionnaire", str(responses_path),
        "--user-study-output", str(output_dir),
        "--study-status", "CONDUCTED",
    ]
    if registry_row is not None:
        registry_path = tmp_path / "registry.csv"
        with registry_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(registry_row))
            writer.writeheader()
            writer.writerow(registry_row)
        args.extend(["--participant-registry", str(registry_path)])

    monkeypatch.setattr(sys, "argv", args)
    hitl_analysis.main()

    status = json.loads((output_dir / "study_status.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert status["study_status"] == "NOT_CONDUCTED"
    assert status["clinician_count"] == 0
    assert status["has_clinician_validation"] is False
    assert summary["items"] == {}
    assert summary["feedback"] == []


def test_questionnaire_cli_accepts_only_verified_consented_clinician_registry(tmp_path, monkeypatch):
    participants_path = tmp_path / "participants.csv"
    responses_path = tmp_path / "responses.csv"
    registry_path = tmp_path / "registry.csv"
    output_dir = tmp_path / "study_output"

    for path, fields, row in [
        (
            participants_path,
            ["participant_code", "role", "source", "consent_status"],
            {"participant_code": "CL-01", "role": "clinician", "source": "hospital", "consent_status": "CONSENTED"},
        ),
        (
            responses_path,
            ["participant_code", "session_id", "item_id", "rating", "na_reason", "feedback"],
            {"participant_code": "CL-01", "session_id": "S-01", "item_id": "usability", "rating": "5", "na_reason": "", "feedback": "verified feedback"},
        ),
        (
            registry_path,
            ["participant_code", "role_verified", "consent_status", "source_evidence", "data_origin", "disposition"],
            {"participant_code": "CL-01", "role_verified": "verified_clinician", "consent_status": "CONSENTED", "source_evidence": "verified-consent-record:1", "data_origin": "live", "disposition": "included"},
        ),
    ]:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hitl_analysis",
            "--participants", str(participants_path),
            "--questionnaire", str(responses_path),
            "--participant-registry", str(registry_path),
            "--user-study-output", str(output_dir),
            "--study-status", "CONDUCTED",
        ],
    )
    hitl_analysis.main()

    status = json.loads((output_dir / "study_status.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert status["study_status"] == "CONDUCTED"
    assert status["clinician_count"] == 1
    assert status["has_clinician_validation"] is True
    assert summary["items"]["usability"]["n_valid"] == 1
