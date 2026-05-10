import { useState, useEffect, useCallback } from 'react'
import Sidebar     from './components/layout/Sidebar'
import Overview    from './pages/Overview'
import Monitoring  from './pages/Monitoring'
import IALab       from './pages/IALab'
import Prognostic  from './pages/Prognostic'
import Maintenance from './pages/Maintenance'
import Config      from './pages/Config'
import { useSimulationWS } from './hooks/useWebSocket'
import { endpoints } from './api/client'

export default function App() {
  const [page,   setPage]   = useState('overview')
  const [alerts, setAlerts] = useState([])
  const ws = useSimulationWS()

  // Charger les alertes et les mettre à jour toutes les 10s
  const loadAlerts = useCallback(() => {
    endpoints.alerts()
      .then(r => setAlerts(r.data.alerts || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    loadAlerts()
    const interval = setInterval(loadAlerts, 10000)
    return () => clearInterval(interval)
  }, [loadAlerts])

  // Ajouter les nouvelles alertes du WebSocket
  useEffect(() => {
    if (ws.data?.new_alerts?.length > 0) {
      setAlerts(prev => [...ws.data.new_alerts, ...prev].slice(0, 100))
    }
  }, [ws.data?.new_alerts])

  const NAV_ITEMS = [
    { id: 'overview',    label: 'Vue Globale'   },
    { id: 'monitoring',  label: 'Monitoring'    },
    { id: 'ialab',       label: 'IA Lab'        },
    { id: 'prognostic',  label: 'Pronostic RUL' },
    { id: 'maintenance', label: 'Maintenance'   },
    { id: 'config',      label: 'Configuration' },
  ]

  const pages = {
    overview   : <Overview    ws={ws} />,
    monitoring : <Monitoring  ws={ws} />,
    ialab      : <IALab />,
    prognostic : <Prognostic  ws={ws} />,
    maintenance: <Maintenance ws={ws} alerts={alerts} />,
    config     : <Config />,
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
        active   = {page}
        onNav    = {setPage}
        wsStatus = {ws.status}
        alerts   = {alerts}
      />

      <main style={{
        flex     : 1,
        overflow : 'auto',
        padding  : 24,
        position : 'relative',
        zIndex   : 2,
      }}>
        <div key={page} style={{ animation: 'fadeInUp 0.3s ease forwards' }}>
          {pages[page]}
        </div>
      </main>
    </div>
  )
}