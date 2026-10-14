import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Ressource } from '../types'

export default function Resources() {
  const resources = useQuery({ queryKey: ['resources'], queryFn: () => client.get<Ressource[]>('/resources').then((r) => r.data) })
  return <><PageHeader title="Ressources" description="Capacités, compétences et charge maximale." /><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{resources.data?.map((resource) => <div key={resource.id} className="rounded-xl border border-slate-200 bg-white p-5"><div className="flex justify-between"><h2 className="font-semibold">{resource.nom}</h2><span className="text-xs text-slate-500">{resource.type}</span></div><p className="mt-4 text-sm text-slate-500">Charge maximale: <strong className="text-slate-800">{resource.charge_max}</strong></p><div className="mt-4 flex flex-wrap gap-2">{resource.competences.map((skill) => <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700" key={skill}>{skill}</span>)}</div></div>)}</div></>
}
