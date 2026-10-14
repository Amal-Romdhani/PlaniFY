import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Indisponibilite } from '../types'

export default function Unavailabilities() {
  const items = useQuery({ queryKey: ['unavailabilities'], queryFn: () => client.get<Indisponibilite[]>('/unavailabilities').then((r) => r.data) })
  return <><PageHeader title="Mes indisponibilités" description="Gérez vos périodes d'indisponibilité." /><div className="rounded-xl border border-slate-200 bg-white"><div className="grid grid-cols-3 border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase text-slate-500"><span>Début</span><span>Fin</span><span>Type</span></div>{items.data?.map((item) => <div className="grid grid-cols-3 border-b border-slate-100 px-5 py-4 text-sm last:border-0" key={item.id}><span>{item.date_debut}</span><span>{item.date_fin}</span><span>{item.motif}</span></div>)}</div></>
}
