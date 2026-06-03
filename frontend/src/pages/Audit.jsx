import { useState, useEffect, useCallback } from 'react'
import { endpoints } from '../api/client'
import { ShieldCheck, RefreshCw, Filter, Activity, AlertTriangle, RotateCcw } from 'lucide-react'

const TYPE_COLORS = {
  prediction : 'var(--cyan)',
  alert      : 'var(--red)',
  retrain    : 'var(--amber)',
}
const TYPE_ICONS = {
  prediction : Activity,
  alert      : AlertTriangle,
  retrain    : RotateCcw,
}

function StatCard({ label, value, color }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 140 }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, color: color || 'var(--cyan)', fontWeight: 700 }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function Audit() {
  const [entries, setEntries]   = useState([])
  const [stats,   setStats]     = useState(null)
  const [filter,  setFilter]    = useState('all')   // all | prediction | alert | retrain
  const [machine, setMachine]   = useState('')
  const [loading, setLoading]   = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      endpoints.auditRecent(200, machine || null),
      endpoints.auditStats(),
    ]).then(([r1, r2]) => {
      setEntries(r1.data.entries || [])
      setStats(r2.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [machine])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  const visible = filter === 'all' ? entries : entries.filter(e => e.type === filter)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* En-tête */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ShieldCheck size={22} color="var(--cyan)" />
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--cyan)', margin: 0 }}>
            AUDIT TRAIL — TRAÇABILITÉ IA
          </h1>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', margin: 0 }}>
            Journal ISO 13373 · Décisions IA horodatées · JSONL quotidien
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 'var(--radius)',
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--cyan)', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 11,
          }}
        >
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Actualiser
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <StatCard label="PRÉDICTIONS"    value={stats?.n_predictions}  color="var(--cyan)"  />
        <StatCard label="ALERTES"        value={stats?.n_alerts}       color="var(--red)"   />
        <StatCard label="RÉENTRAÎNEMENTS" value={stats?.n_retrains}    color="var(--amber)" />
        <StatCard label="EN MÉMOIRE"     value={stats?.total_entries}  color="var(--green)" />
      </div>

      {/* Filtres */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Filter size={12} color="var(--text-muted)" />
        {[
          { v: 'all',        label: 'Tout',            col: 'var(--text-muted)' },
          { v: 'prediction', label: 'Prédictions',     col: 'var(--cyan)'  },
          { v: 'alert',      label: 'Alertes',         col: 'var(--red)'   },
          { v: 'retrain',    label: 'Réentraînements', col: 'var(--amber)' },
        ].map(({ v, label, col }) => (
          <button
            key={v}
            onClick={() => setFilter(v)}
            style={{
              padding: '4px 12px', borderRadius: 20,
              border: `1px solid ${filter === v ? col : 'var(--border)'}`,
              background: filter === v ? `${col}20` : 'transparent',
              color: filter === v ? col : 'var(--text-muted)',
              fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer',
            }}
          >
            {label}
          </button>
        ))}
        <input
          value={machine}
          onChange={e => setMachine(e.target.value)}
          placeholder="Filtrer machine..."
          style={{
            marginLeft: 8, padding: '4px 10px', borderRadius: 'var(--radius)',
            border: '1px solid var(--border)', background: 'var(--bg-elevated)',
            color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 10,
            outline: 'none', width: 140,
          }}
        />
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                {['Type', 'Horodatage', 'Machine', 'Modèle / Alerte', 'Détail', 'Confiance'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: 'left',
                    fontFamily: 'var(--font-display)', fontSize: 9,
                    color: 'var(--text-muted)', letterSpacing: '0.1em',
                    whiteSpace: 'nowrap',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{
                    padding: '32px', textAlign: 'center',
                    fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)',
                  }}>
                    {loading ? 'Chargement...' : 'Aucune entrée — les décisions IA apparaîtront ici en temps réel'}
                  </td>
                </tr>
              ) : visible.slice(0, 150).map((e, i) => {
                const color = TYPE_COLORS[e.type] || 'var(--text-muted)'
                const Icon  = TYPE_ICONS[e.type] || Activity
                const ts    = e.timestamp ? new Date(e.timestamp).toLocaleString('fr-FR') : '—'
                const conf  = e.confidence != null ? `${(e.confidence * 100).toFixed(1)}%` : '—'
                const detail = e.prediction || e.alert_type || e.model_name || '—'
                const featTxt = e.features_summary && typeof e.features_summary === 'object'
                  ? Object.entries(e.features_summary).map(([k, v]) => `${k}=${v}`).join(' · ')
                  : ''
                const sub    = e.message || featTxt || e.dataset || ''
                return (
                  <tr key={i} style={{
                    borderBottom: '1px solid var(--border)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={ev => ev.currentTarget.style.background = 'var(--bg-elevated)'}
                  onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '8px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Icon size={12} color={color} />
                        <span style={{ fontFamily: 'var(--font-display)', fontSize: 9, color, letterSpacing: '0.08em' }}>
                          {e.type?.toUpperCase()}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {ts}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-primary)' }}>
                      {e.machine_id || '—'}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color }}>
                      {detail}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {sub}
                    </td>
                    <td style={{ padding: '8px 14px' }}>
                      {e.confidence != null && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 48, height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                            <div style={{ width: `${e.confidence * 100}%`, height: '100%', background: color }} />
                          </div>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color }}>{conf}</span>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {visible.length > 150 && (
          <div style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}>
            Affichage des 150 dernières entrées sur {visible.length}
          </div>
        )}
      </div>
    </div>
  )
}
