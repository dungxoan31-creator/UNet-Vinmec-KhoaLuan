"""Fail-closed research export boundary for the unverified prototype."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.db.database import UserModel


def build_research_bundle(
    db: Session,
    study_id: str,
    review_ids: list[str],
    expected_revision: int,
    actor: UserModel,
    ethics_approval_code: str,
    patient_consent_confirmed: bool = False,
) -> bytes:
    """Reject export until authorization, consent, and de-identification are verifiable."""
    if not patient_consent_confirmed:
        raise HTTPException(
            status_code=403,
            detail="Research export requires a recorded participant consent decision.",
        )
    if not ethics_approval_code or not ethics_approval_code.strip():
        raise HTTPException(
            status_code=422,
            detail="A research approval code is required.",
        )
    raise HTTPException(
        status_code=501,
        detail=(
            "Research export is disabled until approval, consent, and de-identification "
            "can be verified from trusted records."
        ),
    )
