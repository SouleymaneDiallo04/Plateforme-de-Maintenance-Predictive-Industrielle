import { useState, useEffect, useRef } from 'react'
import {
  ClipboardList, Bot, Send, Download,
  AlertTriangle, CheckCircle, Clock,
  RefreshCw, Zap, Upload, FileText
} from 'lucide-react'
import { endpoints } from '../api/client'


function AlertItem({ alert }) {
  const typeConfig = {
    alerte_rouge  : { color: 'var(--red)',    icon: '⛔' },
    alerte_orange : { color: 'var(--orange)', icon: '⚠️' },
    alerte_jaune  : { color: 'var(--amber)',  icon: '⚡' },
    rul_critique  : { color: 'var(--red)',    icon: '🔴' },
  }
  const cfg = typeConfig[alert.type] || { color: 'var(--cyan)', icon: '•' }

  return (
    <div style={{
      display      : 'flex',
      gap          : 12,
      padding      : '12px 0',
      borderBottom : '1px solid var(--border)',
      alignItems   : 'flex-start',
    }}>
      <span style={{ fontSize: 14, flexShrink: 0 }}>{cfg.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display    : 'flex',
          gap        : 8,
          alignItems : 'center',
          flexWrap   : 'wrap',
        }}>
          <span style={{
            fontFamily : 'var(--font-display)',
            fontSize   : 11,
            color      : cfg.color,
            letterSpacing: '0.05em',
          }}>
            {alert.machine_id}
          </span>
          <span style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
          }}>
            {alert.timestamp?.slice(0, 16).replace('T', ' ')}
          </span>
        </div>
        <div style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 11,
          color      : 'var(--text)',
          marginTop  : 4,
        }}>
          {alert.message}
        </div>
        {alert.hi && (
          <div style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
            marginTop  : 2,
          }}>
            HI : {alert.hi?.toFixed(1)}%
            {alert.rul != null && ` · RUL : ${Math.round(alert.rul)} cycles`}
          </div>
        )}
      </div>
    </div>
  )
}

function CopilotMessage({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{
      display        : 'flex',
      justifyContent : isUser ? 'flex-end' : 'flex-start',
      marginBottom   : 12,
    }}>
      {!isUser && (
        <div style={{
          width        : 28, height: 28,
          borderRadius : '50%',
          background   : 'var(--cyan-dim)',
          border       : '1px solid var(--cyan)',
          display      : 'flex',
          alignItems   : 'center',
          justifyContent: 'center',
          flexShrink   : 0,
          marginRight  : 8,
          marginTop    : 2,
        }}>
          <Bot size={14} color="var(--cyan)" />
        </div>
      )}
      <div style={{
        maxWidth     : '75%',
        padding      : '10px 14px',
        borderRadius : isUser
          ? '16px 16px 4px 16px'
          : '4px 16px 16px 16px',
        background   : isUser
          ? 'var(--cyan-dim)'
          : 'var(--bg-elevated)',
        border       : `1px solid ${isUser ? 'var(--cyan)' : 'var(--border)'}`,
        fontFamily   : 'var(--font-mono)',
        fontSize     : 12,
        color        : 'var(--text)',
        lineHeight   : 1.6,
        whiteSpace   : 'pre-wrap',
      }}>
        {msg.content}
      </div>
    </div>
  )
}

