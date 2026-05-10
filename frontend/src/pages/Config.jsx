import { useState, useEffect, useRef } from 'react'
import {
  Settings, Save, RotateCcw, Bell,
  Sliders, Cpu, Mail, ChevronDown, ChevronUp,
  Upload, Database, RefreshCw, FileCode
} from 'lucide-react'
import { endpoints, api } from '../api/client'

function Section({ title, icon: Icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width          : '100%',
          display        : 'flex',
          alignItems     : 'center',
          justifyContent : 'space-between',
          background     : 'none',
          border         : 'none',
          cursor         : 'pointer',
          padding        : 0,
          marginBottom   : open ? 16 : 0,
        }}
      >
        <div style={{
          display    : 'flex',
          alignItems : 'center',
          gap        : 10,
        }}>
          <Icon size={16} color="var(--cyan)" />
          <span style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 12,
            color         : 'var(--cyan)',
            letterSpacing : '0.08em',
          }}>
            {title}
          </span>
        </div>
        {open
          ? <ChevronUp   size={14} color="var(--text-muted)" />
          : <ChevronDown size={14} color="var(--text-muted)" />
        }
      </button>
      {open && children}
    </div>
  )
}

function Field({ label, value, onChange, type = 'number',
                  unit, min, max, step = 0.1, hint }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        display        : 'flex',
        justifyContent : 'space-between',
        alignItems     : 'baseline',
        marginBottom   : 6,
      }}>
        <label style={{
          fontFamily  : 'var(--font-mono)',
          fontSize    : 11,
          color       : 'var(--text-muted)',
          letterSpacing: '0.05em',
        }}>
          {label}
        </label>
        {unit && (
          <span style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-dim)',
          }}>
            {unit}
          </span>
        )}
      </div>
      <input
        type     = {type}
        value    = {value}
        onChange = {e => onChange(
          type === 'number' ? parseFloat(e.target.value) : e.target.value
        )}
        min      = {min}
        max      = {max}
        step     = {step}
        style    = {{
          width        : '100%',
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
        onFocus = {e => e.target.style.borderColor = 'var(--cyan)'}
        onBlur  = {e => e.target.style.borderColor = 'var(--border)'}
      />
      {hint && (
        <div style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 9,
          color      : 'var(--text-dim)',
          marginTop  : 4,
        }}>
          {hint}
        </div>
      )}
    </div>
  )
}

