export default function MetricCard({
  label, value, unit = '', color = 'var(--cyan)',
  trend = null, icon: Icon = null, size = 'md',
  glow = false
}) {
  const fontSize = size === 'lg' ? 32 : size === 'sm' ? 18 : 24

  return (
    <div className="card" style={{
      display       : 'flex',
      flexDirection : 'column',
      gap           : 8,
      boxShadow     : glow ? `0 0 30px ${color}22` : 'none',
      borderColor   : glow ? `${color}44` : 'var(--border)',
    }}>
      <div style={{
        display    : 'flex',
        alignItems : 'center',
        gap        : 8,
      }}>
        {Icon && (
          <Icon size={14} color={color} />
        )}
        <span className="metric-label">{label}</span>
      </div>

      <div style={{
        display    : 'flex',
        alignItems : 'baseline',
        gap        : 6,
      }}>
        <span
          className="metric-value"
          style={{
            fontSize,
            color,
            filter : glow
              ? `drop-shadow(0 0 8px ${color})`
              : 'none',
          }}
        >
          {value ?? '—'}
        </span>
        {unit && (
          <span style={{
            fontFamily : 'var(--font-mono)',
            fontSize   : fontSize * 0.45,
            color      : 'var(--text-muted)',
          }}>
            {unit}
          </span>
        )}
      </div>

      {trend !== null && (
        <div style={{
          fontFamily : 'var(--font-mono)',
          fontSize   : 11,
          color      : trend < 0 ? 'var(--red)' : 'var(--green)',
        }}>
          {trend < 0 ? '▼' : '▲'} {Math.abs(trend).toFixed(2)}%/cycle
        </div>
      )}
    </div>
  )
}