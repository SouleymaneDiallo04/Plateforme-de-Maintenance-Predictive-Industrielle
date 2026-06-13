import { useState, useEffect, useCallback, Fragment } from 'react'
import {
  Wrench, Bell, CheckCircle, Clock, AlertTriangle,
  Play, ShieldCheck, RefreshCw, X, User, Package
} from 'lucide-react'
import { endpoints, auth } from '../api/client'

// ── Constantes d'affichage ────────────────────────────────────────────────────
const PRIO_COLOR = { P1: 'var(--red)', P2: 'var(--amber)', P3: 'var(--cyan)' }
const STATUS_COLOR = {
  open: 'var(--amber)', assigned: 'var(--cyan)', in_progress: 'var(--cyan)',
  on_hold: 'var(--amber)', done: 'var(--green)', closed: 'var(--text-muted)',
}
const FIELD = {
  width: '100%', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius)', color: 'var(--text)', padding: '8px 10px',
  fontFamily: 'var(--font-mono)', fontSize: 11, outline: 'none', boxSizing: 'border-box',
}

function Prio({ p }) {
  return (
    <span style={{
      fontFamily: 'var(--font-display)', fontSize: 10, color: PRIO_COLOR[p] || 'var(--cyan)',
      border: `1px solid ${PRIO_COLOR[p] || 'var(--cyan)'}`, borderRadius: 8, padding: '2px 7px',
    }}>{p}</span>
  )
}

function Status({ s, label }) {
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: STATUS_COLOR[s] || 'var(--text)' }}>
      {(label || s || '').toUpperCase()}
    </span>
  )
}

// Disponibilité de la pièce de rechange au magasin
function PartBadge({ wo, compact }) {
  if (!wo.part_reference) {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>aucune pièce</span>
  }
  const ok = wo.part_in_stock
  const color = ok ? 'var(--green)' : 'var(--red)'
  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, lineHeight: 1.5 }}>
      <div style={{ color: 'var(--text)' }}>{wo.part_reference}</div>
      <div style={{ color }}>
        {ok ? `✓ en stock (${wo.part_stock_qty})` : '⛔ rupture — à commander'}
      </div>
      {!compact && ok && wo.part_location && (
        <div style={{ color: 'var(--text-dim)' }}>{wo.part_location}</div>
      )}
    </div>
  )
}

