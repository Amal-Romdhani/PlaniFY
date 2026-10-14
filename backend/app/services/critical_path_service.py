from uuid import UUID

from sqlalchemy.orm import Session


def recompute_project_schedule(db: Session, project_id: UUID) -> None:
    """Point d'extension du recalcul déterministe du planning."""

    return None
