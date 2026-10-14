import { useEffect, useMemo, useState } from 'react'
import client from '../api/client'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState(localStorage.getItem('planify_token'))
  const [user, setUser] = useState<import('../types').Utilisateur | null>(null)

  useEffect(() => {
    if (!token) return
    client.get<import('../types').Utilisateur>('/auth/me').then((response) => setUser(response.data)).catch(() => {
      localStorage.removeItem('planify_token')
      setToken(null)
    })
  }, [token])

  const value = useMemo(() => ({
    user,
    token,
    login: async (email: string, password: string) => {
      const body = new URLSearchParams({ username: email, password })
      const response = await client.post<{ access_token: string }>('/auth/login', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('planify_token', response.data.access_token)
      setToken(response.data.access_token)
    },
    logout: () => {
      localStorage.removeItem('planify_token')
      setToken(null)
      setUser(null)
    },
  }), [token, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
