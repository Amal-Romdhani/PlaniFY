import { createContext } from 'react'
import type { UserRole, Utilisateur } from '../types'

export interface AuthContextValue {
  user: Utilisateur | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function hasRole(user: Utilisateur | null, roles: UserRole[]) {
  return Boolean(user && roles.includes(user.role))
}
