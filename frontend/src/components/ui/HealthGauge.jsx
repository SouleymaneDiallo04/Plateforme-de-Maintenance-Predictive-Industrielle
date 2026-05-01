export default function HealthGauge({ value = 75, size = 160, label = '' }) {
  const r         = (size - 20) / 2
  const cx        = size / 2
  const cy        = size / 2
  const circumf   = 2 * Math.PI * r
  const arcLen    = circumf * 0.75   // 270° d'arc
  const progress  = arcLen * (value / 100)
  const rotation  = -225             // départ en bas gauche

  const color = value >= 70 ? 'var(--green)'
              : value >= 40 ? 'var(--amber)'
              : value >= 20 ? 'var(--orange)'
              :               'var(--red)'

  const glow  = value >= 70 ? 'var(--green-glow)'
              : value < 20  ? 'var(--red-glow)'
              : 'none'

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: `rotate(${rotation}deg)` }}>
        {/* Fond de la jauge */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth={8}
          strokeDasharray={`${arcLen} ${circumf - arcLen}`}
          strokeLinecap="round"
        />
        {/* Progression */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={`${progress} ${circumf - progress}`}
          strokeLinecap="round"
          style={{
            filter     : glow !== 'none' ? `drop-shadow(0 0 8px ${color})` : 'none',
            transition : 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)',
          }}
        />
      </svg>

      {/* Valeur centrale */}
      <div style={{
        position      : 'absolute',
        inset         : 0,
        display       : 'flex',
        flexDirection : 'column',
        alignItems    : 'center',
        justifyContent: 'center',
      }}>
        <span style={{
          fontFamily : 'var(--font-display)',
          fontSize   : size * 0.22,
          fontWeight : 700,
          color,
          lineHeight : 1,
          filter     : glow !== 'none'
            ? `drop-shadow(0 0 10px ${color})`
            : 'none',
        }}>
          {Math.round(value)}
        </span>
        <span style={{
          fontFamily  : 'var(--font-mono)',
          fontSize    : size * 0.08,
          color       : 'var(--text-muted)',
          letterSpacing: '0.1em',
          marginTop   : 2,
        }}>
          %
        </span>
        {label && (
          <span style={{
            fontFamily  : 'var(--font-mono)',
            fontSize    : size * 0.07,
            color       : 'var(--text-muted)',
            letterSpacing: '0.08em',
            marginTop   : 4,
            textTransform: 'uppercase',
          }}>
            {label}
          </span>
        )}
      </div>
    </div>
  )
}