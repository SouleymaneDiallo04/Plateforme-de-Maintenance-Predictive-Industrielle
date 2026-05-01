import { useEffect, useState, useCallback } from 'react'
import {
  Activity, AlertTriangle, CheckCircle,
  Clock, Zap, TrendingDown, BarChart3
} from 'lucide-react'
import { endpoints } from '../api/client'
import HealthGauge from '../components/ui/HealthGauge'
import MetricCard  from '../components/ui/MetricCard'

const STATUS_CONFIG = {
  sain        : { color: 'var(--green)',  label: 'SAIN',         badge: 'badge-green'  },
  surveillance: { color: 'var(--amber)',  label: 'SURVEILLANCE', badge: 'badge-amber'  },
  alerte      : { color: 'var(--orange)', label: 'ALERTE',       badge: 'badge-orange' },
  critique    : { color: 'var(--red)',    label: 'CRITIQUE',     badge: 'badge-red'    },
}

function MachineCard({ machine, onClick, isActive }) {
  const cfg = STATUS_CONFIG[machine.status] || STATUS_CONFIG.sain

  return (
    <div
      className = "card"
      onClick   = {() => onClick(machine)}
      style     = {{
        cursor      : 'pointer',
        borderColor : isActive
          ? 'var(--cyan)'
          : machine.status === 'critique'
          ? 'var(--red)'
          : 'var(--border)',
        boxShadow   : isActive
          ? '0 0 20px var(--cyan-dim)'
          : machine.status === 'critique'
          ? '0 0 20px var(--red-dim)'
          : 'none',
        transform   : isActive ? 'scale(1.01)' : 'scale(1)',
        transition  : 'all 0.2s ease',
      }}
    >
      <div style={{
        display        : 'flex',
        justifyContent : 'space-between',
        alignItems     : 'center',
        marginBottom   : 14,
      }}>
        <div>
          <div style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 13,
            color         : isActive ? 'var(--cyan)' : 'var(--text)',
            letterSpacing : '0.05em',
          }}>
            {machine.machine_id}
          </div>
          <div style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
            marginTop  : 2,
          }}>
            {machine.dataset || 'N/A'}
          </div>
        </div>
        <span className={`badge ${cfg.badge}`}>
          <span style={{
            width        : 6, height: 6,
            borderRadius : '50%',
            background   : cfg.color,
            display      : 'inline-block',
          }} />
          {cfg.label}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <HealthGauge value={machine.health_index} size={88} />
        <div style={{ flex: 1 }}>
          <div style={{ marginBottom: 8 }}>
            <div className="metric-label">RUL estimée</div>
            <div style={{
              fontFamily : 'var(--font-display)',
              fontSize   : 18,
              fontWeight : 700,
              color      : (machine.rul ?? 999) < 20 ? 'var(--red)'
                         : (machine.rul ?? 999) < 40 ? 'var(--orange)'
                         : 'var(--cyan)',
            }}>
              {machine.rul != null ? Math.round(machine.rul) : '—'}
              <span style={{
                fontSize   : 10,
                color      : 'var(--text-muted)',
                fontFamily : 'var(--font-mono)',
                marginLeft : 4,
              }}>cycles</span>
            </div>
          </div>
          <div>
            <div className="metric-label">Tendance</div>
            <div style={{
              fontFamily : 'var(--font-mono)',
              fontSize   : 10,
              color      : (machine.trend?.slope ?? 0) < 0
                ? 'var(--red)' : 'var(--green)',
            }}>
              {machine.trend?.description || '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Barre santé */}
      <div style={{
        marginTop    : 12,
        height       : 3,
        background   : 'var(--border)',
        borderRadius : 2,
        overflow     : 'hidden',
      }}>
        <div style={{
          width        : `${machine.health_index}%`,
          height       : '100%',
          background   : `linear-gradient(90deg, ${cfg.color}88, ${cfg.color})`,
          borderRadius : 2,
          transition   : 'width 1s ease',
          boxShadow    : `0 0 6px ${cfg.color}`,
        }} />
      </div>

      {isActive && (
        <div style={{
          marginTop   : 8,
          fontFamily  : 'var(--font-mono)',
          fontSize    : 9,
          color       : 'var(--cyan)',
          letterSpacing: '0.1em',
          textAlign   : 'center',
        }}>
          ● EN COURS DE SURVEILLANCE
        </div>
      )}
    </div>
  )
}

