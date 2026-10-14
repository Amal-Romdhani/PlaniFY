import { useContext } from 'react'
import { AuthContext, hasRole } from './context'

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider')
  return context
}

export { hasRole }
