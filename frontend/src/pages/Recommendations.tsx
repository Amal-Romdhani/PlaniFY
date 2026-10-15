import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { ActionAgent, Projet, SimulationResult, ValidationStatus } from '../types'

type ApiError = { response?: { status?: number; data?: { detail?: string } } }

function errorMessage(error: unknown): string {
  const status = (error as ApiError).response?.status
  if (status === 403) return 'Vous n’avez pas les droits pour cette action.'
  if (status === 409) return (error as ApiError).response?.data?.detail || 'Le planning a changé. Relancez la simulation.'
  return 'Une erreur est survenue. Veuillez réessayer.'
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('fr-FR').format(new Date(`${value}T00:00:00`))
}

function validationClass(status?: ValidationStatus | null): string {
  if (status === 'VALIDE') return 'bg-emerald-50 text-emerald-700'
  if (status === 'REGENERE') return 'bg-blue-50 text-blue-700'
  return 'bg-slate-100 text-slate-600'
}

function SimulationComparison({ simulation }: { simulation?: SimulationResult | null }) {
  if (!simulation) return <p className="text-sm text-slate-500">Aucun résultat de simulation disponible.</p>
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      <div><dt className="text-slate-500">Fin de la tâche</dt><dd className="font-medium">{formatDate(simulation.ancienne_date_fin_tache)} → {formatDate(simulation.nouvelle_date_fin_tache)}</dd></div>
      <div><dt className="text-slate-500">Marge</dt><dd className="font-medium">{simulation.ancienne_marge ?? '—'} → {simulation.nouvelle_marge ?? '—'} jours</dd></div>
      <div><dt className="text-slate-500">Fin du projet</dt><dd className="font-medium">{formatDate(simulation.ancienne_date_fin_projet)} → {formatDate(simulation.nouvelle_date_fin_projet)}</dd></div>
      <div><dt className="text-slate-500">Impact projet</dt><dd className="font-medium">{simulation.retard_projet_jours > 0 ? `+${simulation.retard_projet_jours} jours` : 'Aucun retard'}</dd></div>
    </dl>
  )
}

function ActionCard({ action, onError }: { action: ActionAgent; onError: (message: string) => void }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const params = (action.payload.params ?? {}) as Record<string, unknown>
  const [delayDays, setDelayDays] = useState(Number(params.delay_days ?? 1))
  const [newResourceId, setNewResourceId] = useState(String(params.new_resource_id ?? ''))
  const [confirming, setConfirming] = useState(false)
  const mutate = useMutation({
    mutationFn: (operation: 'accept' | 'reject') => client.post(`/agent/actions/${action.id}/${operation}`),
    onSuccess: () => { setConfirming(false); queryClient.invalidateQueries({ queryKey: ['agent-actions'] }) },
    onError: (error) => onError(errorMessage(error)),
  })
  const modify = useMutation({
    mutationFn: () => client.post(`/agent/actions/${action.id}/modify`, {
      strategy: action.type,
      delay_days: action.type === 'DECALAGE' ? delayDays : undefined,
      new_resource_id: action.type === 'REAFFECTATION' ? newResourceId : undefined,
    }),
    onSuccess: () => { setEditing(false); queryClient.invalidateQueries({ queryKey: ['agent-actions'] }) },
    onError: (error) => onError(errorMessage(error)),
  })
  const pending = action.statut === 'EN_ATTENTE'
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">{action.type}</p><h2 className="mt-1 font-semibold text-slate-950">Tâche {action.tache_id ?? 'non renseignée'}</h2></div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${action.statut === 'EN_ATTENTE' ? 'bg-amber-50 text-amber-700' : action.statut === 'ACCEPTEE' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>{action.statut}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{action.justification}</p>
      <div className="mt-4 rounded-lg bg-slate-50 p-4"><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold">Comparaison de la simulation</h3><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${validationClass(action.validation_status)}`}>{action.validation_status ?? 'NON RENSEIGNÉ'}</span></div><SimulationComparison simulation={action.simulation_result} /></div>
      {action.date_decision && <p className="mt-3 text-xs text-slate-500">Décidée le {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' }).format(new Date(action.date_decision))}{action.decideur_nom ? ` par ${action.decideur_nom}` : ''}</p>}
      {pending && <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => setConfirming(true)} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Valider</button>
        <button onClick={() => mutate.mutate('reject')} className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700">Rejeter</button>
        <button onClick={() => setEditing((value) => !value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">Modifier</button>
      </div>}
      {confirming && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4"><p className="text-sm text-amber-900">Confirmer l’application de cette proposition au planning ?</p><div className="mt-3 flex gap-2"><button onClick={() => mutate.mutate('accept')} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Confirmer</button><button onClick={() => setConfirming(false)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">Annuler</button></div></div>}
      {editing && <form onSubmit={(event: FormEvent) => { event.preventDefault(); modify.mutate() }} className="mt-4 grid gap-3 rounded-lg border border-cyan-100 bg-cyan-50 p-4 sm:grid-cols-[1fr_auto]"><label className="text-sm font-medium">{action.type === 'DECALAGE' ? 'Nouveau décalage (jours ouvrés)' : 'Nouvelle ressource'}{action.type === 'DECALAGE' ? <input type="number" min="0" value={delayDays} onChange={(event) => setDelayDays(Number(event.target.value))} className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2" /> : <input required value={newResourceId} onChange={(event) => setNewResourceId(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2" />}</label><button disabled={modify.isPending} className="self-end rounded-lg bg-cyan-700 px-3 py-2 text-sm font-semibold text-white">Re-simuler</button></form>}
    </article>
  )
}

export default function Recommendations() {
  const [projectId, setProjectId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => client.get<Projet[]>('/projects').then((response) => response.data) })
  const actions = useQuery({
    queryKey: ['agent-actions', projectId],
    queryFn: async () => {
      const responses = await Promise.all(
        (['EN_ATTENTE', 'ACCEPTEE', 'REJETEE'] as const).map((statut) =>
          client.get<ActionAgent[]>('/agent/actions', {
            params: { statut, project_id: projectId || undefined },
          }),
        ),
      )
      return responses.flatMap((response) => response.data)
    },
    refetchInterval: 30000,
    retry: false,
  })
  const pending = actions.data?.filter((action) => action.statut === 'EN_ATTENTE') ?? []
  const history = actions.data?.filter((action) => action.statut !== 'EN_ATTENTE') ?? []
  return <><PageHeader title="Recommandations de l’agent" description="Les propositions sont simulées avant validation humaine." action={<select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"><option value="">Tous les projets</option>{projects.data?.map((project) => <option key={project.id} value={project.id}>{project.nom}</option>)}</select>} />
    {actions.isError && <div role="alert" className="mb-5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{errorMessage(actions.error)}</div>}
    {error && <div role="alert" className="mb-5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}<button onClick={() => setError(null)} className="ml-3 underline">Fermer</button></div>}
    <section><h2 className="mb-3 text-lg font-semibold">À valider ({pending.length})</h2><div className="space-y-4">{pending.length ? pending.map((action) => <ActionCard key={action.id} action={action} onError={setError} />) : <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Aucune recommandation en attente.</p>}</div></section>
    <section className="mt-10"><h2 className="mb-3 text-lg font-semibold">Historique des décisions</h2><div className="space-y-3">{history.length ? history.map((action) => <ActionCard key={action.id} action={action} onError={setError} />) : <p className="text-sm text-slate-500">Aucune action décidée.</p>}</div></section>
  </>
}
