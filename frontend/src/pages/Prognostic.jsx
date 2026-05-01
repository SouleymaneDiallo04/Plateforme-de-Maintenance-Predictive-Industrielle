import { useState, useEffect, useRef } from 'react'
import {
  AreaChart, Area, LineChart, Line, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { Zap } from 'lucide-react'
import HealthGauge from '../components/ui/HealthGauge'
import { endpoints } from '../api/client'

const Tooltip2 = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background:'var(--bg-elevated)', border:'1px solid var(--border)',
      borderRadius:'var(--radius)', padding:'8px 12px',
      fontFamily:'var(--font-mono)', fontSize:11,
    }}>
      <div style={{ color:'var(--text-muted)', marginBottom:4 }}>Cycle {label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || p.stroke }}>
          {p.name} : {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
        </div>
      ))}
    </div>
  )
}

function RULCountdown({ rul }) {
  const valid    = rul != null && isFinite(rul) && rul >= 0
  const isUrgent = valid && rul < 15
  const isWarn   = valid && rul < 40
  const color    = !valid     ? 'var(--text-dim)'
                 : isUrgent   ? 'var(--red)'
                 : isWarn     ? 'var(--orange)'
                 :               'var(--cyan)'

  return (
    <div style={{ textAlign:'center', padding:'16px 0' }}>
      <div style={{
        fontFamily:'var(--font-mono)', fontSize:9,
        color:'var(--text-muted)', letterSpacing:'0.2em', marginBottom:10,
      }}>
        REMAINING USEFUL LIFE
      </div>

      <div style={{
        fontFamily:'var(--font-display)', fontSize:80,
        fontWeight:900, color, lineHeight:1,
        letterSpacing:'-3px',
        filter: valid ? `drop-shadow(0 0 24px ${color})` : 'none',
        animation: isUrgent ? 'glow-pulse 1s infinite' : 'none',
        transition:'color 0.8s ease',
        minHeight:90,
        display:'flex', alignItems:'center', justifyContent:'center',
      }}>
        {valid ? Math.round(rul) : '—'}
      </div>

      <div style={{
        fontFamily:'var(--font-mono)', fontSize:14,
        color: valid ? 'var(--text-muted)' : 'var(--text-dim)',
        marginTop:8,
      }}>
        {valid ? 'cycles restants' : 'sélectionnez Turbine pour la RUL'}
      </div>

      {valid && (
        <div style={{
          fontFamily:'var(--font-mono)', fontSize:11,
          color:'var(--text-muted)', marginTop:10,
          background:'var(--bg-elevated)', display:'inline-block',
          padding:'4px 16px', borderRadius:20,
          border:'1px solid var(--border)',
        }}>
          ± 8 cycles · IC 95%
        </div>
      )}

      {isUrgent && (
        <div style={{
          marginTop:16, padding:'8px 16px',
          background:'var(--red-dim)', border:'1px solid var(--red)',
          borderRadius:'var(--radius)', display:'inline-flex',
          alignItems:'center', gap:8,
          fontFamily:'var(--font-mono)', fontSize:11, color:'var(--red)',
          animation:'pulse-red 2s infinite',
        }}>
          <Zap size={12}/> INTERVENTION IMMÉDIATE
        </div>
      )}
    </div>
  )
}

