"""Allowed HITL session roles, origins, and lifecycle states."""

HITL_SESSION_ROLES = frozenset({"clinician", "technical_tester"})
HITL_SESSION_DATA_ORIGINS = frozenset({"live", "technical_fixture", "demo"})

# ACTIVE is retained because existing sessions in the workspace use this
# non-terminal state. New sessions are created as IN_PROGRESS.
HITL_SESSION_STATUSES = frozenset(
    {"IN_PROGRESS", "ACTIVE", "COMPLETED", "ABORTED", "INCOMPLETE"}
)