// ── Cloche de notifications (commune aux deux rôles) ──────────────────────────
function NotificationBell() {
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)

  const load = useCallback(() => {
    endpoints.notifications()
      .then(r => { setItems(r.data.notifications || []); setUnread(r.data.unread || 0) })
      .catch(() => {})
  }, [])

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t) }, [load])

  const markAll = () => endpoints.readAllNotifications().then(load).catch(() => {})

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} className="btn btn-ghost"
        style={{ position: 'relative', padding: '8px 10px' }}>
        <Bell size={15} />
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -4, background: 'var(--red)', color: '#fff',
            borderRadius: 10, fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
            padding: '1px 5px', minWidth: 16, textAlign: 'center',
          }}>{unread}</span>
        )}
      </button>
      {open && (
        <div style={{
          position: 'absolute', right: 0, top: 42, width: 320, maxHeight: 380, overflowY: 'auto',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', boxShadow: '0 8px 30px rgba(0,0,0,0.4)', zIndex: 50,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
              NOTIFICATIONS
            </span>
            <button onClick={markAll} style={{ background: 'none', border: 'none', color: 'var(--cyan)',
              fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer' }}>Tout marquer lu</button>
          </div>
          {items.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
              Aucune notification
            </div>
          ) : items.map(n => (
            <div key={n.id} style={{
              padding: '10px 12px', borderBottom: '1px solid var(--border)',
              background: n.lu ? 'transparent' : 'var(--cyan-dim)',
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text)', lineHeight: 1.5 }}>
                {n.message}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)', marginTop: 3 }}>
                {n.created_at?.slice(0, 16).replace('T', ' ')}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  VUE ADMIN — dispatch & supervision
// ══════════════════════════════════════════════════════════════════════════════
function CandidatePicker({ woId, onAssigned, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [assigning, setAssigning] = useState(null)

  useEffect(() => {
    endpoints.workOrderCandidates(woId)
      .then(r => setData(r.data)).catch(() => setData({ candidates: [] }))
      .finally(() => setLoading(false))
  }, [woId])

  const assign = (techId, qualified) => {
    if (!qualified && !window.confirm(
      'Ce technicien n’est pas pleinement qualifié pour cet ordre. Confirmer l’affectation ?')) return
    setAssigning(techId)
    endpoints.assignWorkOrder(woId, techId)
      .then(() => onAssigned()).catch(() => {}).finally(() => setAssigning(null))
  }

  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--cyan)',
      borderRadius: 'var(--radius)', padding: 12, margin: '4px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)' }}>
          {data ? <>Requis : <b>{data.competence_requise}</b> · certif. ≥ {data.certif_requise_label}</> : 'Chargement…'}
        </span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex' }}>
          <X size={14} />
        </button>
      </div>
      {loading ? (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', padding: 8 }}>Chargement des candidats…</div>
      ) : (data.candidates || []).length === 0 ? (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', padding: 8 }}>Aucun technicien disponible.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.candidates.map(c => (
            <div key={c.id} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px',
              borderRadius: 'var(--radius)', border: '1px solid var(--border)',
              background: 'var(--bg-card)',
            }}>
              <span style={{ fontSize: 13 }}>{c.qualified ? '✅' : c.has_comp ? '⚠️' : '⛔'}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text)' }}>
                  {c.name} <span style={{ color: 'var(--text-muted)', fontSize: 9 }}>· {c.certif_label}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                  {(c.competences || []).join(', ') || '—'} · {c.charge} OT · {c.statut}
                </div>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9,
                color: c.qualified ? 'var(--green)' : c.has_comp ? 'var(--amber)' : 'var(--red)' }}>
                {c.reason}
              </span>
              <button disabled={assigning === c.id} onClick={() => assign(c.id, c.qualified)}
                className="btn btn-primary" style={{ fontSize: 9, padding: '4px 10px' }}>
                {assigning === c.id ? '…' : 'Assigner'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StockPanel() {
  const [parts, setParts] = useState([])
  const load = useCallback(() => {
    endpoints.stock().then(r => setParts(r.data.parts || [])).catch(() => {})
  }, [])
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t) }, [load])

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
        <Package size={15} color="var(--cyan)" />
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', margin: 0 }}>
          MAGASIN — STOCK PIÈCES DE RECHANGE
        </h3>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
            {['Référence', 'Désignation', 'Catégorie', 'Stock', 'Emplacement', 'Coût u.'].map(h => (
              <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontFamily: 'var(--font-display)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parts.map(p => (
            <tr key={p.id} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-primary)' }}>{p.reference}</td>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>{p.designation}</td>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>{p.category}</td>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, color: p.in_stock ? 'var(--green)' : 'var(--red)' }}>
                {p.stock_qty}{!p.in_stock && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, marginLeft: 5 }}>RUPTURE</span>}
              </td>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>{p.location}</td>
              <td style={{ padding: '7px 14px', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)' }}>{p.unit_cost_eur != null ? `${p.unit_cost_eur} €` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AdminView() {
  const [wos, setWos] = useState([])
  const [techs, setTechs] = useState([])
  const [picker, setPicker] = useState(null)   // wo_id en cours d'affectation
  const [loading, setLoading] = useState(false)

  const reload = useCallback(() => {
    setLoading(true)
    Promise.all([endpoints.workOrders(), endpoints.technicians()])
      .then(([w, t]) => { setWos(w.data.work_orders || []); setTechs(t.data.technicians || []) })
      .catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [reload])

  const verify = (id) => endpoints.verifyWorkOrder(id).then(reload).catch(() => {})

  const active = wos.filter(w => w.status !== 'closed')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Tableau dispatch */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', margin: 0 }}>
              DISPATCH DES INTERVENTIONS
            </h3>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', marginTop: 4 }}>
              Affectation manuelle assistée par compétence (ISO 18436)
            </p>
          </div>
          <button onClick={reload} className="btn btn-ghost" style={{ fontSize: 10 }}>
            <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Actualiser
          </button>
        </div>

        {active.length === 0 ? (
          <div style={{ padding: 28, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            <CheckCircle size={28} color="var(--green)" style={{ margin: '0 auto 8px' }} />
            <div>Aucun ordre de travail actif — ils apparaissent sur alerte critique.</div>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                {['Prio', 'Machine', 'Élément défaillant', 'Pièce / Stock', 'Compétence', 'Statut', 'Technicien', 'Action'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontFamily: 'var(--font-display)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {active.map(w => (
                <Fragment key={w.id}>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top' }}><Prio p={w.priority} /></td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-primary)' }}>{w.machine_id}</td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text)', maxWidth: 280 }}>
                      {w.failing_element || (w.fault || '—').replace(/_/g, ' ')}
                      {w.iso_zone && <span style={{ color: 'var(--text-dim)' }}> · zone ISO {w.iso_zone}</span>}
                    </td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top' }}><PartBadge wo={w} compact /></td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                      {w.competence_requise || '—'}
                      {w.certif_requise_label && w.certif_requise_label !== '—' && <span style={{ color: 'var(--text-dim)' }}> · {w.certif_requise_label}</span>}
                    </td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top' }}><Status s={w.status} label={w.status_label} /></td>
                    <td style={{ padding: '8px 14px', verticalAlign: 'top', fontFamily: 'var(--font-mono)', fontSize: 10, color: w.assigned_to_name ? 'var(--cyan)' : 'var(--text-dim)' }}>
                      {w.assigned_to_name || '—'}
                    </td>
                    <td style={{ padding: '8px 14px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {(w.status === 'open') && (
                          <button onClick={() => setPicker(picker === w.id ? null : w.id)}
                            className="btn btn-primary" style={{ fontSize: 9, padding: '3px 9px' }}>
                            {picker === w.id ? 'Fermer' : 'Assigner'}
                          </button>
                        )}
                        {(w.status === 'assigned' || w.status === 'in_progress' || w.status === 'on_hold') && (
                          <button onClick={() => setPicker(picker === w.id ? null : w.id)}
                            className="btn btn-ghost" style={{ fontSize: 9, padding: '3px 9px' }}>
                            Réassigner
                          </button>
                        )}
                        {w.status === 'done' && (
                          <button onClick={() => verify(w.id)}
                            style={{ fontFamily: 'var(--font-mono)', fontSize: 9, cursor: 'pointer', padding: '3px 9px',
                              borderRadius: 'var(--radius)', border: '1px solid var(--green)', background: 'transparent', color: 'var(--green)' }}>
                            <ShieldCheck size={10} style={{ marginRight: 3, verticalAlign: 'middle' }} />Vérifier
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {picker === w.id && (
                    <tr>
                      <td colSpan={8} style={{ padding: '0 14px 8px' }}>
                        <CandidatePicker woId={w.id}
                          onAssigned={() => { setPicker(null); reload() }}
                          onClose={() => setPicker(null)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Équipe technique */}
      <div className="card">
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 14 }}>
          ÉQUIPE TECHNIQUE — COMPÉTENCES & CHARGE
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
          {techs.map(t => (
            <div key={t.id} style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <User size={14} color="var(--cyan)" />
                <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, color: 'var(--text)' }}>{t.name}</span>
                <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 9,
                  color: t.statut === 'disponible' ? 'var(--green)' : 'var(--amber)' }}>
                  {t.statut}
                </span>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', marginBottom: 6 }}>
                Certification : <span style={{ color: 'var(--cyan)' }}>{t.certif_label}</span> · {t.charge} OT actifs
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {(t.competences || []).map((c, i) => (
                  <span key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 8, padding: '2px 6px',
                    borderRadius: 8, border: '1px solid var(--border)', color: 'var(--text-muted)' }}>{c}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Magasin / stock */}
      <StockPanel />
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  VUE TECHNICIEN — mes interventions
// ══════════════════════════════════════════════════════════════════════════════
function MissionCard({ wo, onStart, onComplete }) {
  const [form, setForm] = useState(null)   // null = fermé ; objet = formulaire CRI ouvert
  const [saving, setSaving] = useState(false)
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const openForm = () => setForm({ cause_racine: '', actions: '', pieces: '', temps_passe_h: '', defaut_confirme: true, cost_euros: '' })

  const submit = async () => {
    setSaving(true)
    try {
      await onComplete(wo.id, {
        cause_racine: form.cause_racine,
        actions: form.actions,
        pieces: form.pieces ? form.pieces.split(',').map(s => s.trim()).filter(Boolean) : [],
        temps_passe_h: form.temps_passe_h ? parseFloat(form.temps_passe_h) : null,
        defaut_confirme: form.defaut_confirme,
        cost_euros: form.cost_euros ? parseFloat(form.cost_euros) : null,
      })
      setForm(null)
    } finally { setSaving(false) }
  }

  return (
    <div style={{ background: 'var(--bg-elevated)', border: `1px solid ${PRIO_COLOR[wo.priority] || 'var(--border)'}40`,
      borderLeft: `3px solid ${PRIO_COLOR[wo.priority] || 'var(--cyan)'}`, borderRadius: 'var(--radius)', padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Prio p={wo.priority} />
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--text)' }}>{wo.machine_id}</span>
        {wo.iso_zone && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>zone ISO {wo.iso_zone}</span>}
        <span style={{ marginLeft: 'auto' }}><Status s={wo.status} label={wo.status_label} /></span>
      </div>
      {/* Élément défaillant explicite */}
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--cyan)', lineHeight: 1.5, marginBottom: 8 }}>
        🔧 {wo.failing_element || (wo.fault || '').replace(/_/g, ' ')}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 8 }}>
        {wo.description}
      </div>
      {/* Pièce de rechange + stock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
        padding: '6px 10px', borderRadius: 'var(--radius)',
        background: wo.part_reference ? (wo.part_in_stock ? 'rgba(0,200,120,0.07)' : 'var(--red-dim)') : 'transparent',
        border: `1px solid ${wo.part_reference ? (wo.part_in_stock ? 'var(--green)' : 'var(--red)') : 'var(--border)'}40` }}>
        <Package size={13} color={wo.part_reference ? (wo.part_in_stock ? 'var(--green)' : 'var(--red)') : 'var(--text-muted)'} />
        <PartBadge wo={wo} />
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', marginBottom: 10 }}>
        Compétence : {wo.competence_requise || '—'}{wo.certif_requise_label && wo.certif_requise_label !== '—' ? ` · ${wo.certif_requise_label}` : ''}
      </div>

      {/* Actions selon statut — le compte-rendu est accessible dès qu'un OT est actif */}
      {!form && ['assigned', 'in_progress', 'on_hold'].includes(wo.status) && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {wo.status === 'assigned' && (
            <button onClick={() => onStart(wo.id)} className="btn btn-ghost" style={{ fontSize: 11 }}>
              <Play size={13} /> Démarrer
            </button>
          )}
          <button onClick={openForm} className="btn btn-primary" style={{ fontSize: 11 }}>
            <CheckCircle size={13} /> Terminer &amp; rédiger le compte-rendu
          </button>
        </div>
      )}

      {wo.status === 'done' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
          <Clock size={12} /> Terminé — en attente de vérification admin
        </div>
      )}

      {/* Formulaire compte-rendu (CRI) */}
      {form && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <div className="metric-label" style={{ marginBottom: 4 }}>Cause racine</div>
              <input style={FIELD} value={form.cause_racine} placeholder="Roulement bague ext. piqué"
                onChange={e => set('cause_racine', e.target.value)} />
            </div>
            <div>
              <div className="metric-label" style={{ marginBottom: 4 }}>Pièces remplacées (séparées par ,)</div>
              <input style={FIELD} value={form.pieces} placeholder="SKF 6205, joint"
                onChange={e => set('pieces', e.target.value)} />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <div className="metric-label" style={{ marginBottom: 4 }}>Actions réalisées</div>
              <input style={FIELD} value={form.actions} placeholder="Remplacement roulement + réalignement laser"
                onChange={e => set('actions', e.target.value)} />
            </div>
            <div>
              <div className="metric-label" style={{ marginBottom: 4 }}>Temps passé (h)</div>
              <input type="number" style={FIELD} value={form.temps_passe_h} placeholder="2.5"
                onChange={e => set('temps_passe_h', e.target.value)} />
            </div>
            <div>
              <div className="metric-label" style={{ marginBottom: 4 }}>Coût pièces (€)</div>
              <input type="number" style={FIELD} value={form.cost_euros} placeholder="120"
                onChange={e => set('cost_euros', e.target.value)} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="metric-label">Le défaut prédit était-il réel ?</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--green)' }}>
              <input type="radio" checked={form.defaut_confirme === true} onChange={() => set('defaut_confirme', true)} style={{ accentColor: 'var(--green)' }} /> Oui (vrai positif)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--amber)' }}>
              <input type="radio" checked={form.defaut_confirme === false} onChange={() => set('defaut_confirme', false)} style={{ accentColor: 'var(--amber)' }} /> Non (fausse alarme)
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={submit} disabled={saving} className="btn btn-primary" style={{ fontSize: 11 }}>
              {saving ? 'Enregistrement…' : 'Valider le compte-rendu'}
            </button>
            <button onClick={() => setForm(null)} className="btn btn-ghost" style={{ fontSize: 11 }}>Annuler</button>
          </div>
        </div>
      )}
    </div>
  )
}

function TechnicianView() {
  const [wos, setWos] = useState([])
  const [loading, setLoading] = useState(false)

  const reload = useCallback(() => {
    setLoading(true)
    endpoints.myWorkOrders()
      .then(r => setWos(r.data.work_orders || [])).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [reload])

  const start = (id) => endpoints.startWorkOrder(id).then(reload).catch(() => {})
  const complete = (id, data) => endpoints.completeWorkOrder(id, data).then(reload)

  const aFaire     = wos.filter(w => ['assigned', 'open'].includes(w.status))
  const enCours    = wos.filter(w => ['in_progress', 'on_hold'].includes(w.status))
  const historique = wos.filter(w => ['done', 'closed'].includes(w.status))

  const Section = ({ title, color, list, empty }) => (
    <div className="card">
      <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 11, color, letterSpacing: '0.1em', marginBottom: 12 }}>
        {title} <span style={{ color: 'var(--text-muted)' }}>· {list.length}</span>
      </h3>
      {list.length === 0 ? (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', padding: '8px 0' }}>{empty}</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {list.map(w => <MissionCard key={w.id} wo={w} onStart={start} onComplete={complete} />)}
        </div>
      )}
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Section title="📋 À FAIRE"     color="var(--amber)" list={aFaire}  empty="Aucune intervention assignée." />
      <Section title="🔧 EN COURS"    color="var(--cyan)"  list={enCours} empty="Aucune intervention en cours." />
      <Section title="✅ HISTORIQUE"  color="var(--green)" list={historique} empty="Aucune intervention terminée." />
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
export default function Interventions() {
  const role = auth.getRole()
  const isAdmin = role === 'admin'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--text)', letterSpacing: '0.05em',
            display: 'flex', alignItems: 'center', gap: 10 }}>
            <Wrench size={20} color="var(--cyan)" /> INTERVENTIONS
          </h1>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            {isAdmin ? 'DISPATCH · AFFECTATION PAR COMPÉTENCE · SUPERVISION' : 'MES INTERVENTIONS · COMPTE-RENDU'}
          </p>
        </div>
        <NotificationBell />
      </div>

      {isAdmin ? <AdminView /> : <TechnicianView />}
    </div>
  )
}
