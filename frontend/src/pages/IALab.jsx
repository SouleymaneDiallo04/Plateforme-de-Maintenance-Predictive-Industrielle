import { useState, useEffect } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
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

export default function IALab() {
  const [benchmark,    setBenchmark]    = useState(null)
  const [activeModels, setActiveModels] = useState({})
  const [tab,          setTab]          = useState('classification')

  useEffect(() => {
    endpoints.benchmark()
      .then(r => {
        setBenchmark(r.data)
        setActiveModels(r.data.active_models || {})
      })
      .catch(() => {})
  }, [])

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
        {['classification', 'regression'].map(t => (
          <button
            key     = {t}
            onClick = {() => setTab(t)}
            style   = {{
              padding      : '8px 16px',
              background   : 'transparent',
              border       : 'none',
              borderBottom : tab === t
                ? '2px solid var(--cyan)'
                : '2px solid transparent',
              color        : tab === t
                ? 'var(--cyan)'
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
            {t === 'classification'
              ? 'Classification Défauts'
              : 'Régression RUL'
            }
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
    </div>
  )
}