import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { DashboardData, Projet } from '../types'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function Dashboard() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => client.get<Projet[]>('/projects').then((r) => r.data) })
  const [projectId, setProjectId] = useState('')
  const dashboard = useQuery({
    queryKey: ['dashboard', projectId],
    queryFn: () => client.get<DashboardData>(`/projects/${projectId}/dashboard`).then((r) => r.data),
    enabled: Boolean(projectId),
  })
  const data = dashboard.data
  const statusData = data ? [
    { name: 'À faire', value: data.nb_taches.a_faire, color: '#94a3b8' },
    { name: 'En cours', value: data.nb_taches.en_cours, color: '#06b6d4' },
    { name: 'Terminées', value: data.nb_taches.terminee, color: '#22c55e' },
  ] : []
  async function resolveAlert(id: string) {
    await client.patch(`/alerts/${id}/resolve`)
    await dashboard.refetch()
  }
  return <><PageHeader title="Tableau de bord" description="Les indicateurs sont calculés par le backend." action={<Link className="text-sm font-medium text-cyan-700" to="/projects">Gérer les projets →</Link>} />
    <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4"><label className="text-sm font-medium text-slate-700">Projet<select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="mt-2 block w-full max-w-xl rounded-lg border border-slate-200 px-3 py-2"><option value="">Sélectionner un projet</option>{projects.data?.map((project) => <option value={project.id} key={project.id}>{project.nom}</option>)}</select></label></div>
    {!projectId && <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">Sélectionnez un projet pour afficher son tableau de bord.</div>}
    {data && <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Kpi title="Avancement global" value={`${data.avancement_global}%`} /><Kpi title="Jours restants" value={String(data.jours_restants)} /><Kpi title="Risque global" value={data.risques.niveau_global} /><Kpi title="Tâches critiques en retard" value={String(data.risques.taches_critiques_en_retard)} /></div>
      {data.nb_recommandations_en_attente > 0 && <Link to="/recommendations" className="mt-5 block rounded-xl bg-cyan-50 p-4 text-sm font-semibold text-cyan-800 hover:bg-cyan-100">{data.nb_recommandations_en_attente} recommandation(s) de l’agent en attente →</Link>}
      <div className="mt-5 grid gap-5 lg:grid-cols-2"><Panel title="Avancement par statut"><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={statusData} dataKey="value" nameKey="name" outerRadius={85} label>{statusData.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></Panel><Panel title="Charge des ressources (4 semaines)"><ResponsiveContainer width="100%" height={240}><BarChart data={data.charge_par_ressource}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="nom" /><YAxis unit="%" /><Tooltip formatter={(value) => `${value ?? 0}%`} /><Bar dataKey="pourcentage_utilisation" name="Utilisation" fill="#06b6d4" /></BarChart></ResponsiveContainer></Panel></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2"><Panel title="Échéances et jalons"><DeadlineList title="Jalons à venir" items={data.jalons_a_venir} /><DeadlineList title="Jalons en retard" items={data.jalons_en_retard} danger /></Panel><Panel title="Alertes non résolues">{data.alertes_non_resolues.length === 0 ? <p className="text-sm text-slate-500">Aucune alerte non résolue.</p> : <ul className="space-y-3">{data.alertes_non_resolues.map((alert) => <li className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 p-3 text-sm" key={alert.id}><span><strong className="mr-2 text-orange-700">{alert.niveau_risque}</strong>{alert.message}</span><button onClick={() => void resolveAlert(alert.id)} className="shrink-0 text-xs font-semibold text-cyan-700">Marquer résolue</button></li>)}</ul>}</Panel></div>
      <div className="mt-5 rounded-xl border border-slate-200 bg-white p-5"><h2 className="font-semibold text-slate-950">Ressources sur-allouées</h2>{data.charge_par_ressource.filter((resource) => resource.est_suralouee).length === 0 ? <p className="mt-3 text-sm text-slate-500">Aucune ressource sur-allouée.</p> : <ul className="mt-3 flex flex-wrap gap-2">{data.charge_par_ressource.filter((resource) => resource.est_suralouee).map((resource) => <li className="rounded-full bg-red-50 px-3 py-1 text-sm text-red-700" key={resource.resource_id}>{resource.nom} ({resource.pourcentage_utilisation}%)</li>)}</ul>}</div>
    </>}
  </>
}

function Kpi({ title, value }: { title: string; value: string }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">{title}</p><p className="mt-2 text-2xl font-bold text-slate-950">{value}</p></div>
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="mb-4 font-semibold text-slate-950">{title}</h2>{children}</section>
}

function DeadlineList({ title, items, danger = false }: { title: string; items: DashboardData['jalons_a_venir']; danger?: boolean }) {
  return <div className="mb-4 last:mb-0"><h3 className={`mb-2 text-sm font-medium ${danger ? 'text-red-700' : 'text-slate-600'}`}>{title}</h3>{items.length === 0 ? <p className="text-sm text-slate-400">Aucun jalon.</p> : <ul className="space-y-2">{items.map((item) => <li className="flex justify-between text-sm" key={item.id}><span>{item.nom}</span><span className="text-slate-500">{item.date}</span></li>)}</ul>}</div>
}
