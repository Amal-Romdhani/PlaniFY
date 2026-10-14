import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Projet } from '../types'

export default function Dashboard() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => client.get<Projet[]>('/projects').then((r) => r.data) })
  return <><PageHeader title="Tableau de bord" description="Une vue claire de vos activités de planification." /><div className="grid gap-4 sm:grid-cols-3"><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Projets suivis</p><p className="mt-2 text-3xl font-bold">{projects.data?.length ?? '—'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Planning</p><p className="mt-2 text-3xl font-bold text-cyan-600">À jour</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Alertes</p><p className="mt-2 text-3xl font-bold">—</p></div></div><div className="mt-8 rounded-xl border border-slate-200 bg-white p-6"><h2 className="font-semibold text-slate-950">Projets récents</h2><div className="mt-4 divide-y divide-slate-100">{projects.data?.slice(0, 5).map((project) => <Link className="flex items-center justify-between py-3 text-sm hover:text-cyan-700" key={project.id} to={`/projects/${project.id}/gantt`}><span>{project.nom}</span><span className="text-slate-400">{project.statut}</span></Link>)}</div></div></>
}
