import { useState, useEffect, useRef, useCallback } from 'react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { Play, Pause, RotateCcw, FastForward } from 'lucide-react'
import { endpoints } from '../api/client'

const CustomTooltip = ({ active, payload, label }) => {
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
          {p.name} : {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
        </div>
      ))}
    </div>
  )
}

function LiveIndicator({ label, value, unit, warn, danger, color='var(--cyan)' }) {
  const isWarn   = warn   != null && value != null && value > warn
  const isDanger = danger != null && value != null && value > danger
  const c = isDanger ? 'var(--red)' : isWarn ? 'var(--amber)' : color

  return (
    <div style={{
      background   : 'var(--bg-elevated)',
      border       : `1px solid ${isDanger ? 'var(--red)' : 'var(--border)'}`,
      borderRadius : 'var(--radius)',
      padding      : '10px 12px',
      boxShadow    : isDanger ? '0 0 12px var(--red-dim)' : 'none',
      transition   : 'all 0.3s',
    }}>
      <div className="metric-label" style={{ marginBottom: 5 }}>{label}</div>
      <div style={{
        fontFamily : 'var(--font-display)',
        fontSize   : 18,
        fontWeight : 700,
        color      : c,
        filter     : isDanger ? 'drop-shadow(0 0 6px var(--red))' : 'none',
      }}>
        {value != null
          ? (typeof value === 'number' ? value.toFixed(3) : value)
          : <span style={{ color:'var(--text-dim)', fontSize:12 }}>—</span>
        }
        {value != null && unit && (
          <span style={{
            fontSize:9, color:'var(--text-muted)',
            fontFamily:'var(--font-mono)', marginLeft:3,
          }}>{unit}</span>
        )}
      </div>
      {isDanger && (
        <div style={{
          fontFamily:'var(--font-mono)', fontSize:8,
          color:'var(--red)', marginTop:2,
          animation:'glow-pulse 1s infinite',
        }}>⛔ CRITIQUE</div>
      )}
      {isWarn && !isDanger && (
        <div style={{
          fontFamily:'var(--font-mono)', fontSize:8,
          color:'var(--amber)', marginTop:2,
        }}>⚠ SEUIL</div>
      )}
    </div>
  )
}

function KpiCard({ label, value, unit, color = 'var(--cyan)' }) {
  return (
    <div style={{
      background   : 'var(--bg-elevated)',
      border       : '1px solid var(--border)',
      borderRadius : 'var(--radius)',
      padding      : '10px 12px',
    }}>
      <div className="metric-label" style={{ marginBottom: 5 }}>{label}</div>
      <div style={{
        fontFamily : 'var(--font-display)',
        fontSize   : 16,
        fontWeight : 700,
        color,
      }}>
        {value != null
          ? (typeof value === 'number' ? value.toFixed(1) : value)
          : '—'
        }
        {unit && (
          <span style={{
            fontSize:9, color:'var(--text-muted)',
            fontFamily:'var(--font-mono)', marginLeft:3,
          }}>{unit}</span>
        )}
      </div>
    </div>
  )
}

