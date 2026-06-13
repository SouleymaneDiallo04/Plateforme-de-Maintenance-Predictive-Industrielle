import { useState, useEffect, useCallback } from 'react'
import Sidebar      from './components/layout/Sidebar'
import ErrorBoundary from './components/ErrorBoundary'
import LoginPage   from './pages/LoginPage'
import Overview    from './pages/Overview'
import Monitoring  from './pages/Monitoring'
import IALab       from './pages/IALab'
import Prognostic  from './pages/Prognostic'
import Maintenance from './pages/Maintenance'
import Interventions from './pages/Interventions'
import Config      from './pages/Config'
import Audit       from './pages/Audit'
import { useSimulationWS } from './hooks/useWebSocket'
import { endpoints, auth } from './api/client'

export default function App() {
  const [user,   setUser]   = useState(auth.getUser())
  // Le technicien atterrit directement sur ses interventions
  const [page,   setPage]   = useState(
    auth.getRole() === 'technicien' ? 'interventions' : 'overview'
  )
  const [alerts, setAlerts] = useState([])
  const ws = useSimulationWS()

  // Vérifier expiration au montage
  useEffect(() => {
    if (auth.isExpired()) {
      auth.logout()
      setUser(null)
    }
  }, [])

  const handleLogin = (token, userInfo) => {
    auth.setToken(token)
    auth.setUser(userInfo)
    setUser(userInfo)
  }

  const handleLogout = () => {
    auth.logout()
    setUser(null)
  }

  const loadAlerts = useCallback(() => {
    endpoints.alerts()
      .then(r => setAlerts(r.data.alerts || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!user) return
    loadAlerts()
    const interval = setInterval(loadAlerts, 10000)
    return () => clearInterval(interval)
  }, [loadAlerts, user])

  useEffect(() => {
    if (ws.data?.new_alerts?.length > 0) {
      setAlerts(prev => [...ws.data.new_alerts, ...prev].slice(0, 100))
    }
  }, [ws.data?.new_alerts])

  // Pas connecté → page de login
  if (!user) {
    return <LoginPage onLogin={handleLogin} />
  }

  const pages = {
    overview     : <Overview    ws={ws} />,
    monitoring   : <Monitoring  ws={ws} />,
    ialab        : <IALab />,
    prognostic   : <Prognostic  ws={ws} />,
    maintenance  : <Maintenance ws={ws} alerts={alerts} />,
    interventions: <Interventions />,
    audit        : <Audit />,
    config       : <Config />,
  }

  return (
    <div style={{
      display  : 'flex',
      height   : '100vh',
      overflow : 'hidden',
      position : 'relative',
    }}>
      <div className="scan-grid" />
      <div className="scan-line" />

      <Sidebar
        active    = {page}
        onNav     = {setPage}
        wsStatus  = {ws.status}
        alerts    = {alerts}
        user      = {user}
        onLogout  = {handleLogout}
      />

      <main style={{
        flex     : 1,
        overflow : 'auto',
        padding  : 24,
        position : 'relative',
        zIndex   : 2,
      }}>
        <div key={page} style={{ animation: 'fadeInUp 0.3s ease forwards' }}>
          <ErrorBoundary resetKey={page}>
            {pages[page]}
          </ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
