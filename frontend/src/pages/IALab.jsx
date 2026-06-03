import { useState, useEffect } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, ReferenceLine,
  ScatterChart, Scatter, ZAxis
} from 'recharts'
import { FlaskConical, Trophy, Zap, Clock, Check } from 'lucide-react'
import { endpoints } from '../api/client'

const MODEL_COLORS = {
  'Decision Tree': '#FF6B35',
  'Random Forest': '#00FF9F',
  'XGBoost'      : '#00D4FF',
  'MLP'          : '#FFB800',
  'Huber Regressor': '#FF3366',
}

const DATASET_LABELS = {
  'VBL-VA001'         : 'Roulements / Désalignement',
  'CWRU'              : 'Roulements (10 classes)',
  'Mechanical Faults' : 'Défauts mécaniques',
  'CMAPSS'            : 'RUL Turbomoteurs',
}

function ModelSelectorCard({ dataset, models, activeModel, onSelect }) {
  return (
    <div className="card">
      <div style={{
        fontFamily    : 'var(--font-display)',
        fontSize      : 11,
        color         : 'var(--cyan)',
        letterSpacing : '0.1em',
        marginBottom  : 4,
      }}>
        {dataset}
      </div>
      <div style={{
        fontFamily  : 'var(--font-mono)',
        fontSize    : 10,
        color       : 'var(--text-muted)',
        marginBottom: 12,
      }}>
        {DATASET_LABELS[dataset] || ''}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {models.map(m => (
          <button
            key     = {m}
            onClick = {() => onSelect(dataset, m)}
            style   = {{
              padding      : '5px 10px',
              borderRadius : 20,
              border       : '1px solid',
              borderColor  : activeModel === m
                ? MODEL_COLORS[m] || 'var(--cyan)'
                : 'var(--border)',
              background   : activeModel === m
                ? `${MODEL_COLORS[m] || 'var(--cyan)'}22`
                : 'transparent',
              color        : activeModel === m
                ? MODEL_COLORS[m] || 'var(--cyan)'
                : 'var(--text-muted)',
              fontFamily   : 'var(--font-mono)',
              fontSize     : 10,
              cursor       : 'pointer',
              transition   : 'all 0.2s ease',
              display      : 'flex',
              alignItems   : 'center',
              gap          : 4,
            }}
          >
            {activeModel === m && <Check size={10} />}
            {m}
          </button>
        ))}
      </div>
    </div>
  )
}

