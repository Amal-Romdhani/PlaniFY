import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { CPMResult, Projet, Tache } from '../types'

export default function ProjectGantt() {
  const { id = '' } = useParams()
  const project = useQuery({ queryKey: ['project', id], queryFn: () => client.get<Projet>(`/projects/${id}`).then((r) => r.data) })
  const tasks = useQuery({ queryKey: ['tasks', id], queryFn: () => client.get<Tache[]>(`/projects/${id}/tasks`).then((r) => r.data) })
  const cpm = useQuery({ queryKey: ['cpm', id], queryFn: () => client.get<CPMResult>(`/projects/${id}/critical-path`).then((r) => r.data) })
  return <><PageHeader title={project.data?.nom || 'Planning'} description="Les dates et marges proviennent du service CPM backend." action={<Link className="text-sm font-medium text-cyan-700" to="/projects">← Retour aux projets</Link>} /><div className="mb-5 grid gap-4 sm:grid-cols-3"><div className="rounded-xl bg-slate-950 p-5 text-white"><p className="text-sm text-slate-300">Fin projet</p><p className="mt-2 text-xl font-bold">{cpm.data?.date_fin_projet || '—'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Durée totale</p><p className="mt-2 text-xl font-bold">{cpm.data ? `${cpm.data.duree_totale} jours ouvrés` : '—'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Chemin critique</p><p className="mt-2 text-xl font-bold">{cpm.data?.critical_path.length ?? '—'} tâches</p></div></div><div className="overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="grid grid-cols-[1.4fr_1fr_1fr_90px] gap-4 border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500"><span>Tâche</span><span>Début</span><span>Fin</span><span>Marge</span></div>{tasks.data?.map((task) => { const result = cpm.data?.tasks[task.id]; return <div key={task.id} className="grid grid-cols-[1.4fr_1fr_1fr_90px] gap-4 border-b border-slate-100 px-5 py-4 text-sm last:border-0"><span className="font-medium">{task.nom}{result?.est_critique && <span className="ml-2 rounded bg-red-50 px-2 py-1 text-xs text-red-600">Critique</span>}</span><span>{result?.es || task.date_debut_prevue}</span><span>{result?.ef || task.date_fin_prevue}</span><span>{result?.marge ?? task.marge} j</span></div> })}</div></>
}
