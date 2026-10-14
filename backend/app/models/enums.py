from enum import Enum


class UserRole(str, Enum):
    CHEF_PROJET = "CHEF_PROJET"
    MEMBRE = "MEMBRE"
    ADMIN = "ADMIN"


class ProjectStatus(str, Enum):
    PLANIFIE = "PLANIFIE"
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"


class MilestoneStatus(str, Enum):
    A_VENIR = "A_VENIR"
    ATTEINT = "ATTEINT"
    EN_RETARD = "EN_RETARD"


class TaskStatus(str, Enum):
    A_FAIRE = "A_FAIRE"
    EN_COURS = "EN_COURS"
    TERMINEE = "TERMINEE"


class DependencyType(str, Enum):
    FIN_DEBUT = "FIN_DEBUT"


class ResourceType(str, Enum):
    HUMAINE = "HUMAINE"
    MATERIELLE = "MATERIELLE"


class UnavailabilityReason(str, Enum):
    CONGE = "CONGE"
    MALADIE = "MALADIE"
    AUTRE = "AUTRE"


class AgentActionType(str, Enum):
    REAFFECTATION = "REAFFECTATION"
    DECALAGE = "DECALAGE"
    ALERTE = "ALERTE"


class AgentActionStatus(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ACCEPTEE = "ACCEPTEE"
    REJETEE = "REJETEE"


class AlertType(str, Enum):
    RETARD = "RETARD"
    SURALLOCATION = "SURALLOCATION"
    CONFLIT_INDISPONIBILITE = "CONFLIT_INDISPONIBILITE"


class RiskLevel(str, Enum):
    FAIBLE = "FAIBLE"
    MOYEN = "MOYEN"
    ELEVE = "ELEVE"