function BenchmarkTable({ data, type }) {
  if (!data?.length) return (
    <div style={{
      padding    : 40,
      textAlign  : 'center',
      color      : 'var(--text-muted)',
      fontFamily : 'var(--font-mono)',
      fontSize   : 12,
    }}>
      Chargement du benchmark...
    </div>
  )

  const cols = type === 'classification'
    ? ['Modèle', 'Dataset', 'Accuracy (%)', 'F1-score', 'Inférence (ms)']
    : ['Modèle', 'Dataset', 'MAE (cycles)', 'RMSE (cycles)', 'R²', 'Score NASA']

  const keys = type === 'classification'
    ? ['Modèle', 'Dataset', 'Accuracy (%)', 'F1-score', 'Inférence (ms)']
    : ['Modèle', 'Dataset', 'MAE (cycles)', 'RMSE (cycles)', 'R²', 'Score NASA']

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width          : '100%',
        borderCollapse : 'collapse',
        fontFamily     : 'var(--font-mono)',
        fontSize       : 11,
      }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {cols.map(c => (
              <th key={c} style={{
                padding      : '8px 12px',
                textAlign    : 'left',
                color        : 'var(--text-muted)',
                fontSize     : 10,
                letterSpacing: '0.08em',
                fontWeight   : 500,
              }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const isXgb = row['Modèle'] === 'XGBoost'
            const acc   = row['Accuracy (%)']
            const isBest = acc >= 97

            return (
              <tr
                key   = {i}
                style = {{
                  borderBottom : '1px solid var(--border)',
                  background   : isBest
                    ? 'var(--cyan-dim)'
                    : i % 2 === 0 ? 'transparent' : 'var(--bg-elevated)',
                  transition   : 'background 0.2s',
                }}
              >
                {keys.map(k => (
                  <td key={k} style={{
                    padding   : '10px 12px',
                    color     : k === 'Modèle'
                      ? MODEL_COLORS[row[k]] || 'var(--text)'
                      : k === 'Accuracy (%)'
                      ? row[k] >= 97
                        ? 'var(--green)'
                        : row[k] >= 85
                        ? 'var(--cyan)'
                        : 'var(--text)'
                      : 'var(--text)',
                    fontWeight : k === 'Modèle' ? 500 : 400,
                  }}>
                    {k === 'Accuracy (%)' && isBest ? '🏆 ' : ''}
                    {row[k] ?? '—'}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Panneau Fiabilité des Modèles ─────────────────────────────────────────

function ModelReliabilityPanel({ dataset }) {
  const [drift, setDrift] = useState(null)

  useEffect(() => {
    endpoints.driftStatus()
      .then(r => setDrift(r.data))
      .catch(() => {})
  }, [dataset])

  const driftScore = drift?.[dataset]?.score ?? 0
  const driftColor = driftScore > 50 ? 'var(--red)'
                   : driftScore > 20 ? 'var(--amber)'
                   :                   'var(--green)'
  const lastDrift  = drift?.[dataset]?.last_drift

  return (
    <div className="card">
      <h3 style={{
        fontFamily:'var(--font-display)', fontSize:11,
        color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:16,
      }}>
        FIABILITÉ — {dataset}
      </h3>

      {/* Score de drift */}
      <div style={{ marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-muted)' }}>
            Score de dérive (concept drift KS-test)
          </span>
          <span style={{ fontFamily:'var(--font-display)', fontSize:16, color:driftColor, fontWeight:700 }}>
            {driftScore}%
          </span>
        </div>
        <div style={{ height:6, background:'var(--border)', borderRadius:3, overflow:'hidden' }}>
          <div style={{
            width:`${driftScore}%`, height:'100%', background:driftColor,
            transition:'width 0.6s ease',
          }}/>
        </div>
        <div style={{ fontFamily:'var(--font-mono)', fontSize:9, color:'var(--text-dim)', marginTop:6 }}>
          {driftScore > 50
            ? 'Réentraînement recommandé — les données de production divergent'
            : driftScore > 20
            ? 'Surveiller — légère dérive détectée'
            : 'Stable — modèle adapté aux données actuelles'
          }
        </div>
      </div>

      {/* Méta-informations */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        {[
          { label:'Dernier drift détecté', value: lastDrift
              ? new Date(lastDrift.timestamp).toLocaleDateString('fr-FR')
              : 'Aucun' },
          { label:'Sévérité drift',        value: lastDrift?.severity ?? '—' },
          { label:'Features en drift',     value: lastDrift?.n_drifted != null
              ? `${lastDrift.n_drifted} features`
              : '—' },
          { label:'Modèle actif',          value: drift?.[dataset]?.has_reference
              ? 'Référence chargée'
              : 'Pas de référence' },
        ].map(({ label, value }) => (
          <div key={label} style={{
            background:'var(--bg-elevated)', border:'1px solid var(--border)',
            borderRadius:'var(--radius)', padding:'8px 10px',
          }}>
            <div style={{ fontFamily:'var(--font-mono)', fontSize:9, color:'var(--text-muted)' }}>
              {label}
            </div>
            <div style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--text)', marginTop:3 }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Certifications */}
      <div style={{
        marginTop:16, padding:'10px 12px',
        background:'rgba(0,212,255,0.05)',
        border:'1px solid rgba(0,212,255,0.2)',
        borderRadius:'var(--radius)',
        fontFamily:'var(--font-mono)', fontSize:9,
        color:'var(--text-muted)', lineHeight:1.8,
      }}>
        Traçabilité conforme ISO 13373 · Audit trail JSONL quotidien<br/>
        Calibration probabiliste disponible via POST /api/explain/reliability<br/>
        Explainabilité SHAP disponible via POST /api/explain/shap
      </div>
    </div>
  )
}


// ── Carte Ensemble d'anomalie (3 algos) ───────────────────────────────────
function EnsembleAnomalyCard() {
  const [ds, setDs]           = useState('CWRU')
  const [res, setRes]         = useState(null)
  const [loading, setLoading] = useState(false)

  const run = () => {
    setLoading(true)
    endpoints.ensembleDemo(ds)
      .then(r => setRes(r.data))
      .catch(() => setRes(null))
      .finally(() => setLoading(false))
  }

  const consensus = res?.consensus_score ?? 0
  const cColor = consensus > 50 ? 'var(--red)' : consensus > 20 ? 'var(--amber)' : 'var(--green)'

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', margin: 0 }}>
          ENSEMBLE D'ANOMALIE — 3 ALGORITHMES (VOTE)
        </h3>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {['CWRU', 'MF', 'VBL'].map(d => (
            <button key={d} onClick={() => setDs(d)} style={{
              padding: '3px 10px', borderRadius: 14, fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer',
              border: `1px solid ${ds === d ? 'var(--cyan)' : 'var(--border)'}`,
              background: ds === d ? 'rgba(0,212,255,0.1)' : 'transparent',
              color: ds === d ? 'var(--cyan)' : 'var(--text-muted)',
            }}>{d}</button>
          ))}
          <button onClick={run} disabled={loading} className="btn btn-ghost" style={{ fontSize: 10 }}>
            {loading ? 'Calcul...' : 'Lancer le test'}
          </button>
        </div>
      </div>

      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', marginBottom: 14 }}>
        IsolationForest + LocalOutlierFactor + EllipticEnvelope · vote majoritaire sur un lot réel
        avec anomalies injectées.
      </p>

      {res ? (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              Consensus d'anomalie ({res.n_injected_anomalies}/{res.batch_size} injectées)
            </span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: cColor, fontWeight: 700 }}>{consensus}%</span>
          </div>
          <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', marginBottom: 14 }}>
            <div style={{ width: `${consensus}%`, height: '100%', background: cColor, transition: 'width 0.5s ease' }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {Object.entries(res.individual_scores || {}).map(([name, score]) => (
              <div key={name} style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '8px 10px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                  {name.replace(/_/g, ' ')}
                </div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--text)', fontWeight: 700, marginTop: 3 }}>
                  {score}%
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: res.votes?.[name] ? 'var(--red)' : 'var(--green)', marginTop: 2 }}>
                  {res.votes?.[name] ? 'anomalie' : 'normal'}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div style={{ padding: 24, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
          {loading ? 'Entraînement / calcul de l\'ensemble...' : 'Cliquez « Lancer le test » pour exécuter les 3 détecteurs.'}
        </div>
      )}
    </div>
  )
}

export default function IALab() {
  const [benchmark,    setBenchmark]    = useState(null)
  const [activeModels, setActiveModels] = useState({})
  const [tab,          setTab]          = useState('classification')
  const [reliabDataset, setReliabDataset] = useState('CWRU')
  const [shapDataset,  setShapDataset]  = useState('CWRU')
  const [shapData,     setShapData]     = useState(null)
  const [shapLoading,  setShapLoading]  = useState(false)
  const [calibDataset, setCalibDataset] = useState('CWRU')
  const [calibData,    setCalibData]    = useState(null)
  const [calibLoading, setCalibLoading] = useState(false)
  const [versDataset,  setVersDataset]  = useState('MF')
  const [versData,     setVersData]     = useState(null)
  const [versLoading,  setVersLoading]  = useState(false)
  const [versMsg,      setVersMsg]      = useState(null)

  useEffect(() => {
    endpoints.benchmark()
      .then(r => {
        setBenchmark(r.data)
        setActiveModels(r.data.active_models || {})
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (tab !== 'shap') return
    setShapLoading(true)
    endpoints.featureImportance(shapDataset)
      .then(r => {
        const raw = r.data
        // L'API retourne importances:[{feature, importance, pct}]
        // Le rendu attend features:[] et importances:[]
        const items = raw.importances || []
        setShapData({
          features    : items.map(x => x.feature),
          importances : items.map(x => x.importance),
          model_name  : raw.model,
          method      : raw.method,
          n_features  : raw.n_features,
          dataset     : raw.dataset,
        })
      })
      .catch(() => setShapData(null))
      .finally(() => setShapLoading(false))
  }, [tab, shapDataset])

  useEffect(() => {
    if (tab !== 'calibration') return
    setCalibLoading(true)
    endpoints.calibrationStats(calibDataset)
      .then(r => setCalibData(r.data))
      .catch(() => setCalibData(null))
      .finally(() => setCalibLoading(false))
  }, [tab, calibDataset])

  const loadVersions = (ds) => {
    setVersLoading(true)
    endpoints.modelVersions(ds, 'MLP')
      .then(r => setVersData(r.data))
      .catch(() => setVersData(null))
      .finally(() => setVersLoading(false))
  }

  useEffect(() => {
    if (tab !== 'versions') return
    setVersMsg(null)
    loadVersions(versDataset)
  }, [tab, versDataset])

  const handleRollback = (version) => {
    setVersMsg(null)
    endpoints.modelRollback(versDataset, 'MLP', version)
      .then(() => { setVersMsg(`✓ Rollback vers la version ${version} effectué`); loadVersions(versDataset) })
      .catch(e => setVersMsg(e.response?.data?.detail || 'Rollback échoué (droits admin requis ?)'))
  }

  const handleSelectModel = (dataset, model) => {
    endpoints.selectModel(dataset, model)
      .then(() => {
        setActiveModels(prev => ({ ...prev, [dataset]: model }))
      })
      .catch(() => {})
  }

  // Préparer les données pour le graphique
  const classifData = (() => {
    const raw = benchmark?.classification
    if (!raw || !raw['Modèle']) return []
    return Object.keys(raw['Modèle']).map(k => ({
      'Modèle'      : raw['Modèle'][k],
      'Dataset'     : raw['Dataset']?.[k],
      'Accuracy (%)': raw['Accuracy (%)']?.[k],
      'F1-score'    : raw['F1-score']?.[k],
      'Inférence (ms)': raw['Inférence (ms)']?.[k],
    }))
  })()

  const regressData = (() => {
    const raw = benchmark?.regression
    if (!raw || !raw['Modèle']) return []
    return Object.keys(raw['Modèle']).map(k => ({
      'Modèle'       : raw['Modèle'][k],
      'Dataset'      : raw['Dataset']?.[k],
      'MAE (cycles)' : raw['MAE (cycles)']?.[k],
      'RMSE (cycles)': raw['RMSE (cycles)']?.[k],
      'R²'           : raw['R²']?.[k],
      'Score NASA'   : raw['Score NASA']?.[k],
    }))
  })()

  // Données pour le graphique barres accuracy
  const accByModel = ['Decision Tree', 'Random Forest', 'XGBoost', 'MLP']
    .map(model => ({
      model,
      VBL  : classifData.find(r =>
        r['Modèle'] === model && r['Dataset'] === 'VBL-VA001'
      )?.[`Accuracy (%)`] || 0,
      CWRU : classifData.find(r =>
        r['Modèle'] === model && r['Dataset'] === 'CWRU'
      )?.[`Accuracy (%)`] || 0,
      MF   : classifData.find(r =>
        r['Modèle'] === model && r['Dataset'] === 'Mechanical Faults'
      )?.[`Accuracy (%)`] || 0,
    }))

  const datasets = {
    VBL : ['Decision Tree', 'Random Forest', 'XGBoost', 'MLP'],
    CWRU: ['Decision Tree', 'Random Forest', 'XGBoost', 'MLP'],
    MF  : ['Decision Tree', 'Random Forest', 'XGBoost', 'MLP'],
    CMAPSS: ['Huber Regressor', 'Decision Tree',
             'Random Forest', 'XGBoost', 'MLP'],
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header */}
      <div>
        <h1 style={{
          fontFamily    : 'var(--font-display)',
          fontSize      : 22,
          color         : 'var(--text)',
          letterSpacing : '0.05em',
        }}>
          IA LAB — BENCHMARK
        </h1>
        <p style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 11,
          color      : 'var(--text-muted)',
          marginTop  : 4,
        }}>
          COMPARATIF DES 5 MODÈLES · SÉLECTION DU MODÈLE ACTIF
        </p>
      </div>

      {/* Sélecteurs de modèles actifs */}
      <div style={{
        display             : 'grid',
        gridTemplateColumns : 'repeat(2, 1fr)',
        gap                 : 12,
      }}>
        {Object.entries(datasets).map(([ds, models]) => (
          <ModelSelectorCard
            key         = {ds}
            dataset     = {ds}
            models      = {models}
            activeModel = {activeModels[ds]}
            onSelect    = {handleSelectModel}
          />
        ))}
      </div>

      {/* Onglets */}
      <div style={{
        display : 'flex',
        gap     : 8,
        borderBottom: '1px solid var(--border)',
        paddingBottom: 0,
      }}>
        {[
          { id: 'classification', label: 'Classification Défauts' },
          { id: 'regression',     label: 'Régression RUL' },
          { id: 'fiabilite',      label: 'Fiabilité & Drift' },
          { id: 'shap',           label: 'Explainabilité SHAP' },
          { id: 'calibration',    label: 'Calibration' },
          { id: 'versions',       label: 'Versions Modèle' },
        ].map(({ id, label }) => (
          <button
            key     = {id}
            onClick = {() => setTab(id)}
            style   = {{
              padding      : '8px 16px',
              background   : 'transparent',
              border       : 'none',
              borderBottom : tab === id
                ? `2px solid ${id === 'fiabilite' ? 'var(--amber)' : id === 'calibration' ? 'var(--green)' : 'var(--cyan)'}`
                : '2px solid transparent',
              color        : tab === id
                ? id === 'fiabilite' ? 'var(--amber)' : id === 'calibration' ? 'var(--green)' : 'var(--cyan)'
                : 'var(--text-muted)',
              fontFamily   : 'var(--font-display)',
              fontSize     : 11,
              letterSpacing: '0.08em',
              cursor       : 'pointer',
              textTransform: 'uppercase',
              transition   : 'all 0.2s',
              marginBottom : -1,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'classification' && (
        <>
          {/* Graphique accuracy */}
          <div className="card">
            <h3 style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 11,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
              marginBottom  : 16,
            }}>
              ACCURACY PAR MODÈLE ET DATASET
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data   = {accByModel}
                margin = {{ top: 0, right: 0, bottom: 0, left: -10 }}
              >
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey  = "model"
                  tick     = {{
                    fontSize   : 10,
                    fontFamily : 'var(--font-mono)',
                    fill       : 'var(--text-muted)',
                  }}
                  tickLine = {false}
                />
                <YAxis
                  domain = {[0, 110]}
                  tick   = {{
                    fontSize   : 9,
                    fontFamily : 'var(--font-mono)',
                    fill       : 'var(--text-muted)',
                  }}
                  tickLine = {false}
                />
                <Tooltip
                  contentStyle = {{
                    background   : 'var(--bg-elevated)',
                    border       : '1px solid var(--border)',
                    borderRadius : 'var(--radius)',
                    fontFamily   : 'var(--font-mono)',
                    fontSize     : 11,
                  }}
                />
                <Bar dataKey="VBL"  name="VBL-VA001"  fill="#00D4FF" radius={[3,3,0,0]} />
                <Bar dataKey="CWRU" name="CWRU"        fill="#00FF9F" radius={[3,3,0,0]} />
                <Bar dataKey="MF"   name="Mech. Faults" fill="#FFB800" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Tableau */}
          <div className="card">
            <h3 style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 11,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
              marginBottom  : 16,
            }}>
              TABLEAU DÉTAILLÉ — CLASSIFICATION
            </h3>
            <BenchmarkTable data={classifData} type="classification" />
          </div>
        </>
      )}

      {tab === 'fiabilite' && (
        <>
          {/* Sélecteur de dataset */}
          <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
            {['VBL', 'CWRU', 'MF', 'CMAPSS'].map(ds => (
              <button
                key     = {ds}
                onClick = {() => setReliabDataset(ds)}
                style   = {{
                  padding    : '5px 14px',
                  borderRadius: 20,
                  border     : '1px solid',
                  borderColor: reliabDataset === ds ? 'var(--amber)' : 'var(--border)',
                  background : reliabDataset === ds ? 'rgba(255,184,0,0.1)' : 'transparent',
                  color      : reliabDataset === ds ? 'var(--amber)' : 'var(--text-muted)',
                  fontFamily : 'var(--font-mono)',
                  fontSize   : 10,
                  cursor     : 'pointer',
                  transition : 'all 0.2s',
                }}
              >
                {ds}
              </button>
            ))}
          </div>

          {/* Panel fiabilité */}
          <ModelReliabilityPanel dataset={reliabDataset} />

          {/* Ensemble d'anomalie (3 algos) */}
          <EnsembleAnomalyCard />

          {/* Panneau pour les 4 datasets en grille */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:12 }}>
            {['VBL', 'CWRU', 'MF', 'CMAPSS'].map(ds => (
              <ModelReliabilityPanel key={ds} dataset={ds} />
            ))}
          </div>
        </>
      )}

      {tab === 'shap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Sélecteur dataset */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              DATASET :
            </span>
            {['VBL', 'CWRU', 'MF', 'CMAPSS'].map(ds => (
              <button
                key={ds}
                onClick={() => setShapDataset(ds)}
                style={{
                  padding: '4px 12px', borderRadius: 20,
                  border: `1px solid ${shapDataset === ds ? 'var(--cyan)' : 'var(--border)'}`,
                  background: shapDataset === ds ? 'rgba(0,212,255,0.1)' : 'transparent',
                  color: shapDataset === ds ? 'var(--cyan)' : 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer',
                }}
              >
                {ds}
              </button>
            ))}
          </div>

          {/* Graphique importance */}
          <div className="card">
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 16 }}>
              IMPORTANCE DES FEATURES — {shapDataset} (SHAP / Random Forest)
            </h3>
            {shapLoading ? (
              <div style={{ textAlign: 'center', padding: 32, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                Chargement SHAP...
              </div>
            ) : shapData?.features?.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={Math.max(200, shapData.features.length * 28)}>
                  <BarChart
                    data={shapData.features.map((f, i) => ({ name: f, value: shapData.importances?.[i] ?? 0 }))}
                    layout="vertical"
                    margin={{ top: 0, right: 20, bottom: 0, left: 110 }}
                  >
                    <CartesianGrid stroke="var(--border)" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }}
                      tickLine={false}
                      domain={[0, 'auto']}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 10, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }}
                      tickLine={false}
                      width={105}
                    />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                      formatter={(v) => [v?.toFixed(4), 'Importance']}
                    />
                    <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                      {(shapData.features || []).map((_, i) => (
                        <Cell
                          key={i}
                          fill={i === 0 ? 'var(--cyan)' : i === 1 ? 'var(--green)' : i < 5 ? 'var(--amber)' : 'var(--border)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                  Modèle : {shapData.model_name} · {shapData.features.length} features · méthode : {shapData.method || 'feature_importances'}
                </div>
              </>
            ) : (
              <div style={{ padding: 32, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                {shapData === null
                  ? 'Modèle non chargé pour ce dataset — lancez une prédiction d\'abord'
                  : 'Aucune donnée d\'importance disponible pour ce dataset'}
              </div>
            )}
          </div>

          {/* Table des top features */}
          {shapData?.features?.length > 0 && (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    {['Rang', 'Feature', 'Importance', 'Part relative'].map(h => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontFamily: 'var(--font-display)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shapData.features.slice(0, 15).map((f, i) => {
                    const val    = shapData.importances?.[i] ?? 0
                    const total  = shapData.importances?.reduce((s, v) => s + v, 0) || 1
                    const pct    = ((val / total) * 100).toFixed(1)
                    const color  = i === 0 ? 'var(--cyan)' : i < 3 ? 'var(--green)' : 'var(--text-primary)'
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '7px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>#{i + 1}</td>
                        <td style={{ padding: '7px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{f}</td>
                        <td style={{ padding: '7px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{val.toFixed(4)}</td>
                        <td style={{ padding: '7px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 80, height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', background: color }} />
                            </div>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>{pct}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'calibration' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Dataset selector */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>DATASET :</span>
            {['VBL', 'CWRU', 'MF', 'CMAPSS'].map(ds => (
              <button
                key={ds}
                onClick={() => setCalibDataset(ds)}
                style={{
                  padding: '4px 12px', borderRadius: 20,
                  border: `1px solid ${calibDataset === ds ? 'var(--green)' : 'var(--border)'}`,
                  background: calibDataset === ds ? 'rgba(0,255,159,0.1)' : 'transparent',
                  color: calibDataset === ds ? 'var(--green)' : 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer',
                }}
              >{ds}</button>
            ))}
          </div>

          {calibLoading ? (
            <div style={{ padding: 40, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              Calcul calibration...
            </div>
          ) : calibData ? (
            <>
              {/* Métriques résumé */}
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {[
                  { label: 'MODÈLE ACTIF',      value: calibData.model_name || calibData.model, color: 'var(--cyan)'  },
                  { label: 'CONFIANCE MOYENNE',  value: `${(calibData.mean_confidence * 100).toFixed(1)}%`, color: 'var(--cyan)'  },
                  { label: 'ECE ESTIMÉ',         value: calibData.ece_estimated?.toFixed(4),     color: calibData.well_calibrated ? 'var(--green)' : 'var(--amber)' },
                  { label: 'CALIBRATION',        value: calibData.well_calibrated ? 'BONNE' : 'À AMÉLIORER', color: calibData.well_calibrated ? 'var(--green)' : 'var(--amber)' },
                  { label: '> 90% CONFIANCE',    value: `${calibData.pct_high_conf}%`, color: 'var(--green)' },
                  { label: '< 60% CONFIANCE',    value: `${calibData.pct_low_conf}%`,  color: 'var(--red)'   },
                ].map(({ label, value, color }) => (
                  <div key={label} className="card" style={{ flex: 1, minWidth: 120 }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color }}>{value ?? '—'}</div>
                  </div>
                ))}
              </div>

              {/* Reliability diagram */}
              {calibData.reliability?.length > 0 && (
                <div className="card">
                  <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 4 }}>
                    DIAGRAMME DE FIABILITÉ — {calibData.dataset}
                  </h3>
                  <p style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', marginBottom: 16 }}>
                    Calibration parfaite = droite diagonale · Modèle au-dessus = sous-confiant · En-dessous = surconfiant
                  </p>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                      <CartesianGrid stroke="var(--border)" />
                      <XAxis
                        type="number" dataKey="confidence" domain={[0, 1]} name="Confiance prédite"
                        tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }}
                        tickLine={false} label={{ value: 'Confiance prédite', position: 'insideBottom', offset: -10, fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                      />
                      <YAxis
                        type="number" domain={[0, 1]} name="Précision réelle"
                        tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }}
                        tickLine={false} label={{ value: 'Précision réelle', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                      />
                      <Tooltip
                        contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', fontFamily: 'var(--font-mono)', fontSize: 10 }}
                        formatter={(v, name) => [v?.toFixed(3), name]}
                      />
                      {/* Ligne de calibration parfaite */}
                      <Line
                        data={[{ confidence: 0, accuracy: 0 }, { confidence: 1, accuracy: 1 }]}
                        dataKey="accuracy" name="Calibration parfaite"
                        stroke="var(--border)" strokeDasharray="4 4" strokeWidth={1} dot={false}
                      />
                      {/* Courbe du modèle */}
                      <Line
                        data={calibData.reliability}
                        dataKey="accuracy" name="Modèle"
                        stroke="var(--green)" strokeWidth={2} dot={{ r: 4, fill: 'var(--green)', strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Distribution de confiance */}
              {calibData.distribution?.length > 0 && (
                <div className="card">
                  <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 16 }}>
                    DISTRIBUTION DES SCORES DE CONFIANCE — {calibData.n_samples} échantillons
                  </h3>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={calibData.distribution} margin={{ top: 0, right: 10, bottom: 0, left: -10 }}>
                      <CartesianGrid stroke="var(--border)" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }} tickLine={false} tickFormatter={v => `${v}%`} />
                      <Tooltip
                        contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', fontFamily: 'var(--font-mono)', fontSize: 10 }}
                        formatter={(v) => [`${v}%`, '% prédictions']}
                      />
                      <Bar dataKey="pct" name="% prédictions" radius={[3, 3, 0, 0]}>
                        {calibData.distribution.map((d, i) => (
                          <Cell
                            key={i}
                            fill={d.bin_low >= 0.9 ? 'var(--green)' : d.bin_low >= 0.6 ? 'var(--cyan)' : 'var(--amber)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', display: 'flex', gap: 16 }}>
                    <span style={{ color: 'var(--green)' }}>■ Haute confiance (&gt;0.9)</span>
                    <span style={{ color: 'var(--cyan)' }}>■ Moyenne (0.6–0.9)</span>
                    <span style={{ color: 'var(--amber)' }}>■ Faible (&lt;0.6)</span>
                  </div>
                </div>
              )}

              {/* Note méthodologique */}
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--radius)',
                border: '1px solid rgba(0,255,159,0.2)', background: 'rgba(0,255,159,0.04)',
                fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', lineHeight: 1.8,
              }}>
                ECE (Expected Calibration Error) — une valeur &lt; 0.05 indique un modèle bien calibré (ISO 13373)<br />
                La calibration isotonique (sklearn) est disponible via POST /api/retrain/start<br />
                Données : {calibData.n_samples} échantillons · Modèle : {calibData.model}
              </div>
            </>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              Modèle non disponible pour ce dataset — lancez d'abord une prédiction
            </div>
          )}
        </div>
      )}

      {tab === 'regression' && (
        <>
          {/* Graphique MAE */}
          <div className="card">
            <h3 style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 11,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
              marginBottom  : 16,
            }}>
              MAE RUL PAR MODÈLE (CMAPSS FD001)
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data   = {regressData}
                margin = {{ top: 0, right: 0, bottom: 0, left: -10 }}
              >
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey  = "Modèle"
                  tick     = {{
                    fontSize   : 10,
                    fontFamily : 'var(--font-mono)',
                    fill       : 'var(--text-muted)',
                  }}
                  tickLine = {false}
                />
                <YAxis
                  tick = {{
                    fontSize   : 9,
                    fontFamily : 'var(--font-mono)',
                    fill       : 'var(--text-muted)',
                  }}
                  tickLine = {false}
                />
                <Tooltip
                  contentStyle = {{
                    background   : 'var(--bg-elevated)',
                    border       : '1px solid var(--border)',
                    borderRadius : 'var(--radius)',
                    fontFamily   : 'var(--font-mono)',
                    fontSize     : 11,
                  }}
                />
                {regressData.map((entry, i) => null)}
                <Bar dataKey="MAE (cycles)" name="MAE (cycles)" radius={[3,3,0,0]}>
                  {regressData.map((entry, i) => (
                    <Cell
                      key  = {i}
                      fill = {MODEL_COLORS[entry['Modèle']] || 'var(--cyan)'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Tableau */}
          <div className="card">
            <h3 style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 11,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
              marginBottom  : 16,
            }}>
              TABLEAU DÉTAILLÉ — RÉGRESSION RUL
            </h3>
            <BenchmarkTable data={regressData} type="regression" />
          </div>
        </>
      )}

      {tab === 'versions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              DATASET (modèle MLP) :
            </span>
            {['MF', 'CWRU', 'VBL'].map(ds => (
              <button
                key={ds}
                onClick={() => setVersDataset(ds)}
                style={{
                  padding: '4px 12px', borderRadius: 20,
                  border: `1px solid ${versDataset === ds ? 'var(--cyan)' : 'var(--border)'}`,
                  background: versDataset === ds ? 'rgba(0,212,255,0.1)' : 'transparent',
                  color: versDataset === ds ? 'var(--cyan)' : 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer',
                }}
              >{ds}</button>
            ))}
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', margin: 0 }}>
                VERSIONS DU MODÈLE — {versDataset} / MLP
              </h3>
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', marginTop: 4 }}>
                Chaque réentraînement crée une version. Rollback = réactiver une version antérieure (admin).
              </p>
            </div>

            {versMsg && (
              <div style={{
                padding: '8px 16px', fontFamily: 'var(--font-mono)', fontSize: 10,
                color: versMsg.startsWith('✓') ? 'var(--green)' : 'var(--red)',
                borderBottom: '1px solid var(--border)',
              }}>{versMsg}</div>
            )}

            {versLoading ? (
              <div style={{ padding: 32, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                Chargement des versions...
              </div>
            ) : versData?.versions?.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    {['Version', 'Date', 'Accuracy', 'Classes', 'Déclencheur', 'Statut', 'Action'].map(h => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontFamily: 'var(--font-display)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {versData.versions.map((v) => (
                    <tr key={v.version} style={{
                      borderBottom: '1px solid var(--border)',
                      background: v.is_active ? 'rgba(0,255,159,0.06)' : 'transparent',
                    }}>
                      <td style={{ padding: '9px 16px', fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--cyan)', fontWeight: 700 }}>v{v.version}</td>
                      <td style={{ padding: '9px 16px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                        {v.trained_at ? new Date(v.trained_at).toLocaleString('fr-FR') : '—'}
                      </td>
                      <td style={{ padding: '9px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text)' }}>
                        {v.accuracy != null ? `${(v.accuracy * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ padding: '9px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{v.n_classes ?? '—'}</td>
                      <td style={{ padding: '9px 16px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>{v.triggered_by || '—'}</td>
                      <td style={{ padding: '9px 16px' }}>
                        {v.is_active ? (
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--green)', border: '1px solid var(--green)', borderRadius: 10, padding: '2px 8px' }}>
                            ● ACTIVE
                          </span>
                        ) : (
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>inactive</span>
                        )}
                      </td>
                      <td style={{ padding: '9px 16px' }}>
                        {!v.is_active && (
                          <button
                            onClick={() => handleRollback(v.version)}
                            style={{
                              fontFamily: 'var(--font-mono)', fontSize: 10, cursor: 'pointer',
                              padding: '4px 10px', borderRadius: 'var(--radius)',
                              border: '1px solid var(--amber)', background: 'transparent', color: 'var(--amber)',
                            }}
                          >Rollback</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ padding: 32, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                Aucune version enregistrée — lancez un réentraînement (page Maintenance) pour créer la version 1.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}