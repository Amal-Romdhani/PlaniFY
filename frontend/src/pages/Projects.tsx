import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import PageHeader from '../components/PageHeader'
import type { Projet } from '../types'

export default function Projects() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => client.get<Projet[]>('/projects').then((r) => r.data) })
  const create = useMutation({ mutationFn: () => client.post('/projects', { nom: name, date_debut: new Date().toISOString().slice(0, 10), date_fin: new Date(Date.now() + 2592000000).toISOString().slice(0, 10), statut: 'PLANIFIE' }), onSuccess: () => { setName(''); queryClient.invalidateQueries({ queryKey: ['projects'] }) } })
  function submit(event: FormEvent) { event.preventDefault(); if (name.trim()) create.mutate() }
  return <><PageHeader title="Projets" description="Pilotez vos projets et consultez leur planning." /><form onSubmit={submit} className="mb-6 flex max-w-xl gap-2"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom du nouveau projet" className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2.5" /><button className="rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white">Créer</button></form><div className="grid gap-4 lg:grid-cols-2">{projects.data?.map((project) => <Link to={`/projects/${project.id}/gantt`} key={project.id} className="rounded-xl border border-slate-200 bg-white p-5 hover:border-cyan-300"><div className="flex items-start justify-between"><h2 className="font-semibold">{project.nom}</h2><span className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs font-medium text-cyan-700">{project.statut}</span></div><p className="mt-3 text-sm text-slate-500">{project.description || 'Aucune description renseignée.'}</p><p className="mt-5 text-xs text-slate-400">{project.date_debut} → {project.date_fin}</p></Link>)}</div></>
}
