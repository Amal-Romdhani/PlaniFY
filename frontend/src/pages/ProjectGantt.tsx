import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import client from '../api/client'
import GanttChart from '../components/GanttChart'
import PageHeader from '../components/PageHeader'
import type { CPMResult, Projet, Tache } from '../types'

export default function ProjectGantt() {
  const { id = '' } = useParams()
  const project = useQuery({ queryKey: ['project', id], queryFn: () => client.get<Projet>(`/projects/${id}`).then((r) => r.data) })
  const tasks = useQuery({ queryKey: ['tasks', id], queryFn: () => client.get<Tache[]>(`/projects/${id}/tasks`).then((r) => r.data) })
  const cpm = useQuery({ queryKey: ['cpm', id], queryFn: () => client.get<CPMResult>(`/projects/${id}/critical-path`).then((r) => r.data) })
  return <><PageHeader title={project.data?.nom || 'Planning'} description="Les dates et marges proviennent du service CPM backend." action={<Link className="text-sm font-medium text-cyan-700" to="/projects">← Retour aux projets</Link>} /><div className="mb-5 grid gap-4 sm:grid-cols-3"><div className="rounded-xl bg-slate-950 p-5 text-white"><p className="text-sm text-slate-300">Fin projet</p><p className="mt-2 text-xl font-bold">{cpm.data?.date_fin_projet || '—'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Durée totale</p><p className="mt-2 text-xl font-bold">{cpm.data ? `${cpm.data.duree_totale} jours ouvrés` : '—'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Chemin critique</p><p className="mt-2 text-xl font-bold">{cpm.data?.critical_path.length ?? '—'} tâches</p></div></div><GanttChart projectId={id} onProjectReload={() => { void tasks.refetch(); void cpm.refetch() }} /></>
}
