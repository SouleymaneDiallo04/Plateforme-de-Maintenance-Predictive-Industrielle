import { useState } from 'react'
import {
  LayoutDashboard, Activity, FlaskConical,
  Timer, ClipboardList, Settings, Zap,
  ChevronRight, Wifi, WifiOff
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'overview',    icon: LayoutDashboard, label: 'Vue Globale',   short: 'VUE' },
  { id: 'monitoring',  icon: Activity,        label: 'Monitoring',    short: 'MON' },
  { id: 'ialab',       icon: FlaskConical,    label: 'IA Lab',        short: 'LAB' },
  { id: 'prognostic',  icon: Timer,           label: 'Pronostic RUL', short: 'RUL' },
  { id: 'maintenance', icon: ClipboardList,   label: 'Maintenance',   short: 'LOG' },
  { id: 'config',      icon: Settings,        label: 'Configuration', short: 'CFG' },
]

export default function Sidebar({ active, onNav, wsStatus, alerts }) {
  const [collapsed, setCollapsed] = useState(false)

  const criticalCount = alerts?.filter(
    a => a.type?.includes('rouge') || a.type?.includes('critique')
  ).length || 0

  return (
    <aside
      style={{
        width         : collapsed ? 64 : 220,
        minWidth      : collapsed ? 64 : 220,
        height        : '100vh',
        background    : 'var(--bg-surface)',
        borderRight   : '1px solid var(--border)',
        display       : 'flex',
        flexDirection : 'column',
        transition    : 'width 0.3s cubic-bezier(0.4,0,0.2,1)',
        position      : 'relative',
        zIndex        : 10,
      }}
    >
      {/* Logo */}
      <div style={{
        padding      : '20px 16px',
        borderBottom : '1px solid var(--border)',
        display      : 'flex',
        alignItems   : 'center',
        gap          : 12,
        overflow     : 'hidden',
      }}>
        <div style={{
          width           : 32, height: 32,
          borderRadius    : '50%',
          border          : '2px solid var(--cyan)',
          display         : 'flex',
          alignItems      : 'center',
          justifyContent  : 'center',
          flexShrink      : 0,
          boxShadow       : 'var(--cyan-glow)',
          animation       : 'glow-pulse 3s ease-in-out infinite',
        }}>
          <Zap size={14} color="var(--cyan)" fill="var(--cyan)" />
        </div>
        {!collapsed && (
          <div>
            <div style={{
              fontFamily : 'var(--font-display)',
              fontSize   : 14,
              fontWeight : 700,
              color      : 'var(--cyan)',
              letterSpacing: '0.1em',
            }}>
              PROGNO
            </div>
            <div style={{
              fontFamily : 'var(--font-display)',
              fontSize   : 10,
              color      : 'var(--text-muted)',
              letterSpacing: '0.15em',
            }}>
              SENSE
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '12px 8px', overflow: 'auto' }}>
        {NAV_ITEMS.map(({ id, icon: Icon, label, short }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => onNav(id)}
              style={{
                width          : '100%',
                display        : 'flex',
                alignItems     : 'center',
                gap            : 12,
                padding        : collapsed ? '12px 16px' : '10px 12px',
                borderRadius   : 'var(--radius)',
                border         : 'none',
                background     : isActive
                  ? 'var(--cyan-dim)'
                  : 'transparent',
                color          : isActive
                  ? 'var(--cyan)'
                  : 'var(--text-muted)',
                cursor         : 'pointer',
                transition     : 'var(--transition)',
                marginBottom   : 2,
                borderLeft     : isActive
                  ? '2px solid var(--cyan)'
                  : '2px solid transparent',
                justifyContent : collapsed ? 'center' : 'flex-start',
                overflow       : 'hidden',
                whiteSpace     : 'nowrap',
                position       : 'relative',
              }}
            >
              <Icon
                size={18}
                style={{
                  flexShrink : 0,
                  filter     : isActive
                    ? 'drop-shadow(0 0 6px var(--cyan))'
                    : 'none'
                }}
              />
              {!collapsed && (
                <span style={{
                  fontFamily : 'var(--font-ui)',
                  fontSize   : 13,
                  fontWeight : isActive ? 600 : 400,
                }}>
                  {label}
                </span>
              )}
              {/* Badge alertes critiques sur Maintenance */}
              {id === 'maintenance' && criticalCount > 0 && (
                <span style={{
                  marginLeft    : 'auto',
                  background    : 'var(--red)',
                  color         : 'white',
                  borderRadius  : '10px',
                  padding       : '1px 6px',
                  fontSize      : 10,
                  fontFamily    : 'var(--font-mono)',
                  fontWeight    : 700,
                  flexShrink    : 0,
                  animation     : 'pulse-red 2s infinite',
                }}>
                  {criticalCount}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Statut WebSocket */}
      <div style={{
        padding      : '12px 16px',
        borderTop    : '1px solid var(--border)',
        display      : 'flex',
        alignItems   : 'center',
        gap          : 8,
        overflow     : 'hidden',
      }}>
        {wsStatus === 'connected'
          ? <Wifi size={14} color="var(--green)" />
          : <WifiOff size={14} color="var(--text-muted)" />
        }
        {!collapsed && (
          <span style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : 10,
            color      : wsStatus === 'connected'
              ? 'var(--green)'
              : 'var(--text-muted)',
            letterSpacing: '0.05em',
          }}>
            {wsStatus === 'connected' ? 'LIVE' : 'OFFLINE'}
          </span>
        )}
      </div>

      {/* Bouton collapse */}
      <button
        onClick={() => setCollapsed(c => !c)}
        style={{
          position   : 'absolute',
          right      : -12,
          top        : '50%',
          transform  : 'translateY(-50%)',
          width      : 24, height: 24,
          borderRadius: '50%',
          background : 'var(--bg-elevated)',
          border     : '1px solid var(--border)',
          display    : 'flex',
          alignItems : 'center',
          justifyContent: 'center',
          cursor     : 'pointer',
          color      : 'var(--text-muted)',
          zIndex     : 20,
        }}
      >
        <ChevronRight
          size={12}
          style={{
            transform  : collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
            transition : 'transform 0.3s',
          }}
        />
      </button>
    </aside>
  )
}