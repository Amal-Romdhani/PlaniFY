import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { ActionAgent } from '../types'

export default function Recommendations() {
  const actions = useQuery({ queryKey: ['agent-actions'], queryFn: () => client.get<ActionAgent[]>('/agent-actions').then((r) => r.data), retry: false })
  return <><PageHeader title="Recommandations" description="Les propositions de l'agent restent en attente jusqu'à votre validation." /><div className="space-y-3">{actions.data?.map((action) => <div className="rounded-xl border border-slate-200 bg-white p-5" key={action.id}><div className="flex justify-between gap-4"><div><h2 className="font-semibold">{action.type}</h2><p className="mt-1 text-sm text-slate-500">{action.justification}</p></div><span className="h-fit rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">{action.statut}</span></div></div>)}</div></>
}