export default function Overview({ ws }) {
  const [fleet,    setFleet]    = useState(null)
  const [kpis,     setKpis]     = useState(null)
  const [selected, setSelected] = useState(null)
  const [machineKpi, setMachineKpi] = useState(null)

  // Charger la flotte périodiquement
  useEffect(() => {
    const load = () => {
      endpoints.fleet()
        .then(r => setFleet(r.data))
        .catch(() => {})
      endpoints.fleetKpi()
        .then(r => setKpis(r.data))
        .catch(() => {})
    }
    load()
    const iv = setInterval(load, 5000)
    return () => clearInterval(iv)
  }, [])

  // KPI de la machine sélectionnée
  useEffect(() => {
    if (!selected) return
    endpoints.kpi(selected)
      .then(r => setMachineKpi(r.data))
      .catch(() => {})
  }, [selected])

  const handleMachineClick = (machine) => {
    setSelected(machine.machine_id)
    // Changer la machine dans le WebSocket
    ws.setMachine(machine.machine_id, machine.dataset || 'CWRU')
  }

  const machines = fleet?.machines || []

  // Données temps réel de la machine active (depuis WS)
  const liveData     = ws.data
  const isLiveMachine = liveData?.machine_id === selected

  // Métriques à afficher : temps réel si dispo, sinon statiques
  const currentHI  = isLiveMachine
    ? liveData.health_index
    : machines.find(m => m.machine_id === selected)?.health_index ?? null
  const currentRUL = isLiveMachine
    ? liveData.rul_pred
    : machines.find(m => m.machine_id === selected)?.rul ?? null
  const currentTrend = isLiveMachine
    ? liveData.trend
    : machines.find(m => m.machine_id === selected)?.trend ?? null
  const anomalyScore = isLiveMachine ? liveData.anomaly_score : null

  const hiColor = currentHI == null ? 'var(--cyan)'
    : currentHI >= 70 ? 'var(--green)'
    : currentHI >= 40 ? 'var(--amber)'
    : currentHI >= 20 ? 'var(--orange)'
    :                   'var(--red)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header */}
      <div style={{
        display        : 'flex',
        justifyContent : 'space-between',
        alignItems     : 'flex-end',
      }}>
        <div>
          <h1 style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 22,
            color         : 'var(--text)',
            letterSpacing : '0.05em',
          }}>VUE GLOBALE</h1>
          <p style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 11,
            color      : 'var(--text-muted)',
            marginTop  : 4,
          }}>
            {fleet?.n_machines || 0} MACHINES ·{' '}
            <span style={{
              color: ws.status === 'connected' ? 'var(--green)' : 'var(--red)'
            }}>
              {ws.status === 'connected' ? '● LIVE' : '○ OFFLINE'}
            </span>
            {selected && (
              <span style={{ color: 'var(--cyan)', marginLeft: 8 }}>
                · Surveillance : {selected}
              </span>
            )}
          </p>
        </div>
        <div style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 11,
          color      : 'var(--text-muted)',
        }}>
          {new Date().toLocaleTimeString('fr-FR')}
        </div>
      </div>

      {/* ── Panneau temps réel machine sélectionnée ── */}
      {selected && (
        <div style={{
          background   : 'var(--bg-card)',
          border       : '1px solid var(--cyan)',
          borderRadius : 'var(--radius-lg)',
          padding      : '16px 20px',
          boxShadow    : '0 0 30px var(--cyan-dim)',
        }}>
          <div style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 11,
            color         : 'var(--cyan)',
            letterSpacing : '0.1em',
            marginBottom  : 14,
          }}>
            ● SURVEILLANCE TEMPS RÉEL — {selected}
          </div>

          <div style={{
            display             : 'grid',
            gridTemplateColumns : '160px 1fr 1fr 1fr 1fr 1fr',
            gap                 : 16,
            alignItems          : 'center',
          }}>
            {/* Grosse jauge */}
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <HealthGauge
                value = {currentHI ?? 0}
                size  = {140}
                label = {currentTrend?.direction || 'STABLE'}
              />
            </div>

            {/* Métriques */}
            <div>
              <div className="metric-label">Health Index</div>
              <div style={{
                fontFamily : 'var(--font-display)',
                fontSize   : 28,
                fontWeight : 700,
                color      : hiColor,
                filter     : `drop-shadow(0 0 8px ${hiColor})`,
              }}>
                {currentHI != null ? `${currentHI.toFixed(1)}%` : '—'}
              </div>
            </div>

            {/* RUL Prédite */}
<div>
  <div className="metric-label">RUL Prédite</div>
  <div style={{
    fontFamily : 'var(--font-display)',
    fontSize   : 28,
    fontWeight : 700,
    color      : (() => {
      // Utiliser rul_pred OU rul_true OU null
      const val = liveData?.rul_pred ?? liveData?.rul_true
      if (val == null) return 'var(--text-dim)'
      return val < 20 ? 'var(--red)'
           : val < 40 ? 'var(--orange)'
           : 'var(--cyan)'
    })(),
  }}>
    {(() => {
      const val = liveData?.rul_pred ?? liveData?.rul_true
      if (val == null || !isFinite(val)) return '—'
      return Math.round(val)
    })()}
    <span style={{
      fontSize:12, color:'var(--text-muted)',
      fontFamily:'var(--font-mono)', marginLeft:4,
    }}>cyc</span>
  </div>
