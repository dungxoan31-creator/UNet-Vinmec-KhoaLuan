"""Canonical client-side HITL telemetry event vocabulary."""

CLIENT_HITL_EVENT_TYPES = frozenset(
    {
        "SESSION_START",
        "INFERENCE_START",
        "INFERENCE_END",
        "INFERENCE_FAILED",
        "PREDICTION_VIEWED",
        "CORRECTION_START",
        "EDIT_COMMITTED",
        "UNDO",
        "REDO",
        "RESET_AI",
        "CLEAR_MASK",
        "PAUSE",
        "RESUME",
        "CONFIRM_ATTEMPT",
        "CONFIRM_ACK",
        "SAVE_FAILED",
        "EXPORT_SUCCEEDED",
        "EXPORT_FAILED",
        "SESSION_ABORTED",
    }
)

SERVER_HITL_EVENT_TYPES = frozenset({"CONFIRM_SUCCEEDED"})

HITL_EVENT_TYPES = CLIENT_HITL_EVENT_TYPES | SERVER_HITL_EVENT_TYPES