// ── Nouveau composant : Upload Dataset ────────────────────────────────────
function DatasetUploadSection() {
  const [file,      setFile]      = useState(null)
  const [preview,   setPreview]   = useState(null)
  const [yamlConf,  setYamlConf]  = useState({
    name            : '',
    sampling_rate   : 12800,
    signal_columns  : '',
    label_column    : '',
    n_sensors       : 3,
    task            : 'classification',
    label_from_folder: false,
  })
  const [yamlGenerated, setYamlGenerated] = useState(null)
  const [loading,   setLoading]   = useState(false)
  const fileRef = useRef(null)

  const handleFileChange = async (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setPreview(null)
    setYamlGenerated(null)

    // Upload et aperçu
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', f)
      const r = await api.post('/dataset/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setPreview(r.data)

      // Pré-remplir le YAML depuis l'aperçu
      if (r.data.columns) {
        setYamlConf(prev => ({
          ...prev,
          name           : f.name.replace(/\.[^.]+$/, ''),
          signal_columns : r.data.columns
            .filter(c => !['label','class','fault'].includes(c.toLowerCase()))
            .slice(0, 8)
            .join(', '),
          label_column   : r.data.columns.find(
            c => ['label','class','fault','condition'].includes(c.toLowerCase())
          ) || '',
          n_sensors      : Math.min(
            r.data.columns?.length || 3, 8
          ),
        }))
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const generateYaml = async () => {
  if (!file) return
  setLoading(true)
  try {
    const cols = yamlConf.signal_columns
      .split(',').map(c => c.trim()).filter(Boolean)

    // Parser le mapping ligne par ligne
    const labelMapping = {}
    if (yamlConf.label_mapping) {
      yamlConf.label_mapping.split('\n').forEach(line => {
        const parts = line.split(':')
        if (parts.length === 2) {
          const key = parts[0].trim()
          const val = parts[1].trim()
          if (key && val) labelMapping[key] = val
        }
      })
    }

    const r = await api.post(
      `/dataset/configure?filename=${encodeURIComponent(file.name)}`,
      {
        name             : yamlConf.name,
        sampling_rate    : yamlConf.sampling_rate,
        signal_columns   : cols,
        label_column     : yamlConf.label_column || null,
        label_from_folder: yamlConf.label_from_folder,
        task             : yamlConf.task,
        label_mapping    : labelMapping,
      }
    )
    setYamlGenerated(r.data)
  } catch (e) {
    console.error(e)
  } finally {
    setLoading(false)
  }
}

  return (
    <div>
      {/* Zone de dépôt de fichier */}
      <div
        onClick = {() => fileRef.current?.click()}
        style   = {{
          border        : `2px dashed ${file ? 'var(--cyan)' : 'var(--border)'}`,
          borderRadius  : 'var(--radius-lg)',
          padding       : '24px',
          textAlign     : 'center',
          cursor        : 'pointer',
          background    : file ? 'var(--cyan-dim)' : 'transparent',
          transition    : 'all 0.2s',
          marginBottom  : 16,
        }}
      >
        <Upload size={24} color={file ? 'var(--cyan)' : 'var(--text-muted)'}
          style={{ margin: '0 auto 8px' }} />
        <div style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 12,
          color      : file ? 'var(--cyan)' : 'var(--text-muted)',
        }}>
          {file ? file.name : 'Cliquer pour importer (CSV, MAT, ZIP, NPY, TXT)'}
        </div>
        {file && preview && (
          <div style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
            marginTop  : 4,
          }}>
            {preview.columns?.length
              ? `${preview.columns.length} colonnes détectées`
              : preview.shape
              ? `Shape : ${preview.shape.join(' × ')}`
              : `${preview.n_files || 0} fichiers`}
          </div>
        )}
        <input
          ref      = {fileRef}
          type     = "file"
          accept   = ".csv,.mat,.zip,.npy,.txt"
          onChange = {handleFileChange}
          style    = {{ display: 'none' }}
        />
      </div>

      {/* Aperçu colonnes */}
      {preview?.columns && (
        <div style={{
          background   : 'var(--bg-elevated)',
          border       : '1px solid var(--border)',
          borderRadius : 'var(--radius)',
          padding      : '10px 14px',
          marginBottom : 16,
          fontFamily   : 'var(--font-mono)',
          fontSize     : 10,
        }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: 6 }}>
            COLONNES DÉTECTÉES
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {preview.columns.map(c => (
              <span key={c} style={{
                padding      : '2px 7px',
                borderRadius : 10,
                background   : 'var(--cyan-dim)',
                color        : 'var(--cyan)',
                border       : '1px solid var(--cyan)',
              }}>
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Configuration YAML */}
      {file && (
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(2, 1fr)',
          gap                 : 12,
          marginBottom        : 16,
        }}>
          <Field
            label    = "Nom du dataset"
            value    = {yamlConf.name}
            onChange = {v => setYamlConf(p => ({ ...p, name: v }))}
            type     = "text"
          />
          <Field
            label    = "Fréq. d'échantillonnage"
            value    = {yamlConf.sampling_rate}
            onChange = {v => setYamlConf(p => ({ ...p, sampling_rate: v }))}
            unit     = "Hz"
            min      = {100} max={200000} step={100}
          />
          <Field
            label    = "Nombre de capteurs"
            value    = {yamlConf.n_sensors}
            onChange = {v => setYamlConf(p => ({
              ...p, n_sensors: Math.round(v)
            }))}
            unit     = "canaux"
            min      = {1} max={32} step={1}
            hint     = "Nombre de colonnes de signal"
          />
          <div>
            <div className="metric-label" style={{ marginBottom: 6 }}>
              Tâche
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {['classification', 'regression'].map(t => (
                <button
                  key     = {t}
                  onClick = {() => setYamlConf(p => ({ ...p, task: t }))}
                  style   = {{
                    flex         : 1,
                    padding      : '7px',
                    borderRadius : 'var(--radius)',
                    border       : '1px solid',
                    borderColor  : yamlConf.task === t
                      ? 'var(--cyan)' : 'var(--border)',
                    background   : yamlConf.task === t
                      ? 'var(--cyan-dim)' : 'transparent',
                    color        : yamlConf.task === t
                      ? 'var(--cyan)' : 'var(--text-muted)',
                    fontFamily   : 'var(--font-mono)',
                    fontSize     : 10,
                    cursor       : 'pointer',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="metric-label" style={{ marginBottom: 6 }}>
              Colonnes signal (séparées par virgule)
            </div>
            <input
              value     = {yamlConf.signal_columns}
              onChange  = {e => setYamlConf(p => ({
                ...p, signal_columns: e.target.value
              }))}
              placeholder = "x, y, z  ou  acc_1, acc_2, acc_3"
              style     = {{
                width        : '100%',
                background   : 'var(--bg-elevated)',
                border       : '1px solid var(--border)',
                borderRadius : 'var(--radius)',
                color        : 'var(--text)',
                padding      : '8px 12px',
                fontFamily   : 'var(--font-mono)',
                fontSize     : 11,
                outline      : 'none',
              }}
            />
          </div>
          <Field
            label    = "Colonne label (optionnel)"
            value    = {yamlConf.label_column}
            onChange = {v => setYamlConf(p => ({ ...p, label_column: v }))}
            type     = "text"
            hint     = "Laisser vide si labels dans les noms de dossiers"
          />
          <div style={{
            display    : 'flex',
            alignItems : 'center',
            gap        : 8,
            marginTop  : 8,
          }}>
            <input
              type     = "checkbox"
              checked  = {yamlConf.label_from_folder}
              onChange = {e => setYamlConf(p => ({
                ...p, label_from_folder: e.target.checked
              }))}
              id       = "label-folder"
              style    = {{ accentColor: 'var(--cyan)' }}
            />
            <label htmlFor="label-folder" style={{
              fontFamily : 'var(--font-mono)',
              fontSize   : 10,
              color      : 'var(--text-muted)',
              cursor     : 'pointer',
            }}>
              Labels dans les noms de dossiers (VBL style)
            </label>
          </div>
          // Après la checkbox label_from_folder, ajoute :
<div style={{ gridColumn: '1 / -1', marginTop: 8 }}>
  <div className="metric-label" style={{ marginBottom: 6 }}>
    Mapping des labels (format: label_brut:label_affiche, un par ligne)
  </div>
  <textarea
    value     = {yamlConf.label_mapping || ''}
    onChange  = {e => setYamlConf(p => ({
      ...p, label_mapping: e.target.value
    }))}
    placeholder = {
      "normal:sain\n" +
      "bearing:roulement\n" +
      "misalignment:desalignement\n" +
      "unbalance:desequilibre"
    }
    style     = {{
      width        : '100%',
      height       : 90,
      background   : 'var(--bg-elevated)',
      border       : '1px solid var(--border)',
      borderRadius : 'var(--radius)',
      color        : 'var(--text)',
      padding      : '8px 10px',
      fontFamily   : 'var(--font-mono)',
      fontSize     : 10,
      resize       : 'vertical',
      outline      : 'none',
    }}
  />
  <div style={{
    fontFamily : 'var(--font-mono)',
    fontSize   : 9,
    color      : 'var(--text-dim)',
    marginTop  : 3,
  }}>
    Ex: "normal:sain" → le label "normal" dans vos données sera affiché "sain"
  </div>
</div>
        </div>
      )}

      {file && (
        <button
          className = "btn btn-primary"
          onClick   = {generateYaml}
          disabled  = {loading || !yamlConf.name}
        >
          <FileCode size={14}/>
          {loading ? 'Génération...' : 'Générer le fichier YAML'}
        </button>
      )}

      {/* YAML généré */}
      {yamlGenerated && (
        <div style={{ marginTop: 16 }}>
          <div style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 10,
            color         : 'var(--green)',
            letterSpacing : '0.1em',
            marginBottom  : 8,
          }}>
            ✓ YAML GÉNÉRÉ — {yamlGenerated.yaml_path}
          </div>
          <pre style={{
            background   : 'var(--bg-deep)',
            border       : '1px solid var(--border)',
            borderRadius : 'var(--radius)',
            padding      : '12px',
            fontFamily   : 'var(--font-mono)',
            fontSize     : 10,
            color        : 'var(--green)',
            overflow     : 'auto',
            maxHeight    : 200,
          }}>
            {JSON.stringify(yamlGenerated.config, null, 2)}
          </pre>
          <div style={{
            marginTop  : 10,
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : 'var(--text-muted)',
          }}>
            Le fichier YAML a été sauvegardé dans{' '}
            <span style={{ color: 'var(--cyan)' }}>
              configs/datasets/
            </span>
            . Vous pouvez maintenant utiliser ce dataset pour
            l'entraînement depuis la page Maintenance.
          </div>
        </div>
      )}
    </div>
  )
}

export default function Config() {
  const [config,  setConfig]  = useState(null)
  const [saved,   setSaved]   = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    endpoints.config()
      .then(r => setConfig(r.data))
      .catch(() => {})
  }, [])

  const update = (path, value) => {
    setConfig(prev => {
      const next = { ...prev }
      const keys = path.split('.')
      let ref = next
      for (let i = 0; i < keys.length - 1; i++) {
        ref[keys[i]] = { ...ref[keys[i]] }
        ref = ref[keys[i]]
      }
      ref[keys[keys.length - 1]] = value
      return next
    })
    setSaved(false)
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      await endpoints.updateConfig(config)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    try {
      const r = await endpoints.updateConfig({})
      const r2 = await endpoints.config()
      setConfig(r2.data)
      setSaved(false)
    } catch (e) {}
  }

  if (!config) return (
    <div style={{
      display        : 'flex',
      justifyContent : 'center',
      alignItems     : 'center',
      height         : '60vh',
      color          : 'var(--text-muted)',
      fontFamily     : 'var(--font-mono)',
    }}>
      Chargement de la configuration...
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>

      {/* Header */}
      <div style={{
        display        : 'flex',
        justifyContent : 'space-between',
        alignItems     : 'flex-end',
        marginBottom   : 24,
      }}>
        <div>
          <h1 style={{
            fontFamily    : 'var(--font-display)',
            fontSize      : 22,
            color         : 'var(--text)',
            letterSpacing : '0.05em',
          }}>
            CONFIGURATION
          </h1>
          <p style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 11,
            color      : 'var(--text-muted)',
            marginTop  : 4,
          }}>
            PARAMÈTRES GLOBAUX DE LA PLATEFORME
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={handleReset}>
            <RotateCcw size={14} />
            Réinitialiser
          </button>
          <button
            className = "btn btn-primary"
            onClick   = {handleSave}
            disabled  = {loading}
          >
            <Save size={14} />
            {saved ? '✓ Sauvegardé' : 'Appliquer'}
          </button>
        </div>
      </div>

      {/* 1. Seuils d'alerte Health Index */}
      <Section title="SEUILS D'ALERTE — HEALTH INDEX" icon={Sliders}>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(3, 1fr)',
          gap                 : 16,
        }}>
          <Field
            label    = "Seuil Vert → Jaune"
            value    = {config.alert_thresholds?.green}
            onChange = {v => update('alert_thresholds.green', v)}
            unit     = "%"
            min      = {0} max={100} step={1}
            hint     = "Au-dessus = machine saine (vert)"
          />
          <Field
            label    = "Seuil Jaune → Orange"
            value    = {config.alert_thresholds?.yellow}
            onChange = {v => update('alert_thresholds.yellow', v)}
            unit     = "%"
            min      = {0} max={100} step={1}
            hint     = "Au-dessus = surveillance (jaune)"
          />
          <Field
            label    = "Seuil Orange → Rouge"
            value    = {config.alert_thresholds?.orange}
            onChange = {v => update('alert_thresholds.orange', v)}
            unit     = "%"
            min      = {0} max={100} step={1}
            hint     = "En-dessous = critique (rouge)"
          />
        </div>

        {/* Visualisation des zones */}
        <div style={{
          marginTop    : 12,
          height       : 20,
          borderRadius : 10,
          overflow     : 'hidden',
          display      : 'flex',
        }}>
          {[
            { color: 'var(--red)',    pct: config.alert_thresholds?.orange || 20 },
            { color: 'var(--orange)', pct: (config.alert_thresholds?.yellow || 40) - (config.alert_thresholds?.orange || 20) },
            { color: 'var(--amber)',  pct: (config.alert_thresholds?.green  || 70) - (config.alert_thresholds?.yellow || 40) },
            { color: 'var(--green)',  pct: 100 - (config.alert_thresholds?.green || 70) },
          ].map((zone, i) => (
            <div key={i} style={{
              width      : `${zone.pct}%`,
              background : zone.color,
              opacity    : 0.7,
            }} />
          ))}
        </div>
        <div style={{
          display        : 'flex',
          justifyContent : 'space-between',
          fontFamily     : 'var(--font-mono)',
          fontSize       : 9,
          color          : 'var(--text-muted)',
          marginTop      : 4,
        }}>
          <span>0%</span>
          <span>{config.alert_thresholds?.orange}%</span>
          <span>{config.alert_thresholds?.yellow}%</span>
          <span>{config.alert_thresholds?.green}%</span>
          <span>100%</span>
        </div>
      </Section>

      {/* 2. Seuils Autoencoder */}
      <Section title="SEUILS AUTOENCODER PAR DATASET" icon={Cpu}>
        <p style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 10,
          color      : 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Ajuster pour réduire les faux positifs.
          Augmenter le seuil → moins de fausses alarmes,
          moins de sensibilité.
        </p>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(4, 1fr)',
          gap                 : 12,
        }}>
          {['VBL', 'CWRU', 'MF', 'CMAPSS'].map(ds => (
            <Field
              key      = {ds}
              label    = {ds}
              value    = {config.autoencoder_thresholds?.[ds] || 50}
              onChange = {v => update(`autoencoder_thresholds.${ds}`, v)}
              unit     = "%"
              min      = {10} max={90} step={5}
              hint     = {ds === 'CMAPSS' ? '19% FP → recommandé: 65%'
                         : ds === 'CWRU'  ? '11% FP → recommandé: 60%'
                         : 'Recommandé: 50%'}
            />
          ))}
        </div>
      </Section>

      {/* 3. Paramètres géométriques roulements */}
      <Section title="PARAMÈTRES GÉOMÉTRIQUES ROULEMENTS" icon={Settings}>
        <p style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 10,
          color      : 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Utilisés pour calculer BPFI, BPFO, BSF, FTF dans l'analyse spectrale.
        </p>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(3, 1fr)',
          gap                 : 16,
        }}>
          <Field
            label    = "Fréquence de rotation (f₀)"
            value    = {config.bearing_params?.shaft_freq}
            onChange = {v => update('bearing_params.shaft_freq', v)}
            unit     = "Hz"
            min      = {1} max={500} step={0.1}
            hint     = "Ex: 1238 RPM → 20.63 Hz"
          />
          <Field
            label    = "Nombre de billes"
            value    = {config.bearing_params?.n_balls}
            onChange = {v => update('bearing_params.n_balls', Math.round(v))}
            unit     = "billes"
            min      = {3} max={30} step={1}
          />
          <Field
            label    = "Diamètre bille"
            value    = {config.bearing_params?.ball_diam}
            onChange = {v => update('bearing_params.ball_diam', v)}
            unit     = "mm"
            min      = {1} max={50} step={0.01}
          />
          <Field
            label    = "Diamètre primitif"
            value    = {config.bearing_params?.pitch_diam}
            onChange = {v => update('bearing_params.pitch_diam', v)}
            unit     = "mm"
            min      = {10} max={500} step={0.1}
          />
          <Field
            label    = "Angle de contact"
            value    = {config.bearing_params?.contact_angle}
            onChange = {v => update('bearing_params.contact_angle', v)}
            unit     = "°"
            min      = {0} max={45} step={0.5}
          />
          <Field
            label    = "Fréq. d'échantillonnage cible"
            value    = {config.sampling_rate || 12800}
            onChange = {v => update('sampling_rate', v)}
            unit     = "Hz"
            min      = {1000} max={50000} step={100}
          />
        </div>

        {/* Calcul live des fréquences */}
        {config.bearing_params && (
          <div style={{
            marginTop    : 12,
            padding      : '12px 16px',
            background   : 'var(--bg-elevated)',
            borderRadius : 'var(--radius)',
            border       : '1px solid var(--border)',
          }}>
            <div style={{
              fontFamily    : 'var(--font-display)',
              fontSize      : 10,
              color         : 'var(--text-muted)',
              letterSpacing : '0.1em',
              marginBottom  : 8,
            }}>
              FRÉQUENCES CALCULÉES
            </div>
            <div style={{
              display             : 'grid',
              gridTemplateColumns : 'repeat(4, 1fr)',
              gap                 : 8,
            }}>
              {(() => {
                const p = config.bearing_params
                const f0 = p.shaft_freq || 20.6
                const n  = p.n_balls || 9
                const bd = p.ball_diam || 7.94
                const pd = p.pitch_diam || 38.5
                const phi = (p.contact_angle || 0) * Math.PI / 180
                const ratio = (bd / pd) * Math.cos(phi)
                const freqs = {
                  BPFO: (n/2) * f0 * (1 - ratio),
                  BPFI: (n/2) * f0 * (1 + ratio),
                  BSF : (pd/(2*bd)) * f0 * (1 - ratio**2),
                  FTF : (f0/2) * (1 - ratio),
                }
                return Object.entries(freqs).map(([name, val]) => (
                  <div key={name} style={{
                    textAlign  : 'center',
                    padding    : '8px',
                    background : 'var(--bg-card)',
                    borderRadius: 'var(--radius)',
                  }}>
                    <div style={{
                      fontFamily  : 'var(--font-mono)',
                      fontSize    : 10,
                      color       : 'var(--text-muted)',
                    }}>
                      {name}
                    </div>
                    <div style={{
                      fontFamily  : 'var(--font-display)',
                      fontSize    : 16,
                      color       : 'var(--cyan)',
                      fontWeight  : 700,
                    }}>
                      {val.toFixed(1)}
                    </div>
                    <div style={{
                      fontFamily : 'var(--font-mono)',
                      fontSize   : 9,
                      color      : 'var(--text-dim)',
                    }}>
                      Hz
                    </div>
                  </div>
                ))
              })()}
            </div>
          </div>
        )}
      </Section>

      {/* 4. Simulation */}
      <Section title="SIMULATION" icon={Settings} defaultOpen={false}>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : 'repeat(2, 1fr)',
          gap                 : 16,
        }}>
          <Field
            label    = "Vitesse de simulation"
            value    = {config.simulation_speed}
            onChange = {v => update('simulation_speed', v)}
            unit     = "s/cycle"
            min      = {0.05} max={5.0} step={0.05}
            hint     = "0.1s = très rapide, 2s = lent"
          />
          <Field
            label    = "Nombre de machines"
            value    = {config.n_machines}
            onChange = {v => update('n_machines', Math.round(v))}
            unit     = "machines"
            min      = {1} max={20} step={1}
          />
        </div>
      </Section>

      {/* 5. Notifications email */}
      <Section title="NOTIFICATIONS EMAIL" icon={Mail} defaultOpen={false}>
        <p style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 10,
          color      : 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Les alertes critiques seront envoyées à cette adresse
          lorsque le Health Index passe sous le seuil rouge.
        </p>
        <div style={{
          display             : 'grid',
          gridTemplateColumns : '1fr 1fr',
          gap                 : 16,
        }}>
          <Field
            label    = "Email destinataire"
            value    = {config.notifications?.email_address || ''}
            onChange = {v => update('notifications.email_address', v)}
            type     = "text"
            hint     = "Alertes critiques envoyées à cette adresse"
          />
          <Field
            label    = "Serveur SMTP"
            value    = {config.notifications?.smtp_server || 'smtp.gmail.com'}
            onChange = {v => update('notifications.smtp_server', v)}
            type     = "text"
          />
        </div>
        <div style={{
          display    : 'flex',
          alignItems : 'center',
          gap        : 10,
          marginTop  : 8,
        }}>
          <input
            type     = "checkbox"
            checked  = {config.notifications?.email_enabled || false}
            onChange = {e => update('notifications.email_enabled', e.target.checked)}
            id       = "email-enabled"
            style    = {{ accentColor: 'var(--cyan)' }}
          />
          <label
            htmlFor  = "email-enabled"
            style    = {{
              fontFamily : 'var(--font-mono)',
              fontSize   : 11,
              color      : 'var(--text-muted)',
              cursor     : 'pointer',
            }}
          >
            Activer les notifications email
          </label>
        </div>

        {/* Bouton test email */}
        {config.notifications?.email_enabled &&
         config.notifications?.email_address && (
          <button
            className = "btn btn-ghost"
            style     = {{ marginTop: 12 }}
            onClick   = {async () => {
              try {
                await fetch(
                  `/api/notifications/test?recipient=${encodeURIComponent(
                    config.notifications.email_address
                  )}`,
                  { method: 'POST' }
                )
                alert('Email de test envoyé !')
              } catch (e) {
                alert('Erreur SMTP — vérifiez la configuration.')
              }
            }}
          >
            <Bell size={14} />
            Envoyer email de test
          </button>
        )}
      </Section>
      <Section title="IMPORT DATASET & CONFIGURATION YAML" icon={Database}>
        <p style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 10,
          color      : 'var(--text-muted)',
          marginBottom: 16,
       }}>
          Importez vos propres données (CSV, MAT, ZIP, NPY) pour entraîner
          de nouveaux défauts. Le fichier YAML de configuration sera généré
          automatiquement.
        </p>
        <DatasetUploadSection />
      </Section>
    </div>
  )
}