import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Recommendations from './Recommendations'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../api/client', () => ({ default: { get, post } }))
vi.mock('../components/PageHeader', () => ({ default: ({ title }: { title: string }) => <h1>{title}</h1> }))

const action = {
  id: 'action-1',
  projet_id: 'project-1',
  tache_id: 'task-1',
  type: 'DECALAGE',
  statut: 'EN_ATTENTE',
  justification: 'Décalage absorbé par la marge.',
  payload: { params: { delay_days: 1 } },
  simulation_result: {
    task_id: 'task-1',
    ancienne_date_fin_tache: '2026-04-07',
    nouvelle_date_fin_tache: '2026-04-08',
    ancienne_date_fin_projet: '2026-04-30',
    nouvelle_date_fin_projet: '2026-04-30',
    retard_projet_jours: 0,
    ancienne_marge: 2,
    nouvelle_marge: 1,
    taches_nouvellement_critiques: [],
    nouveaux_conflits: [],
    problemes: [],
  },
  validation_status: 'VALIDE',
  date_creation: '2026-04-01T10:00:00Z',
  date_decision: null,
  decideur_id: null,
  decideur_nom: null,
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><Recommendations /></QueryClientProvider>)
}

describe('Recommendations', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockImplementation((url: string, config?: { params?: { statut?: string } }) => {
      if (url === '/projects') return Promise.resolve({ data: [] })
      if (config?.params?.statut === 'EN_ATTENTE') return Promise.resolve({ data: [action] })
      return Promise.resolve({ data: [] })
    })
    post.mockResolvedValue({ data: action })
  })

  it('affiche les recommandations et leur comparaison', async () => {
    renderPage()
    expect(await screen.findByText('Décalage absorbé par la marge.')).toBeInTheDocument()
    expect(screen.getByText('Aucun retard')).toBeInTheDocument()
    expect(screen.getByText('VALIDE')).toBeInTheDocument()
  })

  it('valide après confirmation et peut rejeter une action', async () => {
    renderPage()
    await screen.findByText('Décalage absorbé par la marge.')
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/agent/actions/action-1/accept'))

    fireEvent.click(screen.getByRole('button', { name: 'Rejeter' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/agent/actions/action-1/reject'))
  })

  it('affiche le message du conflit de planning', async () => {
    post.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'planning modifié, relancer la simulation' } } })
    renderPage()
    await screen.findByText('Décalage absorbé par la marge.')
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('planning modifié, relancer la simulation')).toBeInTheDocument()
  })
})