function SpectrumDiagnose() {
  const [mode,      setMode]      = useState('paste')  // 'paste' | 'file'
  const [freqsText, setFreqsText] = useState('')
  const [ampsText,  setAmpsText]  = useState('')
  const [isDb,      setIsDb]      = useState(true)
  const [hi,        setHi]        = useState(80)
  const [result,    setResult]    = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [fileName,  setFileName]  = useState(null)
  const fileRef = useRef(null)

  // Parser un fichier CSV ou JSON
  const handleFile = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFileName(f.name)
    setError(null)
    setResult(null)

    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target.result
      try {
        if (f.name.endsWith('.json')) {
          // Format JSON : { freqs: [...], amplitudes: [...] }
          // ou [[freq, amp], ...]
          const data = JSON.parse(content)
          if (Array.isArray(data) && Array.isArray(data[0])) {
            setFreqsText(data.map(row => row[0]).join(', '))
            setAmpsText (data.map(row => row[1]).join(', '))
          } else if (data.freqs && data.amplitudes) {
            setFreqsText(data.freqs.join(', '))
            setAmpsText (data.amplitudes.join(', '))
          } else {
            setError('Format JSON invalide. Attendu: {freqs:[], amplitudes:[]} ou [[f,a],...]')
          }
        } else {
          // Format CSV : deux colonnes freq,amp
          const lines = content.trim().split('\n')
          const freqs = [], amps = []
          lines.forEach((line, i) => {
            if (i === 0 && isNaN(parseFloat(line.split(/[,;\t]/)[0]))) return // header
            const parts = line.split(/[,;\t]/)
            if (parts.length >= 2) {
              const f = parseFloat(parts[0])
              const a = parseFloat(parts[1])
              if (!isNaN(f) && !isNaN(a)) {
                freqs.push(f)
                amps.push(a)
              }
            }
          })
          if (freqs.length < 10) {
            setError(`Trop peu de points valides : ${freqs.length} (minimum 10)`)
          } else {
            setFreqsText(freqs.join(', '))
            setAmpsText (amps.join(', '))
          }
        }
        setMode('paste')
      } catch (err) {
        setError('Erreur de parsing : ' + err.message)
      }
    }
    reader.readAsText(f)
  }

  const diagnose = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const freqs = freqsText.split(/[,\s\n;]+/)
        .map(parseFloat).filter(n => !isNaN(n))
      const amps  = ampsText.split(/[,\s\n;]+/)
        .map(parseFloat).filter(n => !isNaN(n))

      if (freqs.length < 10) {
        setError(`Minimum 10 points requis (actuellement ${freqs.length})`)
        return
      }
      if (freqs.length !== amps.length) {
        setError(`Nombre de fréquences (${freqs.length}) ≠ amplitudes (${amps.length})`)
        return
      }

      const r = await api.post('/diagnose/spectrum', {
        freqs,
        amplitudes   : amps,
        is_db        : isDb,
        health_index : hi,
      })
      setResult(r.data)
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map(d => d.msg).join(', ')
        : 'Erreur de diagnostic')
    } finally {
      setLoading(false)
    }
  }

  const diagColor = result ? ({
    sain              : 'var(--green)',
    desequilibre      : 'var(--amber)',
    desalignement     : 'var(--amber)',
    roulement_externe : 'var(--red)',
    roulement_interne : 'var(--red)',
    roulement_bille   : 'var(--orange)',
    jeu_mecanique     : 'var(--orange)',
  }[result.diagnosis?.fault] || 'var(--cyan)') : 'var(--cyan)'

  return (
    <div>
      {/* Onglets mode saisie */}
      <div style={{ display:'flex', gap:8, marginBottom:14 }}>
        {[
          { id:'paste', label:'Coller les données' },
          { id:'file',  label:'Importer CSV / JSON' },
        ].map(tab => (
          <button key={tab.id} onClick={() => setMode(tab.id)} style={{
            padding    : '6px 14px',
            borderRadius: 'var(--radius)',
            border     : '1px solid',
            borderColor: mode === tab.id ? 'var(--cyan)' : 'var(--border)',
            background : mode === tab.id ? 'var(--cyan-dim)' : 'transparent',
            color      : mode === tab.id ? 'var(--cyan)' : 'var(--text-muted)',
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            cursor     : 'pointer',
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Mode : importer un fichier */}
      {mode === 'file' && (
        <div>
          <div
            onClick={() => fileRef.current?.click()}
            style={{
              border        : `2px dashed ${fileName ? 'var(--cyan)' : 'var(--border)'}`,
              borderRadius  : 'var(--radius-lg)',
              padding       : '20px',
              textAlign     : 'center',
              cursor        : 'pointer',
              background    : fileName ? 'var(--cyan-dim)' : 'transparent',
              marginBottom  : 12,
            }}
          >
            <Upload size={20}
              color={fileName ? 'var(--cyan)' : 'var(--text-muted)'}
              style={{ margin:'0 auto 8px' }}
            />
            <div style={{
              fontFamily:'var(--font-mono)', fontSize:11,
              color: fileName ? 'var(--cyan)' : 'var(--text-muted)',
            }}>
              {fileName || 'Cliquer pour importer (CSV ou JSON)'}
            </div>
            <div style={{
              fontFamily:'var(--font-mono)', fontSize:9,
              color:'var(--text-dim)', marginTop:4,
            }}>
              CSV : deux colonnes (fréquence, amplitude) · JSON : {`{freqs:[], amplitudes:[]}`}
            </div>
            <input ref={fileRef} type="file" accept=".csv,.json,.txt"
              onChange={handleFile} style={{ display:'none' }}
            />
          </div>
          {fileName && (
            <div style={{
              fontFamily:'var(--font-mono)', fontSize:10,
              color:'var(--green)', marginBottom:8,
            }}>
              ✓ Fichier chargé : {fileName}
              {freqsText && ` — ${freqsText.split(',').filter(Boolean).length} points`}
            </div>
          )}
        </div>
      )}

      {/* Mode : coller les données */}
      {mode === 'paste' && (
        <div style={{
          display:'grid', gridTemplateColumns:'1fr 1fr',
          gap:12, marginBottom:12,
        }}>
          <div>
            <div className="metric-label" style={{ marginBottom:5 }}>
              Fréquences (Hz)
            </div>
            <textarea
              value       = {freqsText}
              onChange    = {e => setFreqsText(e.target.value)}
              placeholder = "0, 12.5, 25, 37.5, 50, 62.5, 75..."
              style       = {{
                width:'100%', height:80,
                background:'var(--bg-elevated)', border:'1px solid var(--border)',
                borderRadius:'var(--radius)', color:'var(--text)',
                padding:'8px 10px', fontFamily:'var(--font-mono)',
                fontSize:10, resize:'vertical', outline:'none',
              }}
            />
          </div>
          <div>
            <div className="metric-label" style={{ marginBottom:5 }}>
              Amplitudes ({isDb ? 'dB' : 'linéaire'})
            </div>
            <textarea
              value       = {ampsText}
              onChange    = {e => setAmpsText(e.target.value)}
              placeholder = "-80, -75, -60, -55, -78, -82..."
              style       = {{
                width:'100%', height:80,
                background:'var(--bg-elevated)', border:'1px solid var(--border)',
                borderRadius:'var(--radius)', color:'var(--text)',
                padding:'8px 10px', fontFamily:'var(--font-mono)',
                fontSize:10, resize:'vertical', outline:'none',
              }}
            />
          </div>
        </div>
      )}

      {/* Options + bouton analyser */}
      <div style={{
        display:'flex', gap:14, alignItems:'center',
        flexWrap:'wrap', marginBottom:12,
      }}>
        <label style={{ display:'flex', alignItems:'center', gap:6, cursor:'pointer' }}>
          <input type="checkbox" checked={isDb}
            onChange={e => setIsDb(e.target.checked)}
            style={{ accentColor:'var(--cyan)' }}
          />
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10,
            color:'var(--text-muted)' }}>
            Amplitudes en dB
          </span>
        </label>

        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span className="metric-label">Health Index actuel</span>
          <input type="range" min={0} max={100} value={hi}
            onChange={e => setHi(Number(e.target.value))}
            style={{ accentColor:'var(--cyan)', width:70 }}
          />
          <span style={{
            fontFamily:'var(--font-display)', fontSize:13,
            color:'var(--cyan)', fontWeight:700,
          }}>{hi}%</span>
        </div>

        <button
          className = "btn btn-primary"
          onClick   = {diagnose}
          disabled  = {loading || (!freqsText && !ampsText)}
          style     = {{ marginLeft:'auto' }}
        >
          {loading ? 'Analyse en cours...' : 'Analyser le spectre'}
        </button>
      </div>

      {/* Erreur */}
      {error && (
        <div style={{
          padding:'8px 12px', background:'var(--red-dim)',
          border:'1px solid var(--red)', borderRadius:'var(--radius)',
          fontFamily:'var(--font-mono)', fontSize:11, color:'var(--red)',
          marginBottom:12,
        }}>
          ⛔ {error}
        </div>
      )}

      {/* Résultat diagnostic */}
      {result && (
        <div style={{
          background   : 'var(--bg-elevated)',
          border       : `1px solid ${diagColor}`,
          borderRadius : 'var(--radius)',
          padding      : '14px 16px',
          boxShadow    : `0 0 20px ${diagColor}22`,
        }}>
          <div style={{
            fontFamily:'var(--font-display)', fontSize:16,
            color:diagColor, letterSpacing:'0.05em', marginBottom:12,
            filter:`drop-shadow(0 0 6px ${diagColor})`,
          }}>
            {result.diagnosis?.fault?.toUpperCase().replace(/_/g, ' ') || '—'}
          </div>
          <div style={{
            display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:10,
            marginBottom:12,
          }}>
            <div>
              <div className="metric-label">Confiance</div>
              <div style={{
                fontFamily:'var(--font-display)', fontSize:22,
                color:diagColor, fontWeight:700,
              }}>
                {((result.diagnosis?.confidence || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="metric-label">Sévérité</div>
              <div style={{
                fontFamily:'var(--font-mono)', fontSize:13,
                color:'var(--text)', marginTop:4,
              }}>
                {result.diagnosis?.severity?.toUpperCase() || '—'}
              </div>
            </div>
            <div>
              <div className="metric-label">Délai d'intervention</div>
              <div style={{
                fontFamily:'var(--font-mono)', fontSize:11,
                color:'var(--text)', marginTop:4, lineHeight:1.5,
              }}>
                {result.recommendation?.delay || '—'}
              </div>
            </div>
          </div>
          <div style={{
            fontFamily:'var(--font-mono)', fontSize:10,
            color:'var(--text-muted)',
            padding:'7px 10px', background:'var(--bg-card)',
            borderRadius:'var(--radius)', marginBottom:8,
          }}>
            {result.diagnosis?.message}
          </div>
          <div style={{
            fontFamily:'var(--font-mono)', fontSize:10,
            color: diagColor === 'var(--red)' ? 'var(--red)' : 'var(--amber)',
            fontWeight:600,
          }}>
            → {result.recommendation?.action}
          </div>

          {/* Fréquences détectées */}
          {result.annotations?.length > 0 && (
            <div style={{ marginTop:12 }}>
              <div className="metric-label" style={{ marginBottom:6 }}>
                FRÉQUENCES CARACTÉRISTIQUES DÉTECTÉES
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                {result.annotations.map((a, i) => (
                  <span key={i} style={{
                    padding    : '3px 8px',
                    borderRadius: 10,
                    border     : `1px solid ${a.color === 'red'
                      ? 'var(--red)'
                      : a.color === 'orange'
                      ? 'var(--orange)'
                      : 'var(--border)'}`,
                    background : a.color === 'red'
                      ? 'var(--red-dim)'
                      : 'transparent',
                    fontFamily : 'var(--font-mono)',
                    fontSize   : 9,
                    color      : a.color === 'red'
                      ? 'var(--red)'
                      : a.color === 'orange'
                      ? 'var(--orange)'
                      : 'var(--text-muted)',
                  }}>
                    {a.name} = {a.frequency_hz} Hz
                    {a.is_primary && ' ★'}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Maintenance({ alerts: externalAlerts = [] }) {
  const [alerts,   setAlerts]   = useState(externalAlerts)
  const [messages, setMessages] = useState([{
    role   : 'assistant',
    content: 'Bonjour. Je suis le Copilot PrognoSense.\n' +
             'Je surveille votre flotte en temps réel.\n' +
             'Posez-moi une question sur vos machines ou demandez ' +
             'un rapport d\'intervention.',
  }])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [retrain,  setRetrain]  = useState({ running: false, progress: 0 })
  const chatRef  = useRef(null)
  const pollRef  = useRef(null)

  useEffect(() => {
    endpoints.alerts()
      .then(r => setAlerts(r.data.alerts || []))
      .catch(() => {})
  }, [])

  // Scroll chat vers le bas
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = async (text = input) => {
    if (!text.trim() || loading) return

    const userMsg = { role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const history = messages
        .slice(-6)
        .map(m => ({ role: m.role, content: m.content }))

      const r = await endpoints.copilotChat({
        message : text.trim(),
        history,
      })
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: r.data.reply }
      ])
    } catch (e) {
      setMessages(prev => [
        ...prev,
        {
          role   : 'assistant',
          content: 'Erreur de connexion au Copilot. ' +
                   'Vérifiez la clé ANTHROPIC_API_KEY.'
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const generateReport = async (machineId) => {
    setLoading(true)
    try {
      const r = await endpoints.copilotReport(machineId)
      setMessages(prev => [
        ...prev,
        {
          role   : 'assistant',
          content: `📋 RAPPORT D'INTERVENTION — ${machineId}\n\n` +
                   r.data.reply
        }
      ])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const exportReport = (machineId) => {
    window.open(endpoints.exportReport(machineId), '_blank')
  }

  const exportBenchmark = () => {
    window.open(endpoints.exportBenchmark(), '_blank')
  }

  // Polling réentraînement
  const startRetrain = async () => {
    setRetrain({ running: true, progress: 0 })
    pollRef.current = setInterval(async () => {
      try {
        const r = await endpoints.retrainStatus()
        const s = r.data
        setRetrain({
          running  : s.running,
          progress : s.progress,
          message  : s.message,
        })
        if (!s.running) {
          clearInterval(pollRef.current)
        }
      } catch (e) {
        clearInterval(pollRef.current)
      }
    }, 1000)
  }

  const suggestions = [
    'Quelles machines nécessitent une intervention urgente ?',
    'Génère un rapport pour Turbine_01',
    'Analyse le risque si on reporte de 10 cycles',
    'Quels capteurs surveiller en priorité ?',
  ]

  const criticalAlerts = alerts.filter(
    a => a.type?.includes('rouge') || a.type?.includes('critique')
  )

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
          }}>
            LOG & MAINTENANCE
          </h1>
          <p style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 11,
            color      : 'var(--text-muted)',
            marginTop  : 4,
          }}>
            JOURNAL DES ALERTES · COPILOT IA · RÉENTRAÎNEMENT
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className = "btn btn-ghost"
            onClick   = {exportBenchmark}
          >
            <Download size={14} />
            Export Benchmark
          </button>
          <button
            className = "btn btn-primary"
            onClick   = {() => exportReport('Turbine_01')}
          >
            <FileText size={14} />
            Export Rapport
          </button>
        </div>
      </div>

      {/* Alertes critiques */}
      {criticalAlerts.length > 0 && (
        <div style={{
          background   : 'var(--red-dim)',
          border       : '1px solid var(--red)',
          borderRadius : 'var(--radius)',
          padding      : '12px 16px',
          display      : 'flex',
          alignItems   : 'center',
          gap          : 12,
          animation    : 'pulse-red 2s infinite',
        }}>
          <Zap size={16} color="var(--red)" />
          <span style={{
            fontFamily : 'var(--font-display)',
            fontSize   : 12,
            color      : 'var(--red)',
            letterSpacing: '0.05em',
          }}>
            {criticalAlerts.length} ALERTE(S) CRITIQUE(S) — INTERVENTION REQUISE
          </span>
        </div>
      )}

      <div style={{
        display             : 'grid',
        gridTemplateColumns : '1fr 1fr',
        gap                 : 16,
        alignItems          : 'start',
      }}>

        {/* Journal des alertes */}
        <div className="card">
          <div style={{
            display        : 'flex',
            justifyContent : 'space-between',
            alignItems     : 'center',
            marginBottom   : 16,
          }}>
            <h3 style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 11,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
            }}>
              JOURNAL DES ALERTES
            </h3>
            <span style={{
              fontFamily   : 'var(--font-mono)',
              fontSize     : 10,
              color        : 'var(--text-muted)',
            }}>
              {alerts.length} événements
            </span>
          </div>

          <div style={{
            maxHeight  : 400,
            overflowY  : 'auto',
          }}>
            {alerts.length === 0 ? (
              <div style={{
                padding    : '40px 0',
                textAlign  : 'center',
                color      : 'var(--text-muted)',
                fontFamily : 'var(--font-mono)',
                fontSize   : 12,
              }}>
                <CheckCircle
                  size  = {32}
                  color = "var(--green)"
                  style = {{ margin: '0 auto 8px' }}
                />
                <div>Aucune alerte active</div>
              </div>
            ) : (
              alerts.map((a, i) => (
                <AlertItem key={i} alert={a} />
              ))
            )}
          </div>

          {/* Boutons rapport rapide */}
          <div style={{
            marginTop  : 16,
            paddingTop : 16,
            borderTop  : '1px solid var(--border)',
            display    : 'flex',
            gap        : 8,
            flexWrap   : 'wrap',
          }}>
            {['Turbine_01', 'M01', 'M02'].map(mid => (
              <button
                key       = {mid}
                className = "btn btn-ghost"
                onClick   = {() => generateReport(mid)}
                style     = {{ fontSize: 11 }}
              >
                <FileText size={12} />
                Rapport {mid}
              </button>
            ))}
          </div>
        </div>

        {/* Copilot LLM */}
        <div className="card" style={{
          display       : 'flex',
          flexDirection : 'column',
          height        : 550,
        }}>
          {/* Header Copilot */}
          <div style={{
            display        : 'flex',
            alignItems     : 'center',
            gap            : 10,
            marginBottom   : 16,
            paddingBottom  : 12,
            borderBottom   : '1px solid var(--border)',
          }}>
            <div style={{
              width        : 32, height: 32,
              borderRadius : '50%',
              background   : 'var(--cyan-dim)',
              border       : '1px solid var(--cyan)',
              display      : 'flex',
              alignItems   : 'center',
              justifyContent: 'center',
              boxShadow    : 'var(--cyan-glow)',
            }}>
              <Bot size={16} color="var(--cyan)" />
            </div>
            <div>
              <div style={{
                fontFamily : 'var(--font-display)',
                fontSize   : 12,
                color      : 'var(--cyan)',
                letterSpacing: '0.05em',
              }}>
                PROGNOSENSE COPILOT
              </div>
              <div style={{
                fontFamily : 'var(--font-mono)',
                fontSize   : 9,
                color      : 'var(--text-muted)',
              }}>
                Propulsé par Claude · Contexte flotte injecté
              </div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <span className="badge badge-green">
                <span style={{
                  width        : 5, height: 5,
                  borderRadius : '50%',
                  background   : 'var(--green)',
                  display      : 'inline-block',
                  animation    : 'glow-pulse 2s infinite',
                }} />
                ACTIF
              </span>
            </div>
          </div>

          {/* Messages */}
          <div
            ref   = {chatRef}
            style = {{
              flex      : 1,
              overflowY : 'auto',
              paddingRight: 4,
            }}
          >
            {messages.map((m, i) => (
              <CopilotMessage key={i} msg={m} />
            ))}
            {loading && (
              <div style={{
                display    : 'flex',
                gap        : 4,
                padding    : '8px 0',
                marginLeft : 36,
              }}>
                {[0, 1, 2].map(i => (
                  <div
                    key   = {i}
                    style = {{
                      width        : 6, height: 6,
                      borderRadius : '50%',
                      background   : 'var(--cyan)',
                      animation    : `glow-pulse 1s ${i * 0.2}s infinite`,
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Suggestions rapides */}
          <div style={{
            display    : 'flex',
            gap        : 6,
            flexWrap   : 'wrap',
            marginTop  : 8,
            marginBottom: 8,
          }}>
            {suggestions.map((s, i) => (
              <button
                key     = {i}
                onClick = {() => sendMessage(s)}
                style   = {{
                  padding      : '4px 8px',
                  borderRadius : 12,
                  border       : '1px solid var(--border)',
                  background   : 'transparent',
                  color        : 'var(--text-muted)',
                  fontFamily   : 'var(--font-mono)',
                  fontSize     : 9,
                  cursor       : 'pointer',
                  transition   : 'all 0.2s',
                }}
                onMouseEnter = {e => {
                  e.target.style.borderColor = 'var(--cyan)'
                  e.target.style.color = 'var(--cyan)'
                }}
                onMouseLeave = {e => {
                  e.target.style.borderColor = 'var(--border)'
                  e.target.style.color = 'var(--text-muted)'
                }}
              >
                {s.length > 35 ? s.slice(0, 35) + '…' : s}
              </button>
            ))}
          </div>

          {/* Input */}
          <div style={{
            display      : 'flex',
            gap          : 8,
            borderTop    : '1px solid var(--border)',
            paddingTop   : 12,
          }}>
            <input
              value       = {input}
              onChange    = {e => setInput(e.target.value)}
              onKeyDown   = {e => e.key === 'Enter' && sendMessage()}
              placeholder = "Posez une question sur vos machines..."
              disabled    = {loading}
              style       = {{
                flex         : 1,
                background   : 'var(--bg-elevated)',
                border       : '1px solid var(--border)',
                borderRadius : 'var(--radius)',
                color        : 'var(--text)',
                padding      : '8px 12px',
                fontFamily   : 'var(--font-mono)',
                fontSize     : 12,
                outline      : 'none',
                transition   : 'border-color 0.2s',
              }}
              onFocus = {e => {
                e.target.style.borderColor = 'var(--cyan)'
              }}
              onBlur = {e => {
                e.target.style.borderColor = 'var(--border)'
              }}
            />
            <button
              className = "btn btn-primary"
              onClick   = {() => sendMessage()}
              disabled  = {loading || !input.trim()}
              style     = {{ padding: '8px 14px' }}
            >
              <Send size={14} />
            </button>
          </div>
        </div>
        {/* Import spectre pour diagnostic */}
        <div className="card">
          <h3 style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 11,
            color         : 'var(--text-muted)',
            letterSpacing : '0.1em',
            marginBottom  : 16,
          }}>
            DIAGNOSTIC PAR SPECTRE EXTERNE
          </h3>
          <p style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
            marginBottom: 14,
          }}>
            Collez un spectre FFT externe (fréquences et amplitudes séparées par virgules).
            Le système identifiera le type de défaut.
          </p>
          <SpectrumDiagnose />
        </div>
      </div>

      {/* Section réentraînement */}
      <div className="card">
        <h3 style={{
          fontFamily    : 'var(--font-display)',
          fontSize      : 11,
          color         : 'var(--text-muted)',
          letterSpacing : '0.1em',
          marginBottom  : 16,
        }}>
          RÉENTRAÎNEMENT DES MODÈLES
        </h3>
        <div style={{
          display    : 'flex',
          alignItems : 'center',
          gap        : 16,
        }}>
          <button
            className = "btn btn-primary"
            onClick   = {startRetrain}
            disabled  = {retrain.running}
          >
            <RefreshCw
              size  = {14}
              style = {{
                animation : retrain.running
                  ? 'spin 1s linear infinite'
                  : 'none',
              }}
            />
            {retrain.running ? 'Réentraînement...' : 'Lancer réentraînement'}
          </button>

          {retrain.running && (
            <div style={{ flex: 1 }}>
              <div style={{
                fontFamily : 'var(--font-mono)',
                fontSize   : 11,
                color      : 'var(--text-muted)',
                marginBottom: 6,
              }}>
                {retrain.message || 'Préparation...'}
              </div>
              <div style={{
                height       : 4,
                background   : 'var(--border)',
                borderRadius : 2,
                overflow     : 'hidden',
              }}>
                <div style={{
                  width        : `${retrain.progress}%`,
                  height       : '100%',
                  background   : 'linear-gradient(90deg, var(--cyan)88, var(--cyan))',
                  borderRadius : 2,
                  transition   : 'width 0.5s ease',
                  boxShadow    : '0 0 6px var(--cyan)',
                }} />
              </div>
            </div>
          )}

          {!retrain.running && retrain.progress === 100 && (
            <div style={{
              display    : 'flex',
              alignItems : 'center',
              gap        : 6,
              color      : 'var(--green)',
              fontFamily : 'var(--font-mono)',
              fontSize   : 11,
            }}>
              <CheckCircle size={14} />
              Réentraînement terminé
            </div>
          )}
        </div>
      </div>
    </div>
  )
}