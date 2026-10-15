import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import client from '../api/client'
import { useAuth } from '../auth/useAuth'
import type { ActionAgent } from '../types'

const links = [
  { to: '/', label: 'Tableau de bord', roles: ['CHEF_PROJET', 'ADMIN', 'MEMBRE'] },
  { to: '/projects', label: 'Projets', roles: ['CHEF_PROJET', 'ADMIN'] },
  { to: '/resources', label: 'Ressources', roles: ['CHEF_PROJET', 'ADMIN'] },
  { to: '/my-unavailabilities', label: 'Mes indisponibilités', roles: ['MEMBRE'] },
  { to: '/recommendations', label: 'Recommandations', roles: ['CHEF_PROJET', 'ADMIN'] },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const pendingActions = useQuery({
    queryKey: ['agent-actions', 'pending', 'navigation'],
    queryFn: () => client.get<ActionAgent[]>('/agent/actions', { params: { statut: 'EN_ATTENTE' } }).then((response) => response.data),
    enabled: Boolean(user && ['CHEF_PROJET', 'ADMIN'].includes(user.role)),
    refetchInterval: 30000,
    retry: false,
  })
  const pendingCount = pendingActions.data?.length ?? 0
  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 shrink-0 bg-slate-950 p-6 text-white md:block">
        <div className="mb-10 flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-cyan-400 font-bold text-slate-950">P</span><span className="text-xl font-semibold">PlaniFY</span></div>
        <nav className="space-y-2">
          {links.filter((link) => user && link.roles.includes(user.role)).map((link) => (
            <NavLink key={link.to} to={link.to} className={({ isActive }) => `flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition ${isActive ? 'bg-cyan-400 font-semibold text-slate-950' : 'text-slate-300 hover:bg-slate-800'}`}>
              {({ isActive }) => <><span>{link.label}</span>
                {link.to === '/recommendations' && pendingCount > 0 && <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${isActive ? 'bg-slate-950 text-white' : 'bg-amber-400 text-slate-950'}`}>{pendingCount}</span>}
              </>}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 md:px-8">
          <div><p className="text-sm font-semibold text-slate-900">Espace de pilotage</p><p className="text-xs text-slate-500">Planification déterministe</p></div>
          <div className="flex items-center gap-4"><div className="text-right"><p className="text-sm font-medium">{user?.nom}</p><p className="text-xs text-slate-500">{user?.role}</p></div><button onClick={logout} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">Déconnexion</button></div>
        </header>
        <div className="p-5 md:p-8"><Outlet /></div>
      </main>
    </div>
  )
}
