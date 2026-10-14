import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Indisponibilite, Ressource } from '../types'

export default function Unavailabilities() {
  const [month, setMonth] = useState(new Date())
  const [error, setError] = useState<string | null>(null)
  const items = useQuery({ queryKey: ['unavailabilities'], queryFn: () => client.get<Indisponibilite[]>('/unavailabilities').then((r) => r.data) })
  const resources = useQuery({ queryKey: ['my-resource'], queryFn: () => client.get<Ressource[]>('/resources').then((r) => r.data) })
  const days = monthDays(month)
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      await client.post('/unavailabilities', {
        ressource_id: resources.data?.[0]?.id,
        date_debut: String(form.get('date_debut')),
        date_fin: String(form.get('date_fin')),
        motif: String(form.get('motif')),
      })
      event.currentTarget.reset()
      await items.refetch()
    } catch {
      setError('Impossible de déclarer cette absence. Vérifiez les dates et les chevauchements.')
    }
  }
  async function remove(id: string) {
    try {
      await client.delete(`/unavailabilities/${id}`)
      await items.refetch()
    } catch {
      setError('Impossible de supprimer cette absence.')
    }
  }
  return <><PageHeader title="Mes indisponibilités" description="Gérez vos périodes d'indisponibilité." />
    <p className="mb-5 rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-800">Seul votre chef de projet et l'administrateur voient ces informations.</p>
    {error && <p role="alert" className="mb-5 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
    <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <section className="rounded-xl border border-slate-200 bg-white p-5"><div className="mb-4 flex items-center justify-between"><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="rounded border px-3 py-1">←</button><h2 className="font-semibold">{month.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })}</h2><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="rounded border px-3 py-1">→</button></div><div className="grid grid-cols-7 gap-px overflow-hidden rounded border bg-slate-200">{['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((day) => <div className="bg-slate-50 p-2 text-center text-xs font-semibold text-slate-500" key={day}>{day}</div>)}{days.map((day, index) => { const iso = day ? formatDate(day) : ''; const absence = items.data?.find((item) => iso >= item.date_debut && iso <= item.date_fin); return <div className={`min-h-20 bg-white p-2 text-xs ${!day ? 'bg-slate-50' : ''}`} key={`${iso}-${index}`}>{day && <><span className="font-medium">{day.getDate()}</span>{absence && <span className="mt-2 block rounded bg-cyan-100 px-1 py-1 text-cyan-800">Absence</span>}</>}</div> })}</div></section>
      <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Déclarer une absence</h2><form onSubmit={create} className="mt-4 space-y-3"><label className="block text-sm">Date de début<input name="date_debut" type="date" required className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="block text-sm">Date de fin<input name="date_fin" type="date" required className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="block text-sm">Motif<select name="motif" defaultValue="CONGE" className="mt-1 w-full rounded-lg border px-3 py-2"><option value="CONGE">Congé</option><option value="MALADIE">Maladie</option><option value="AUTRE">Autre</option></select></label><button className="w-full rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-white">Déclarer</button></form></section>
    </div>
    <section className="mt-5 rounded-xl border border-slate-200 bg-white"><h2 className="border-b border-slate-100 p-5 font-semibold">Mes absences</h2>{items.data?.map((item) => <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 text-sm last:border-0" key={item.id}><span>{item.date_debut} → {item.date_fin} · {item.motif}</span><button onClick={() => void remove(item.id)} className="text-red-600">Supprimer</button></div>)}</section>
  </>
}

function formatDate(value: Date) { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}` }
function monthDays(month: Date): Array<Date | null> {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const offset = (first.getDay() + 6) % 7
  const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  return [...Array(offset).fill(null), ...Array.from({ length: count }, (_, index) => new Date(month.getFullYear(), month.getMonth(), index + 1))]
}
