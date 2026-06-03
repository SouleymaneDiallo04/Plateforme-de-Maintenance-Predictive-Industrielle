import { useState } from 'react'
import { Zap, Eye, EyeOff, LogIn, UserPlus } from 'lucide-react'
import { api } from '../api/client'

export default function LoginPage({ onLogin }) {
  const [tab,      setTab]      = useState('login')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [visible,  setVisible]  = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const endpoint = tab === 'login' ? '/auth/login' : '/auth/register'
      const res = await api.post(endpoint, { email, password })
      onLogin(res.data.access_token, res.data.user)
    } catch (err) {
      setError(err.response?.data?.detail || 'Une erreur est survenue')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%', padding: '10px 14px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-elevated)',
    color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 13,
    outline: 'none', boxSizing: 'border-box',
  }

  const tabBtn = (id, label) => (
    <button
      key={id}
      onClick={() => { setTab(id); setError('') }}
      style={{
        flex: 1, padding: '10px', border: 'none',
        background: tab === id ? 'var(--cyan-dim)' : 'transparent',
        borderBottom: tab === id ? '2px solid var(--cyan)' : '2px solid transparent',
        color: tab === id ? 'var(--cyan)' : 'var(--text-muted)',
        fontFamily: 'var(--font-display)', fontSize: 11,
        letterSpacing: '0.1em', cursor: 'pointer', transition: 'all 0.2s',
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'var(--bg)',
      position: 'relative', overflow: 'hidden',
    }}>
      <div className="scan-grid" />
      <div className="scan-line" />

      <div style={{
        width: 400, zIndex: 10, display: 'flex', flexDirection: 'column',
        gap: 0, background: 'var(--bg-surface)',
        border: '1px solid var(--border)', borderRadius: 16,
        overflow: 'hidden', boxShadow: '0 0 40px rgba(0,212,255,0.08)',
      }}>
        {/* Header */}
        <div style={{
          padding: '28px 28px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            border: '2px solid var(--cyan)', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            boxShadow: 'var(--cyan-glow)',
            animation: 'glow-pulse 3s ease-in-out infinite',
          }}>
            <Zap size={18} color="var(--cyan)" fill="var(--cyan)" />
          </div>
          <div>
            <div style={{
              fontFamily: 'var(--font-display)', fontSize: 18,
              fontWeight: 700, color: 'var(--cyan)', letterSpacing: '0.1em',
            }}>PROGNOSENSE</div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: 'var(--text-muted)', letterSpacing: '0.12em',
            }}>MAINTENANCE PRÉDICTIVE · IA</div>
          </div>
        </div>

        {/* Onglets */}
        <div style={{ display: 'flex' }}>
          {tabBtn('login',    'CONNEXION')}
          {tabBtn('register', 'INSCRIPTION')}
        </div>

        {/* Formulaire */}
        <form onSubmit={submit} style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>
              ADRESSE EMAIL
            </div>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="vous@exemple.com"
              required
              style={inputStyle}
            />
          </div>

          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>
              MOT DE PASSE
            </div>
            <div style={{ position: 'relative' }}>
              <input
                type={visible ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                style={{ ...inputStyle, paddingRight: 42 }}
              />
              <button
                type="button"
                onClick={() => setVisible(v => !v)}
                style={{
                  position: 'absolute', right: 12, top: '50%',
                  transform: 'translateY(-50%)', background: 'transparent',
                  border: 'none', color: 'var(--text-muted)', cursor: 'pointer',
                  padding: 0, display: 'flex',
                }}
              >
                {visible ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {error && (
            <div style={{
              padding: '8px 12px', borderRadius: 6,
              background: 'rgba(255,51,102,0.1)', border: '1px solid var(--red)',
              fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--red)',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '11px', borderRadius: 8, border: 'none',
              background: loading ? 'var(--border)' : 'var(--cyan)',
              color: '#000', cursor: loading ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-display)', fontSize: 12,
              letterSpacing: '0.08em', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              transition: 'all 0.2s',
            }}
          >
            {tab === 'login'
              ? <><LogIn size={14} />{loading ? 'CONNEXION...' : 'SE CONNECTER'}</>
              : <><UserPlus size={14} />{loading ? 'CRÉATION...' : 'CRÉER UN COMPTE'}</>
            }
          </button>

          <div style={{
            textAlign: 'center', fontFamily: 'var(--font-mono)',
            fontSize: 10, color: 'var(--text-muted)',
          }}>
            {tab === 'login'
              ? <>Pas encore de compte ?{' '}
                  <span onClick={() => setTab('register')} style={{ color: 'var(--cyan)', cursor: 'pointer' }}>
                    S'inscrire
                  </span></>
              : <>Déjà un compte ?{' '}
                  <span onClick={() => setTab('login')} style={{ color: 'var(--cyan)', cursor: 'pointer' }}>
                    Se connecter
                  </span></>
            }
          </div>
        </form>
      </div>
    </div>
  )
}