</div>

            <div>
              <div className="metric-label">Score Anomalie</div>
              <div style={{
                fontFamily : 'var(--font-display)',
                fontSize   : 28,
                fontWeight : 700,
                color      : (anomalyScore ?? 0) > 60 ? 'var(--red)'
                           : (anomalyScore ?? 0) > 30 ? 'var(--amber)'
                           : 'var(--green)',
              }}>
                {anomalyScore != null ? `${anomalyScore.toFixed(1)}%` : '—'}
              </div>
            </div>

            <div>
              <div className="metric-label">Défaut détecté</div>
              <div style={{
                fontFamily    : 'var(--font-display)',
                fontSize      : 13,
                fontWeight    : 700,
                color         : 'var(--text)',
                letterSpacing : '0.03em',
                marginTop     : 4,
              }}>
                {liveData?.prediction || '—'}
              </div>
              {liveData?.confidence != null && (
                <div style={{
                  fontFamily : 'var(--font-mono)',
                  fontSize   : 10,
                  color      : 'var(--text-muted)',
                  marginTop  : 2,
                }}>
                  confiance {(liveData.confidence * 100).toFixed(1)}%
                </div>
              )}
            </div>

            <div>
              <div className="metric-label">Tendance</div>
              <div style={{
                fontFamily : 'var(--font-mono)',
                fontSize   : 11,
                color      : (currentTrend?.slope ?? 0) < 0
                  ? 'var(--red)' : 'var(--green)',
                marginTop  : 4,
              }}>
                {currentTrend?.description || '—'}
              </div>
              {machineKpi?.kpis && (
                <div style={{ marginTop: 8 }}>
                  <div className="metric-label">MTBF</div>
                  <div style={{
                    fontFamily : 'var(--font-display)',
                    fontSize   : 14,
                    color      : 'var(--amber)',
                  }}>
                    {machineKpi.kpis.MTBF?.toFixed(1)}h
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* KPIs flotte globaux */}
      <div style={{
        display             : 'grid',
        gridTemplateColumns : 'repeat(5, 1fr)',
        gap                 : 12,
      }}>
        <MetricCard label="Saines"       value={fleet?.n_healthy}        color="var(--green)"  icon={CheckCircle} />
        <MetricCard label="Surveillance" value={fleet?.n_surveillance}   color="var(--amber)"  icon={Activity}    />
        <MetricCard label="Alertes"      value={fleet?.n_alert}          color="var(--orange)" icon={AlertTriangle} />
        <MetricCard label="Critiques"    value={fleet?.n_critical}       color="var(--red)"    icon={Zap} glow={fleet?.n_critical > 0} />
        <MetricCard label="HI Moyen"     value={fleet?.avg_health_index?.toFixed(1)} unit="%" color="var(--cyan)" icon={BarChart3} glow />
      </div>

      {/* KPIs industriels flotte */}
      {kpis?.fleet_averages && (
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(3, 1fr)',
          gap                 : 12,
        }}>
          <MetricCard
            label = "MTBF Moyen"
            value = {kpis.fleet_averages.MTBF?.toFixed(1)}
            unit  = "h"
            color = "var(--amber)"
            icon  = {Clock}
          />
          <MetricCard
            label = "OEE Moyen"
            value = {kpis.fleet_averages.OEE?.toFixed(1)}
            unit  = "%"
            color = "var(--cyan)"
            icon  = {BarChart3}
          />
          <MetricCard
            label = "Disponibilité"
            value = {kpis.fleet_averages.availability?.toFixed(1)}
            unit  = "%"
            color = "var(--green)"
            icon  = {CheckCircle}
          />
        </div>
      )}

      {/* Grille machines */}
      <div>
        <h2 style={{
          fontFamily    : 'var(--font-display)',
          fontSize      : 11,
          color         : 'var(--text-muted)',
          letterSpacing : '0.1em',
          marginBottom  : 14,
        }}>
          FLOTTE — CLIQUER POUR SURVEILLER
        </h2>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(auto-fill, minmax(280px, 1fr))',
          gap                 : 14,
        }}>
          {machines.map(m => (
            <MachineCard
              key      = {m.machine_id}
              machine  = {m}
              isActive = {selected === m.machine_id}
              onClick  = {handleMachineClick}
            />
          ))}
        </div>
      </div>
    </div>
  )
}