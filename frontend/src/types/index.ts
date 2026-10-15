export type UserRole = 'CHEF_PROJET' | 'MEMBRE' | 'ADMIN'
export type ProjectStatus = 'PLANIFIE' | 'EN_COURS' | 'TERMINE'
export type TaskStatus = 'A_FAIRE' | 'EN_COURS' | 'TERMINEE'
export type ResourceType = 'HUMAINE' | 'MATERIELLE'
export type ActionStatus = 'EN_ATTENTE' | 'ACCEPTEE' | 'REJETEE'
export type ActionStrategy = 'DECALAGE' | 'REAFFECTATION' | 'ALERTE'
export type ValidationStatus = 'VALIDE' | 'REGENERE' | 'REPLI'

export interface Utilisateur {
  id: string
  nom: string
  email: string
  role: UserRole
}

export interface Projet {
  id: string
  nom: string
  description?: string | null
  date_debut: string
  date_fin: string
  statut: ProjectStatus
  chef_id: string
}

export interface Tache {
  id: string
  projet_id: string
  jalon_id?: string | null
  nom: string
  duree: number
  competences_requises: string[]
  date_debut_prevue: string
  date_fin_prevue: string
  avancement: number
  est_critique: boolean
  marge: number
  statut: TaskStatus
}

export interface Dependance {
  id: string
  tache_amont_id: string
  tache_aval_id: string
  type: 'FIN_DEBUT'
}

export interface Ressource {
  id: string
  nom: string
  type: ResourceType
  competences: string[]
  charge_max: number
  utilisateur_id?: string | null
}

export interface Indisponibilite {
  id: string
  ressource_id: string
  date_debut: string
  date_fin: string
  motif: 'CONGE' | 'MALADIE' | 'AUTRE'
  source: string
}

export interface ActionAgent {
  id: string
  projet_id: string
  tache_id?: string | null
  type: 'REAFFECTATION' | 'DECALAGE' | 'ALERTE'
  justification: string
  payload: Record<string, unknown>
  statut: ActionStatus
  date_creation: string
  date_decision?: string | null
  decideur_id?: string | null
  decideur_nom?: string | null
  simulation_result?: SimulationResult | null
  validation_status?: ValidationStatus | null
}

export interface SimulationConflict {
  tache_id: string
  nom: string
  jours_impactes: number
  est_critique: boolean
  marge: number
}

export interface SimulationResult {
  task_id: string
  ancienne_date_fin_tache: string
  nouvelle_date_fin_tache: string
  ancienne_date_fin_projet: string
  nouvelle_date_fin_projet: string
  retard_projet_jours: number
  ancienne_marge?: number | null
  nouvelle_marge?: number | null
  taches_nouvellement_critiques: string[]
  nouveaux_conflits: SimulationConflict[]
  ressource_actuelle_id?: string | null
  nouvelle_ressource_id?: string | null
  reaffectation_possible?: boolean | null
  problemes: string[]
}

export interface Alerte {
  id: string
  projet_id: string
  type: 'RETARD' | 'SURALLOCATION' | 'CONFLIT_INDISPONIBILITE'
  message: string
  niveau: 'FAIBLE' | 'MOYEN' | 'ELEVE'
}

export interface CPMTaskResult {
  es: string
  ef: string
  ls: string
  lf: string
  marge: number
  est_critique: boolean
}

export interface CPMResult {
  tasks: Record<string, CPMTaskResult>
  critical_path: string[]
  date_fin_projet: string
  duree_totale: number
}

export interface DashboardData {
  avancement_global: number
  date_debut: string
  date_fin_prevue: string
  jours_restants: number
  nb_taches: {
    a_faire: number
    en_cours: number
    terminee: number
  }
  jalons_a_venir: DashboardMilestone[]
  jalons_en_retard: DashboardMilestone[]
  charge_par_ressource: DashboardResourceLoad[]
  ressources_suralouees: string[]
  risques: {
    taches_critiques_en_retard: number
    conflits_ouverts: number
    ressources_suralouees: number
    niveau_global: 'FAIBLE' | 'MOYEN' | 'ELEVE'
  }
  alertes_non_resolues: DashboardAlert[]
  nb_recommandations_en_attente: number
}

export interface DashboardMilestone {
  id: string
  nom: string
  date: string
  statut: string
}

export interface DashboardResourceLoad {
  resource_id: string
  nom: string
  pourcentage_utilisation: number
  charge_max: number
  charge_max_journaliere: number
  est_suralouee: boolean
}

export interface DashboardAlert {
  id: string
  type: string
  niveau_risque: string
  message: string
  date_creation: string
}