export default function Prognostic({ ws }) {
  const [machines, setMachines] = useState([])
  const [selected, setSelected] = useState('')
  const [histData, setHistData] = useState([])
  const pollRef = useRef(null)

  // Charger la flotte
  useEffect(() => {
    endpoints.fleet().then(r => {
      const list = r.data.machines || []
      setMachines(list)
      // Sélectionner CMAPSS par défaut pour avoir la RUL
      const cmapss = list.find(m => m.dataset === 'CMAPSS')
      const first  = cmapss || list[0]
      if (first && !selected) {
        setSelected(first.machine_id)
        ws.setMachine(first.machine_id, first.dataset || 'CMAPSS')
      }
    }).catch(() => {})
  }, [])

  // Charger l'historique backend périodiquement
  useEffect(() => {
    if (!selected) return
    const load = () => {
      endpoints.machineHistory(selected).then(r => {
        const h = r.data
        if (!h?.cycles?.length) return
        const rows = h.cycles.map((c, i) => ({
          cycle   : c,
          hi      : h.health_index?.[i] ?? null,
          rul     : h.rul?.[i]          ?? null,
          rul_true: h.rul?.[i]          ?? null,
          anomaly : h.anomaly?.[i]      ?? null,
        })).filter(d => d.hi != null && isFinite(d.hi))
        if (rows.length > 0) setHistData(rows)
      }).catch(() => {})
    }
    load()
    pollRef.current = setInterval(load, 6000)
    return () => clearInterval(pollRef.current)
  }, [selected])

  const handleSelect = (e) => {
    const mid = e.target.value
    setSelected(mid)
    setHistData([])
    ws.reset()
    const m = machines.find(x => x.machine_id === mid)
    ws.setMachine(mid, m?.dataset || 'CWRU')
  }

  // Données temps réel
  const isLive = ws.data?.machine_id === selected && ws.status === 'connected'

  // Extraire RUL depuis le WS — plusieurs sources possibles
  const getRulFromWsData = (d) => {
    if (!d) return null
    if (d.rul_pred != null && isFinite(d.rul_pred)) return d.rul_pred
    if (d.rul_true != null && isFinite(d.rul_true)) return d.rul_true
    return null
  }

  const liveHI    = isLive ? ws.data?.health_index : null
  const liveRUL   = isLive ? getRulFromWsData(ws.data) : null
  const liveTrend = isLive ? ws.data?.trend : null

  // Historique WS
  const wsRows = ws.history
    .filter(h => h.health_index != null && isFinite(h.health_index))
    .map(h => ({
      cycle   : h.cycle,
      hi      : h.health_index,
      rul     : h.rul_pred ?? h.rul_true ?? null,
      rul_true: h.rul_true ?? null,
    }))

  // Source principale : WS si dispo, sinon backend
  const chartData = (isLive && wsRows.length >= 5) ? wsRows : histData

  // Valeurs courantes
  const currentHI  = liveHI  ?? chartData.slice(-1)[0]?.hi  ?? null
  const currentRUL = liveRUL ?? chartData.slice(-1)[0]?.rul ?? null

  const hiColor = !currentHI ? 'var(--cyan)'
    : currentHI >= 70 ? 'var(--green)'
    : currentHI >= 40 ? 'var(--amber)'
    : currentHI >= 20 ? 'var(--orange)'
    :                   'var(--red)'

  const hasHI  = chartData.length >= 2
  const hasRUL = chartData.some(d =>
    d.rul != null && isFinite(d.rul) && d.rul > 0
  )

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>

      {/* Header + sélecteur */}
      <div style={{
        display:'flex', justifyContent:'space-between', alignItems:'flex-end',
      }}>
        <div>
          <h1 style={{
            fontFamily:'var(--font-display)', fontSize:22,
            color:'var(--text)', letterSpacing:'0.05em',
          }}>PRONOSTIC & RUL</h1>
          <p style={{
            fontFamily:'var(--font-mono)', fontSize:11,
            color:'var(--text-muted)', marginTop:4,
          }}>
            {isLive ? '● TEMPS RÉEL' : '◌ HISTORIQUE'} · {chartData.length} pts
            {currentRUL != null && (
              <span style={{ color: 'var(--cyan)', marginLeft:8 }}>
                · RUL = {Math.round(currentRUL)} cycles
              </span>
            )}
          </p>
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
          <label style={{
            fontFamily:'var(--font-mono)', fontSize:9,
            color:'var(--text-muted)', letterSpacing:'0.1em',
          }}>
            MACHINE SURVEILLÉE
          </label>
          <select
            value    = {selected}
            onChange = {handleSelect}
            style    = {{
              background   : 'var(--bg-card)',
              border       : '1px solid var(--border)',
              borderRadius : 'var(--radius)',
              color        : 'var(--text)',
              padding      : '8px 14px',
              fontFamily   : 'var(--font-mono)',
              fontSize     : 12,
              cursor       : 'pointer',
              outline      : 'none',
              minWidth     : 240,
            }}
          >
            {machines.length === 0 && (
              <option value="">Chargement de la flotte...</option>
            )}
            {machines.map(m => (
              <option key={m.machine_id} value={m.machine_id}>
                {m.machine_id}
                {m.dataset ? ` [${m.dataset}]` : ''}
                {` — ${(m.status || 'sain').toUpperCase()}`}
                {` (${Math.round(m.health_index ?? 0)}%)`}
              </option>
            ))}
          </select>
          <div style={{
            fontFamily:'var(--font-mono)', fontSize:9,
            color:'var(--text-dim)',
          }}>
            💡 Sélectionnez une Turbine [CMAPSS] pour voir la RUL
          </div>
        </div>
      </div>

      {/* Jauge + RUL countdown */}
      <div style={{
        display:'grid', gridTemplateColumns:'1fr 1fr', gap:16,
      }}>
        <div className="card" style={{ textAlign:'center' }}>
          <div style={{
            fontFamily:'var(--font-display)', fontSize:10,
            color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:14,
          }}>HEALTH INDEX</div>
          <div style={{ display:'flex', justifyContent:'center' }}>
            <HealthGauge
              value = {currentHI ?? 0}
              size  = {190}
              label = {liveTrend?.direction ?? (histData.length > 0 ? 'historique' : '—')}
            />
          </div>
          {(liveTrend || histData.length > 0) && (
            <div style={{
              marginTop:14, padding:'8px 12px',
              background:'var(--bg-elevated)', borderRadius:'var(--radius)',
              fontFamily:'var(--font-mono)', fontSize:11,
              color: (liveTrend?.slope ?? -1) < 0 ? 'var(--red)' : 'var(--green)',
            }}>
              {liveTrend?.description ?? '—'}
            </div>
          )}
        </div>

        <div className="card">
          <RULCountdown rul={currentRUL} />
        </div>
      </div>

      {/* Courbe Health Index */}
      <div className="card">
        <div style={{
          display:'flex', justifyContent:'space-between',
          alignItems:'center', marginBottom:14,
        }}>
          <h3 style={{
            fontFamily:'var(--font-display)', fontSize:10,
            color:'var(--text-muted)', letterSpacing:'0.1em',
          }}>TRAJECTOIRE DE DÉGRADATION — HEALTH INDEX</h3>
          {isLive && (
            <span className="badge badge-cyan">
              <span style={{
                width:5, height:5, borderRadius:'50%',
                background:'var(--cyan)', display:'inline-block',
                animation:'glow-pulse 1s infinite',
              }}/>
              LIVE
            </span>
          )}
        </div>

        {hasHI ? (
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData}
              margin={{ top:8, right:24, bottom:8, left:-10 }}>
              <defs>
                <linearGradient id="hi-prog" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={hiColor} stopOpacity={0.4}/>
                  <stop offset="100%" stopColor={hiColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" opacity={0.5}/>
              <XAxis dataKey="cycle"
                tick={{ fontSize:9, fontFamily:'var(--font-mono)', fill:'var(--text-muted)' }}
                tickLine={false}
              />
              <YAxis domain={[0, 105]}
                tick={{ fontSize:9, fontFamily:'var(--font-mono)', fill:'var(--text-muted)' }}
                tickLine={false}
              />
              <Tooltip content={<Tooltip2/>}/>
              <ReferenceLine y={70} stroke="var(--green)" strokeDasharray="5 3" opacity={0.5}
                label={{ value:'70%', position:'insideTopRight',
                  style:{ fontSize:8, fill:'var(--green)' } }}
              />
              <ReferenceLine y={40} stroke="var(--amber)" strokeDasharray="5 3" opacity={0.4}
                label={{ value:'40%', position:'insideTopRight',
                  style:{ fontSize:8, fill:'var(--amber)' } }}
              />
              <ReferenceLine y={20} stroke="var(--red)" strokeDasharray="5 3" opacity={0.4}
                label={{ value:'20%', position:'insideTopRight',
                  style:{ fontSize:8, fill:'var(--red)' } }}
              />
              <Area type="monotone" dataKey="hi" name="Health Index (%)"
                stroke={hiColor} fill="url(#hi-prog)"
                strokeWidth={2.5} dot={false} isAnimationActive={false}
                connectNulls
                style={{ filter:`drop-shadow(0 0 5px ${hiColor})` }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div style={{
            height:200, display:'flex', flexDirection:'column',
            alignItems:'center', justifyContent:'center',
            color:'var(--text-dim)', fontFamily:'var(--font-mono)',
            fontSize:12, gap:8,
          }}>
            <div>Démarrez la simulation</div>
            <div style={{ fontSize:10 }}>La courbe s'affiche après quelques cycles</div>
          </div>
        )}
      </div>

      {/* Courbe RUL */}
      <div className="card">
        <h3 style={{
          fontFamily:'var(--font-display)', fontSize:10,
          color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:14,
        }}>
          RUL PRÉDITE VS RÉELLE
          {!hasRUL && (
            <span style={{
              fontFamily:'var(--font-mono)', fontSize:9,
              color:'var(--text-dim)', marginLeft:12, fontWeight:400,
            }}>
              — disponible uniquement sur dataset CMAPSS (Turbine_01, Turbine_02)
            </span>
          )}
        </h3>

        {hasRUL ? (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}
              margin={{ top:8, right:24, bottom:8, left:-10 }}>
              <CartesianGrid stroke="var(--border)" opacity={0.5}/>
              <XAxis dataKey="cycle"
                tick={{ fontSize:9, fontFamily:'var(--font-mono)', fill:'var(--text-muted)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize:9, fontFamily:'var(--font-mono)', fill:'var(--text-muted)' }}
                tickLine={false}
              />
              <Tooltip content={<Tooltip2/>}/>
              <Line type="monotone" dataKey="rul_true"
                name="RUL réelle" stroke="var(--green)"
                strokeWidth={1.5} strokeDasharray="6 3"
                dot={false} isAnimationActive={false} connectNulls
              />
              <Line type="monotone" dataKey="rul"
                name="RUL prédite" stroke="var(--cyan)"
                strokeWidth={2.5} dot={false}
                isAnimationActive={false} connectNulls
                style={{ filter:'drop-shadow(0 0 5px var(--cyan))' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{
            height:180, display:'flex', flexDirection:'column',
            alignItems:'center', justifyContent:'center',
            color:'var(--text-dim)', fontFamily:'var(--font-mono)',
            fontSize:12, gap:12,
          }}>
            <div>Sélectionnez Turbine_01 ou Turbine_02</div>
            <div style={{
              padding:'6px 14px', borderRadius:20,
              border:'1px solid var(--border)',
              fontFamily:'var(--font-mono)', fontSize:9,
              color:'var(--text-dim)',
            }}>
              Dataset CMAPSS requis pour la courbe RUL
            </div>
          </div>
        )}
      </div>
    </div>
  )
}