"""
Tests for user study and questionnaire summarization.
Verifies honest handling of clinician vs technical participants,
non-fabrication of metrics, Likert statistics oracles, and HTML escaping.
"""

import html
import pytest
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
