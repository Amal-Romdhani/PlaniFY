"""Ajoute les compétences requises aux tâches."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_task_required_skills"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Ajoute la liste des compétences d'une tâche."""

    op.add_column(
        "taches",
        sa.Column(
            "competences_requises",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("taches", "competences_requises", server_default=None)


def downgrade() -> None:
    """Supprime la liste des compétences d'une tâche."""

    op.drop_column("taches", "competences_requises")