export default function Monitoring({ ws }) {
  const [indics,  setIndics]  = useState(null)
  const [fftData, setFftData] = useState(null)
  const [kpis,    setKpis]    = useState(null)
  const [speed,   setSpeed]   = useState(0.5)
  const [running, setRunning] = useState(true)
  const kpiRef    = useRef(null)

  const { data, history, pause, play, reset, setSpeed: wsSetSpeed } = ws

    // ── Indicateurs : depuis le WS à chaque cycle ─────────────────────────────
  useEffect(() => {
    if (!data?.features) return
    setIndics({
      RMS          : data.features.RMS          ?? null,
      Kurtosis     : data.features.Kurtosis     ?? null,
      Crest_Factor : data.features.Crest_Factor ?? null,
      Peak_to_Peak : data.features.Peak_to_Peak ?? null,
      Skewness     : data.features.Skewness     ?? null,
      Std          : data.features.Std          ?? null,
      Kurtosis_flag: (data.features.Kurtosis ?? 0) > 4 ? 'anomalie' : 'normal',
    })
  }, [data?.features])

  // ── FFT : fournie directement par le backend dans chaque message WS ────────
  // (auparavant un appel REST throttlé, fragile et désynchronisé → spectre vide)
  useEffect(() => {
    if (data?.fft?.freqs?.length) setFftData(data.fft)
  }, [data?.fft])

  // Charger KPIs de la machine active
  useEffect(() => {
    if (!data?.machine_id) return
    clearInterval(kpiRef.current)
    const loadKpi = () => {
      endpoints.kpi(data.machine_id)
        .then(r => setKpis(r.data))
        .catch(() => {})
    }
    loadKpi()
    kpiRef.current = setInterval(loadKpi, 15000)
    return () => clearInterval(kpiRef.current)
  }, [data?.machine_id])

  const handlePlayPause = () => {
    if (running) { pause(); setRunning(false) }
    else         { play();  setRunning(true) }
  }
  const handleSpeed = (s) => { setSpeed(s); wsSetSpeed(s) }

  // Spectre FFT pour le graphique — mise à l'échelle AUTOMATIQUE
  // (le plancher de bruit du spectre est ramené à 0 et les pics ressortent ;
  //  robuste quelle que soit l'amplitude du signal, contrairement à un
  //  décalage fixe « +80 dB » qui pouvait tout écraser à zéro)
  const fftChartData = (() => {
    if (!fftData?.freqs?.length) return []
    const freqs  = fftData.freqs
    const specDb = fftData.spectrum_db ?? fftData.spectrum_lin
    if (!specDb?.length) return []

    const window = specDb.slice(0, 256).filter(v => Number.isFinite(v))
    const floor  = window.length ? Math.min(...window) : 0

    return freqs
      .slice(0, 256)
      .map((f, i) => ({
        freq : Math.round(f),
        amp  : Number.isFinite(specDb[i]) ? Math.max(0, specDb[i] - floor) : 0,
      }))
  })()

  const hiColor = (data?.health_index ?? 100) >= 70 ? 'var(--green)'
                : (data?.health_index ?? 100) >= 40 ? 'var(--amber)'
                : (data?.health_index ?? 100) >= 20 ? 'var(--orange)'
                :                                     'var(--red)'

  // Données RUL pour le graphique
  const hasRUL = history.some(h => h.rul_pred != null && h.rul_pred > 0)
  const hasHI  = history.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header + contrôles */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <h1 style={{
            fontFamily:'var(--font-display)', fontSize:22,
            color:'var(--text)', letterSpacing:'0.05em',
          }}>MONITORING SIGNAL</h1>
          <p style={{
            fontFamily:'var(--font-mono)', fontSize:11,
            color:'var(--text-muted)', marginTop:4,
          }}>
            {data?.machine_id || '—'}
            {data?.dataset  && ` · ${data.dataset}`}
            {data?.unit_id  && ` · Unité ${data.unit_id}`}
          </p>
        </div>
        <div style={{
          display:'flex', alignItems:'center', gap:8,
          background:'var(--bg-surface)', border:'1px solid var(--border)',
          borderRadius:'var(--radius)', padding:'8px 12px',
        }}>
          <button className="btn btn-ghost" onClick={handlePlayPause}
            style={{ padding:'5px 9px' }}>
            {running ? <Pause size={14}/> : <Play size={14}/>}
          </button>
          <button className="btn btn-ghost" onClick={() => { reset(); setIndics(null); setFftData(null) }}
            style={{ padding:'5px 9px' }}>
            <RotateCcw size={14}/>
          </button>
          <div style={{ display:'flex', alignItems:'center', gap:5, marginLeft:6 }}>
            <FastForward size={11} color="var(--text-muted)"/>
            {[0.1, 0.5, 1.0, 2.0].map(s => (
              <button key={s} onClick={() => handleSpeed(s)} style={{
                padding:'3px 7px', borderRadius:4, border:'1px solid',
                borderColor: speed===s ? 'var(--cyan)' : 'var(--border)',
                background:  speed===s ? 'var(--cyan-dim)' : 'transparent',
                color:       speed===s ? 'var(--cyan)' : 'var(--text-muted)',
                fontFamily:'var(--font-mono)', fontSize:10, cursor:'pointer',
              }}>{s}s</button>
            ))}
          </div>
        </div>
      </div>

      {/* Barre progression */}
      {data?.progress && (
        <div style={{
          background:'var(--bg-card)', border:'1px solid var(--border)',
          borderRadius:'var(--radius)', padding:'10px 14px',
          display:'flex', alignItems:'center', gap:14,
        }}>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10,
            color:'var(--text-muted)', whiteSpace:'nowrap' }}>
            CYCLE {data.progress.current} / {data.progress.total}
          </span>
          <div style={{
            flex:1, height:4, background:'var(--border)',
            borderRadius:2, overflow:'hidden',
          }}>
            <div style={{
              width:`${data.progress.pct}%`, height:'100%',
              background:`linear-gradient(90deg, ${hiColor}88, ${hiColor})`,
              transition:'width 0.5s ease', boxShadow:`0 0 6px ${hiColor}`,
            }}/>
          </div>
          <span style={{
            fontFamily:'var(--font-display)', fontSize:12,
            color:hiColor, whiteSpace:'nowrap', fontWeight:700,
          }}>
            {data.progress.pct}%
          </span>
        </div>
      )}

      {/* ── Indicateurs vibratoires ── */}
      <div>
        <div style={{
          fontFamily:'var(--font-display)', fontSize:9,
          color:'var(--text-muted)', letterSpacing:'0.12em', marginBottom:8,
        }}>
          INDICATEURS VIBRATOIRES
        </div>
        <div style={{
          display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:8,
        }}>
          <LiveIndicator label="RMS"          value={indics?.RMS}          unit="g"  color="var(--cyan)"   warn={2.0} danger={4.5} />
          <LiveIndicator label="Kurtosis"     value={indics?.Kurtosis}                color="var(--green)"  warn={4}   danger={10}  />
          <LiveIndicator label="Crest Factor" value={indics?.Crest_Factor}             color="var(--amber)"  warn={4}   danger={6}   />
          <LiveIndicator label="Peak-to-Peak" value={indics?.Peak_to_Peak} unit="g"  color="var(--orange)"                          />
          <LiveIndicator label="Skewness"     value={indics?.Skewness}                color="var(--cyan)"                            />
          <LiveIndicator label="Std"          value={indics?.Std}          unit="g"  color="var(--cyan)"                            />
        </div>
      </div>

      {/* ── Graphiques : Signal | Spectre FFT côte à côte ── */}
      <div style={{
        display:'grid', gridTemplateColumns:'1fr 1fr', gap:14,
      }}>
        {/* Health Index temps réel */}
        <div className="card">
          <div style={{
            display:'flex', justifyContent:'space-between',
            alignItems:'center', marginBottom:12,
          }}>
            <h3 style={{
              fontFamily:'var(--font-display)', fontSize:9,
              color:'var(--text-muted)', letterSpacing:'0.1em',
            }}>HEALTH INDEX — TEMPS RÉEL</h3>
            {running && (
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
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={history}
                margin={{ top:4, right:0, bottom:0, left:-20 }}>
                <defs>
                  <linearGradient id="hi-mon" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor={hiColor} stopOpacity={0.3}/>
                    <stop offset="100%" stopColor={hiColor} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)"/>
                <XAxis dataKey="cycle" hide/>
                <YAxis domain={[0,100]} hide/>
                <Tooltip content={<CustomTooltip/>}/>
                <Area type="monotone" dataKey="health_index"
                  name="Health Index (%)"
                  stroke={hiColor} fill="url(#hi-mon)"
                  strokeWidth={2} dot={false} isAnimationActive={false}
                  style={{ filter:`drop-shadow(0 0 4px ${hiColor})` }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              height:120, display:'flex', alignItems:'center',
              justifyContent:'center', color:'var(--text-dim)',
              fontFamily:'var(--font-mono)', fontSize:11,
            }}>Démarrez la simulation</div>
          )}

          {/* RUL prédite vs réelle */}
          <div style={{ marginTop:10 }}>
            <div style={{
              fontFamily:'var(--font-display)', fontSize:9,
              color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:6,
            }}>
              RUL PRÉDITE (cyan) VS RÉELLE (vert)
            </div>
            {hasRUL ? (
              <ResponsiveContainer width="100%" height={110}>
                <LineChart data={history}
                  margin={{ top:4, right:0, bottom:0, left:-20 }}>
                  <CartesianGrid stroke="var(--border)"/>
                  <XAxis dataKey="cycle" hide/>
                  <YAxis hide/>
                  <Tooltip content={<CustomTooltip/>}/>
                  <Line type="monotone" dataKey="rul_true"
                    name="RUL réelle" stroke="var(--green)"
                    strokeWidth={1.5} strokeDasharray="5 3"
                    dot={false} isAnimationActive={false} connectNulls
                  />
                  <Line type="monotone" dataKey="rul_pred"
                    name="RUL prédite" stroke="var(--cyan)"
                    strokeWidth={2} dot={false}
                    isAnimationActive={false} connectNulls
                    style={{ filter:'drop-shadow(0 0 4px var(--cyan))' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{
                height:110, display:'flex', alignItems:'center',
                justifyContent:'center', color:'var(--text-dim)',
                fontFamily:'var(--font-mono)', fontSize:10,
              }}>
                RUL disponible sur CMAPSS
              </div>
            )}
          </div>
        </div>

        {/* Spectre FFT */}
        <div className="card">
          <div style={{
            display:'flex', justifyContent:'space-between',
            alignItems:'center', marginBottom:12,
          }}>
            <h3 style={{
              fontFamily:'var(--font-display)', fontSize:9,
              color:'var(--text-muted)', letterSpacing:'0.1em',
            }}>SPECTRE FFT</h3>
            <span style={{
              fontFamily:'var(--font-mono)', fontSize:8,
              color:'var(--text-muted)',
            }}>
              {fftData?.resolution_hz
                ? `Rés. ${fftData.resolution_hz} Hz`
                : 'Mise à jour toutes les 3s'}
            </span>
          </div>

          {fftChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={fftChartData} barSize={2}
                margin={{ top:0, right:0, bottom:0, left:-20 }}>
                <CartesianGrid vertical={false} stroke="var(--border)"/>
                <XAxis dataKey="freq"
                  tick={{ fontSize:8, fontFamily:'var(--font-mono)',
                    fill:'var(--text-muted)' }}
                  tickLine={false} interval={24}
                  label={{ value:'Hz', position:'insideBottomRight',
                    style:{ fontSize:8, fill:'var(--text-muted)' } }}
                />
                <YAxis hide/>
                <Tooltip content={<CustomTooltip/>}/>
                <Bar dataKey="amp" name="Amplitude (dB)"
                  fill="var(--cyan)" opacity={0.85}
                  style={{ filter:'drop-shadow(0 0 2px var(--cyan))' }}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              height:240, display:'flex', flexDirection:'column',
              alignItems:'center', justifyContent:'center',
              color:'var(--text-dim)', fontFamily:'var(--font-mono)', fontSize:11, gap:8,
            }}>
              <div>Calcul FFT en cours...</div>
              <div style={{ fontSize:9 }}>
                Démarre après 3s de simulation
              </div>
            </div>
          )}

          {/* Interprétation Kurtosis */}
          {indics?.Kurtosis != null && (
            <div style={{
              marginTop:10, padding:'7px 10px',
              background: indics.Kurtosis > 4
                ? 'var(--red-dim)' : 'var(--green-dim)',
              borderRadius:'var(--radius)',
              fontFamily:'var(--font-mono)', fontSize:10,
              color: indics.Kurtosis > 4 ? 'var(--red)' : 'var(--green)',
              border:`1px solid ${indics.Kurtosis > 4 ? 'var(--red)' : 'var(--green)'}`,
            }}>
              {indics.Kurtosis > 10 ? `⛔ Kurtosis=${indics.Kurtosis.toFixed(2)} — Défaut sévère`
               : indics.Kurtosis > 4  ? `⚠ Kurtosis=${indics.Kurtosis.toFixed(2)} — Défaut probable`
               :                        `✓ Kurtosis=${indics.Kurtosis.toFixed(2)} — Normal`}
            </div>
          )}
        </div>
      </div>

      {/* Score anomalie */}
      <div className="card">
        <h3 style={{
          fontFamily:'var(--font-display)', fontSize:9,
          color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:10,
        }}>
          SCORE D'ANOMALIE — AUTOENCODER
        </h3>
        {hasHI ? (
          <ResponsiveContainer width="100%" height={85}>
            <AreaChart data={history}
              margin={{ top:4, right:0, bottom:0, left:-20 }}>
              <defs>
                <linearGradient id="anom-g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="var(--red)" stopOpacity={0.4}/>
                  <stop offset="100%" stopColor="var(--red)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)"/>
              <XAxis dataKey="cycle" hide/>
              <YAxis domain={[0,100]} hide/>
              <Tooltip content={<CustomTooltip/>}/>
              <ReferenceLine y={50} stroke="var(--red)"
                strokeDasharray="4 4" opacity={0.5}
                label={{ value:'Seuil 50%', position:'insideRight',
                  style:{ fontSize:8, fill:'var(--red)' } }}
              />
              <Area type="monotone" dataKey="anomaly"
                name="Score anomalie (%)"
                stroke="var(--red)" fill="url(#anom-g)"
                strokeWidth={1.5} dot={false} isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{
            height:85, display:'flex', alignItems:'center',
            justifyContent:'center', color:'var(--text-dim)',
            fontFamily:'var(--font-mono)', fontSize:11,
          }}>Démarrez la simulation</div>
        )}
      </div>

      {/* KPIs industriels */}
      {kpis?.kpis && (
        <div>
          <div style={{
            fontFamily:'var(--font-display)', fontSize:9,
            color:'var(--text-muted)', letterSpacing:'0.12em', marginBottom:8,
          }}>
            KPIs INDUSTRIELS — {data?.machine_id}
          </div>
          <div style={{
            display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:8,
          }}>
            <KpiCard label="MTBF"         value={kpis.kpis.MTBF}         unit="h"  color="var(--amber)"/>
            <KpiCard label="MTTR"         value={kpis.kpis.MTTR}         unit="h"  color="var(--orange)"/>
            <KpiCard label="MTTF"         value={kpis.kpis.MTTF}         unit="h"  color="var(--amber)"/>
            <KpiCard label="Disponibilité" value={kpis.kpis.availability} unit="%"  color="var(--green)"/>
            <KpiCard label="Fiabilité"    value={kpis.kpis.reliability}  unit="%"  color="var(--cyan)"/>
            <KpiCard label="OEE"          value={kpis.kpis.OEE}          unit="%"  color="var(--cyan)"/>
          </div>
          {kpis.cycles_to_maintenance != null && (
            <div style={{
              marginTop:10, padding:'8px 12px',
              background:'var(--amber-dim)', border:'1px solid var(--amber)',
              borderRadius:'var(--radius)',
              fontFamily:'var(--font-mono)', fontSize:10, color:'var(--amber)',
            }}>
              ⚡ Estimation maintenance dans{' '}
              <strong>{kpis.cycles_to_maintenance}</strong> cycles
            </div>
          )}
        </div>
      )}
    </div>
  )
}