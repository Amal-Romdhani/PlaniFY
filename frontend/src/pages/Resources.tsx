import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Indisponibilite, Ressource } from '../types'

export default function Resources() {
  const resources = useQuery({ queryKey: ['resources'], queryFn: () => client.get<Ressource[]>('/resources').then((r) => r.data) })
  const [tab, setTab] = useState<'resources' | 'absences'>('resources')
  const absences = useQuery({ queryKey: ['team-unavailabilities'], queryFn: () => client.get<Indisponibilite[]>('/unavailabilities').then((r) => r.data), enabled: tab === 'absences' })
  return <><PageHeader title="Ressources" description="Capacités, compétences et charge maximale." /><div className="mb-5 flex gap-2"><button onClick={() => setTab('resources')} className={`rounded-lg px-4 py-2 text-sm ${tab === 'resources' ? 'bg-slate-950 text-white' : 'border bg-white'}`}>Ressources</button><button onClick={() => setTab('absences')} className={`rounded-lg px-4 py-2 text-sm ${tab === 'absences' ? 'bg-slate-950 text-white' : 'border bg-white'}`}>Absences de l'équipe</button></div>{tab === 'resources' ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{resources.data?.map((resource) => <div key={resource.id} className="rounded-xl border border-slate-200 bg-white p-5"><div className="flex justify-between"><h2 className="font-semibold">{resource.nom}</h2><span className="text-xs text-slate-500">{resource.type}</span></div><p className="mt-4 text-sm text-slate-500">Charge maximale: <strong className="text-slate-800">{resource.charge_max}</strong></p><div className="mt-4 flex flex-wrap gap-2">{resource.competences.map((skill) => <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700" key={skill}>{skill}</span>)}</div></div>)}</div> : <div className="rounded-xl border border-slate-200 bg-white">{absences.data?.map((item) => <div key={item.id} className="flex justify-between border-b border-slate-100 px-5 py-4 text-sm last:border-0"><span>{resources.data?.find((resource) => resource.id === item.ressource_id)?.nom ?? 'Ressource'}</span><span>{item.date_debut} → {item.date_fin} · {item.motif === 'MALADIE' ? 'Absence' : item.motif}</span></div>)}</div>}</>
}
