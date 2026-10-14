import { Navigate, Outlet } from 'react-router-dom'
import { hasRole, useAuth } from './useAuth'
import type { UserRole } from '../types'

export default function ProtectedRoute({ roles }: { roles?: UserRole[] }) {
  const { user, token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  if (!user) return <div className="grid min-h-screen place-items-center text-slate-500">Chargement...</div>
  if (roles && !hasRole(user, roles)) return <Navigate to="/" replace />
  return <Outlet />
}
