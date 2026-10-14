import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import Gantt from 'frappe-gantt'
import '../../node_modules/frappe-gantt/src/styles/gantt.css'
import client from '../api/client'
import type { CPMResult, Dependance, Ressource, Tache } from '../types'

interface Jalon {
  id: string
  nom: string
  date: string
}

interface Affectation {
  id: string
  ressource_id: string
  tache_id: string
  charge_allouee: number
}

interface Conflit {
  tache_id: string
  jours_impactes: number
}

interface GanttChartProps {
  projectId: string
  onProjectReload?: () => void
}

interface ChartTask {
  id: string
  name: string
  start: string
  end: string
  progress: number
  dependencies?: string
  custom_class?: string
}

const toDateInput = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export default function GanttChart({ projectId, onProjectReload }: GanttChartProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const ganttRef = useRef<Gantt | null>(null)
  const [tasks, setTasks] = useState<Tache[]>([])
  const [dependencies, setDependencies] = useState<Dependance[]>([])
  const [milestones, setMilestones] = useState<Jalon[]>([])
  const [assignments, setAssignments] = useState<Affectation[]>([])
  const [resources, setResources] = useState<Ressource[]>([])
  const [conflicts, setConflicts] = useState<Set<string>>(new Set())
  const [cpm, setCpm] = useState<CPMResult | null>(null)
  const [zoom, setZoom] = useState('Week')
  const [toast, setToast] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<Tache | null>(null)
  const [editingTask, setEditingTask] = useState<Tache | null>(null)
  const [showTaskForm, setShowTaskForm] = useState(false)
  const [dependencySource, setDependencySource] = useState('')
  const [dependencyTarget, setDependencyTarget] = useState('')

  const load = useCallback(async () => {
    const [taskResponse, cpmResponse, milestoneResponse, resourceResponse] = await Promise.all([
      client.get<Tache[]>(`/projects/${projectId}/tasks`),
      client.get<CPMResult>(`/projects/${projectId}/critical-path`),
      client.get<Jalon[]>(`/projects/${projectId}/milestones`),
      client.get<Ressource[]>('/resources'),
    ])
    const taskData = taskResponse.data
    const dependencyData = (await Promise.all(taskData.map((task) => client.get<Dependance[]>(`/tasks/${task.id}/dependencies`)))).flatMap((response) => response.data)
    const assignmentData = (await Promise.all(taskData.map((task) => client.get<Affectation[]>(`/tasks/${task.id}/assignments`)))).flatMap((response) => response.data)
    const resourceIds = [...new Set(assignmentData.map((item) => item.ressource_id))]
    const start = taskData.length > 0 ? taskData.reduce((min, item) => item.date_debut_prevue < min ? item.date_debut_prevue : min, taskData[0].date_debut_prevue) : undefined
    const end = taskData.length > 0 ? taskData.reduce((max, item) => item.date_fin_prevue > max ? item.date_fin_prevue : max, taskData[0].date_fin_prevue) : undefined
    const conflictResponses = start && end ? await Promise.all(resourceIds.map((resourceId) => client.get<Conflit[]>(`/resources/${resourceId}/conflicts`, { params: { start, end } }))) : []
    setTasks(taskData)
    setCpm(cpmResponse.data)
    setMilestones(milestoneResponse.data)
    setDependencies([...new Map(dependencyData.map((item) => [item.id, item])).values()])
    setAssignments(assignmentData)
    setResources(resourceResponse.data)
    setConflicts(new Set(conflictResponses.flatMap((response) => response.data).filter((item) => item.jours_impactes > 0).map((item) => item.tache_id)))
    onProjectReload?.()
  }, [onProjectReload, projectId])

  useEffect(() => {
    async function initialize() {
      try {
        await load()
      } catch {
        setToast('Impossible de charger le planning.')
      }
    }
    void initialize()
  }, [load])

  const chartTasks = useMemo<ChartTask[]>(() => {
    const mapped = tasks.map((task) => {
      const critical = cpm?.tasks[task.id]?.est_critique ?? task.est_critique
      const classes = [critical ? 'gantt-critical' : 'gantt-normal']
      if (conflicts.has(task.id)) classes.push('gantt-conflict')
      return {
        id: task.id,
        name: task.nom,
        start: cpm?.tasks[task.id]?.es ?? task.date_debut_prevue,
        end: cpm?.tasks[task.id]?.ef ?? task.date_fin_prevue,
        progress: task.avancement,
        dependencies: dependencies.filter((item) => item.tache_aval_id === task.id).map((item) => item.tache_amont_id).join(','),
        custom_class: classes.join(' '),
      }
    })
    return [...mapped, ...milestones.map((milestone) => ({
      id: `milestone-${milestone.id}`,
      name: `◆ ${milestone.nom}`,
      start: milestone.date,
      end: milestone.date,
      progress: 100,
      custom_class: 'gantt-milestone',
    }))]
  }, [conflicts, cpm, dependencies, milestones, tasks])

  const taskDetails = useCallback((task: ChartTask) => {
    const source = tasks.find((item) => item.id === task.id)
    if (!source) return ''
    const taskResources = assignments.filter((item) => item.tache_id === source.id).map((item) => resources.find((resource) => resource.id === item.ressource_id)?.nom ?? 'Ressource')
    return `<strong>${source.nom}</strong><br>Durée: ${source.duree} jours<br>Marge: ${cpm?.tasks[source.id]?.marge ?? source.marge} jours<br>Ressources: ${taskResources.join(', ') || 'Aucune'}<br><button class="gantt-edit-task" data-task-id="${source.id}">Modifier</button>`
  }, [assignments, cpm, resources, tasks])

  useEffect(() => {
    if (!wrapperRef.current || chartTasks.length === 0) return
    const wrapper = wrapperRef.current
    wrapper.replaceChildren()
    ganttRef.current?.hide_popup()
    ganttRef.current = new Gantt(wrapper, chartTasks, {
      view_mode: zoom,
      view_modes: ['Day', 'Week', 'Month'],
      language: 'fr',
      popup_on: 'click',
      popup: ({ task }) => {
        setSelectedTask(tasks.find((item) => item.id === task.id) ?? null)
        return taskDetails(task)
      },
      on_date_change: (task, start, end) => {
        const previous = tasks.find((item) => item.id === task.id)
        void client.patch(`/tasks/${task.id}`, { date_debut_prevue: toDateInput(start), date_fin_prevue: toDateInput(end) }).then(() => load()).catch(() => {
          setToast('Le backend a refusé cette modification de dates.')
          if (previous) setTasks((current) => current.map((item) => item.id === previous.id ? previous : item))
        })
      },
      on_progress_change: (task, progress) => {
        void client.patch(`/tasks/${task.id}`, { avancement: progress }).then(() => load()).catch(() => setToast('Le backend a refusé cette progression.'))
      },
    })
    const editTask = (event: Event) => {
      const target = event.target
      if (!(target instanceof HTMLElement) || !target.matches('.gantt-edit-task')) return
      const task = tasks.find((item) => item.id === target.dataset.taskId)
      if (task) {
        setSelectedTask(task)
        setEditingTask(task)
        setShowTaskForm(true)
        ganttRef.current?.hide_popup()
      }
    }
    wrapper.addEventListener('click', editTask)
    return () => {
      wrapper.removeEventListener('click', editTask)
      ganttRef.current?.hide_popup()
      ganttRef.current = null
      wrapper.replaceChildren()
    }
  }, [chartTasks, load, tasks, taskDetails, zoom])

  async function saveTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = {
      nom: String(form.get('nom')),
      duree: Number(form.get('duree')),
      date_debut_prevue: String(form.get('date_debut_prevue')),
      date_fin_prevue: String(form.get('date_fin_prevue')),
      jalon_id: String(form.get('jalon_id') || '') || null,
      competences_requises: String(form.get('competences_requises') || '').split(',').map((item) => item.trim()).filter(Boolean),
      statut: editingTask?.statut ?? 'A_FAIRE',
    }
    try {
      if (editingTask) await client.patch(`/tasks/${editingTask.id}`, body)
      else await client.post(`/projects/${projectId}/tasks`, body)
      setShowTaskForm(false)
      setEditingTask(null)
      await load()
    } catch {
      setToast('Impossible d’enregistrer la tâche.')
    }
  }

  async function addDependency(event: FormEvent) {
    event.preventDefault()
    try {
      await client.post(`/tasks/${dependencySource}/dependencies`, { tache_amont_id: dependencySource, tache_aval_id: dependencyTarget, type: 'FIN_DEBUT' })
      setDependencySource('')
      setDependencyTarget('')
      await load()
    } catch {
      setToast('Dépendance refusée : elle créerait probablement un cycle.')
    }
  }

  async function removeDependency(dependency: Dependance) {
    try {
      await client.delete(`/dependencies/${dependency.id}`)
      await load()
    } catch {
      setToast('Impossible de supprimer cette dépendance.')
    }
  }

  return <div className="space-y-4">
    {toast && <div role="alert" className="flex items-center justify-between rounded-lg bg-orange-50 px-4 py-3 text-sm text-orange-800"><span>{toast}</span><button onClick={() => setToast(null)} aria-label="Fermer">×</button></div>}
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-2">{(['Day', 'Week', 'Month'] as const).map((mode) => <button key={mode} onClick={() => { setZoom(mode); ganttRef.current?.change_view_mode(mode) }} className={`rounded-lg px-3 py-2 text-sm ${zoom === mode ? 'bg-slate-950 text-white' : 'border border-slate-200 bg-white'}`}>{mode === 'Day' ? 'Jour' : mode === 'Week' ? 'Semaine' : 'Mois'}</button>)}</div>
      <button onClick={() => { setEditingTask(null); setShowTaskForm(true) }} className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-white">+ Nouvelle tâche</button>
    </div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4"><div ref={wrapperRef} className="min-w-[760px]" /></div>
      <aside className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="font-semibold text-slate-950">Chemin critique</h2><p className="mt-1 text-xs text-slate-500">{cpm?.critical_path.length ?? 0} tâches</p><ol className="mt-4 space-y-2 text-sm">{cpm?.critical_path.map((id, index) => <li className="flex gap-2" key={id}><span className="font-semibold text-red-500">{index + 1}</span><span>{tasks.find((task) => task.id === id)?.nom ?? id}</span></li>)}</ol></aside>
    </div>
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Modifier une tâche</h2><p className="mt-1 text-xs text-slate-500">Cliquez sur une tâche du graphique pour ouvrir ses détails.</p>{selectedTask && <div className="mt-4 flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm"><span>{selectedTask.nom}</span><button onClick={() => { setEditingTask(selectedTask); setShowTaskForm(true) }} className="font-medium text-cyan-700">Modifier</button></div>}</div>
      <div className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Dépendances</h2><form onSubmit={addDependency} className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto]"><select value={dependencySource} onChange={(event) => setDependencySource(event.target.value)} required className="rounded-lg border border-slate-200 px-2 py-2"><option value="">Amont</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.nom}</option>)}</select><select value={dependencyTarget} onChange={(event) => setDependencyTarget(event.target.value)} required className="rounded-lg border border-slate-200 px-2 py-2"><option value="">Aval</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.nom}</option>)}</select><button className="rounded-lg bg-slate-950 px-3 py-2 text-sm text-white">Ajouter</button></form><ul className="mt-4 space-y-2 text-xs text-slate-500">{dependencies.map((dependency) => <li className="flex justify-between gap-2" key={dependency.id}><span>{tasks.find((task) => task.id === dependency.tache_amont_id)?.nom} → {tasks.find((task) => task.id === dependency.tache_aval_id)?.nom}</span><button className="text-red-600" onClick={() => removeDependency(dependency)}>Supprimer</button></li>)}</ul></div>
    </div>
    {showTaskForm && <div className="fixed inset-0 z-20 grid place-items-center bg-slate-950/40 p-5"><form onSubmit={saveTask} className="w-full max-w-lg space-y-4 rounded-xl bg-white p-6 shadow-2xl"><div className="flex justify-between"><h2 className="text-xl font-bold">{editingTask ? 'Modifier la tâche' : 'Nouvelle tâche'}</h2><button type="button" onClick={() => setShowTaskForm(false)}>×</button></div><label className="block text-sm">Nom<input name="nom" defaultValue={editingTask?.nom} required className="mt-1 w-full rounded border p-2" /></label><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Durée<input name="duree" type="number" min="0" defaultValue={editingTask?.duree ?? 1} required className="mt-1 w-full rounded border p-2" /></label><label className="text-sm">Jalon<select name="jalon_id" defaultValue={editingTask?.jalon_id ?? ''} className="mt-1 w-full rounded border p-2"><option value="">Aucun</option>{milestones.map((milestone) => <option value={milestone.id} key={milestone.id}>{milestone.nom}</option>)}</select></label></div><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Début<input name="date_debut_prevue" type="date" defaultValue={editingTask?.date_debut_prevue} required className="mt-1 w-full rounded border p-2" /></label><label className="text-sm">Fin<input name="date_fin_prevue" type="date" defaultValue={editingTask?.date_fin_prevue} required className="mt-1 w-full rounded border p-2" /></label></div><label className="block text-sm">Compétences requises<input name="competences_requises" defaultValue={editingTask?.competences_requises.join(', ')} placeholder="python, sql" className="mt-1 w-full rounded border p-2" /></label><div className="flex justify-end gap-2"><button type="button" onClick={() => setShowTaskForm(false)} className="rounded-lg border px-4 py-2">Annuler</button><button className="rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-white">Enregistrer</button></div></form></div>}
  </div>
}
