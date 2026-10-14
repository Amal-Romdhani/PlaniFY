import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import ProjectGantt from './pages/ProjectGantt'
import Projects from './pages/Projects'
import Recommendations from './pages/Recommendations'
import Resources from './pages/Resources'
import Unavailabilities from './pages/Unavailabilities'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />
                <Route element={<ProtectedRoute roles={['CHEF_PROJET', 'ADMIN']} />}>
                  <Route path="/projects" element={<Projects />} />
                  <Route path="/projects/:id/gantt" element={<ProjectGantt />} />
                  <Route path="/resources" element={<Resources />} />
                  <Route path="/recommendations" element={<Recommendations />} />
                </Route>
                <Route element={<ProtectedRoute roles={['MEMBRE']} />}>
                  <Route path="/my-unavailabilities" element={<Unavailabilities />} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
