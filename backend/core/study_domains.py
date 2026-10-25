"""Allowed case workflow and ovary assessment domains."""

STUDY_STATUSES = frozenset(
    {
        "PENDING",
        "ANALYZED",
        "PARTIALLY_REVIEWED",
        "REVIEWED",
        "SIGNED_PRELIM",
        "APPROVED",
        "LOCKED",
    }
)
STUDY_OVARY_SIDES = frozenset({"RIGHT", "LEFT", "BOTH", "UNKNOWN"})
CONTRALATERAL_STATUSES = frozenset({"UNKNOWN", "NOT_VISUALIZED", "NORMAL", "SUSPECTED"})
