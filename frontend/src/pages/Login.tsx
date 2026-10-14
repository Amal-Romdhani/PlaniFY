import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function Login() {
  const { login, token } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  if (token) return <Navigate to="/" replace />
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    try { await login(email, password); navigate('/') } catch { setError('Email ou mot de passe invalide.') }
  }
  return <div className="grid min-h-screen place-items-center bg-slate-950 p-5"><form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl"><div className="mb-8"><div className="mb-5 grid size-11 place-items-center rounded-xl bg-cyan-400 text-xl font-bold">P</div><h1 className="text-3xl font-bold text-slate-950">Bienvenue</h1><p className="mt-2 text-sm text-slate-500">Connectez-vous à votre espace PlaniFY.</p></div>{error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<label className="mb-4 block text-sm font-medium text-slate-700">Email<input className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-cyan-400" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><label className="mb-6 block text-sm font-medium text-slate-700">Mot de passe<input className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 outline-none focus:border-cyan-400" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label><button className="w-full rounded-lg bg-slate-950 py-3 font-semibold text-white hover:bg-slate-800">Se connecter</button></form></div>
}
