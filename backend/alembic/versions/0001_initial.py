"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée le schéma initial de PlaniFY."""

    user_role = sa.Enum("CHEF_PROJET", "MEMBRE", "ADMIN", name="user_role")
    project_status = sa.Enum(
        "PLANIFIE", "EN_COURS", "TERMINE", name="project_status"
    )
    milestone_status = sa.Enum(
        "A_VENIR", "ATTEINT", "EN_RETARD", name="milestone_status"
    )
    task_status = sa.Enum("A_FAIRE", "EN_COURS", "TERMINEE", name="task_status")
    dependency_type = sa.Enum("FIN_DEBUT", name="dependency_type")
    resource_type = sa.Enum("HUMAINE", "MATERIELLE", name="resource_type")
    unavailability_reason = sa.Enum(
        "CONGE", "MALADIE", "AUTRE", name="unavailability_reason"
    )
    agent_action_type = sa.Enum(
        "REAFFECTATION", "DECALAGE", "ALERTE", name="agent_action_type"
    )
    agent_action_status = sa.Enum(
        "EN_ATTENTE", "ACCEPTEE", "REJETEE", name="agent_action_status"
    )
    alert_type = sa.Enum(
        "RETARD", "SURALLOCATION", "CONFLIT_INDISPONIBILITE", name="alert_type"
    )
    risk_level = sa.Enum("FAIBLE", "MOYEN", "ELEVE", name="risk_level")

    op.create_table(
        "utilisateurs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("mot_de_passe_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_utilisateurs_email", "utilisateurs", ["email"], unique=False)

    op.create_table(
        "projets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=False),
        sa.Column("statut", project_status, nullable=False),
        sa.Column(
            "chef_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id"),
            nullable=False,
        ),
    )
    op.create_table(
        "ressources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("type", resource_type, nullable=False),
        sa.Column("competences", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("charge_max", sa.Integer(), nullable=False, server_default="8"),
        sa.Column(
            "utilisateur_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("utilisateur_id", name="uq_ressources_utilisateur"),
    )
    op.create_table(
        "jalons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "projet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("statut", milestone_status, nullable=False),
    )
    op.create_table(
        "taches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "projet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "jalon_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jalons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("duree", sa.Integer(), nullable=False),
        sa.Column("date_debut_prevue", sa.Date(), nullable=False),
        sa.Column("date_fin_prevue", sa.Date(), nullable=False),
        sa.Column("avancement", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("est_critique", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marge", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("statut", task_status, nullable=False),
        sa.CheckConstraint("duree >= 0", name="ck_taches_duree_positive"),
        sa.CheckConstraint("avancement BETWEEN 0 AND 100", name="ck_taches_avancement"),
        sa.CheckConstraint("marge >= 0", name="ck_taches_marge_positive"),
    )
    op.create_table(
        "dependances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tache_amont_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tache_aval_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", dependency_type, nullable=False),
        sa.UniqueConstraint(
            "tache_amont_id", "tache_aval_id", name="uq_dependances_taches"
        ),
        sa.CheckConstraint(
            "tache_amont_id <> tache_aval_id",
            name="ck_dependances_taches_distinctes",
        ),
    )
    op.create_table(
        "affectations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ressource_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ressources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tache_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("charge_allouee", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "ressource_id", "tache_id", name="uq_affectations_ressource_tache"
        ),
    )
    op.create_table(
        "indisponibilites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ressource_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ressources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=False),
        sa.Column("motif", unavailability_reason, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="INTERNE"),
        sa.CheckConstraint(
            "date_fin >= date_debut", name="ck_indisponibilites_dates_valides"
        ),
    )
    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "projet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tache_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "indisponibilite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("indisponibilites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", agent_action_type, nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("statut", agent_action_status, nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_decision", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decideur_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_table(
        "alertes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "projet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("type", alert_type, nullable=False),
        sa.Column("niveau_risque", risk_level, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("date_creation", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolue", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Supprime le schéma initial de PlaniFY."""

    op.drop_table("alertes")
    op.drop_table("agent_actions")
    op.drop_table("indisponibilites")
    op.drop_table("affectations")
    op.drop_table("dependances")
    op.drop_table("taches")
    op.drop_table("jalons")
    op.drop_table("ressources")
    op.drop_table("projets")
    op.drop_index("ix_utilisateurs_email", table_name="utilisateurs")
    op.drop_table("utilisateurs")

    for enum_name in (
        "risk_level",
        "alert_type",
        "agent_action_status",
        "agent_action_type",
        "unavailability_reason",
        "resource_type",
        "dependency_type",
        "task_status",
        "milestone_status",
        "project_status",
        "user_role",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
