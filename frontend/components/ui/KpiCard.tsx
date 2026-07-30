import { clsx } from 'clsx'
import { ReactNode, CSSProperties } from 'react'

interface KpiCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: number          // positive = up, negative = down
  accent?: 'gold' | 'silver' | 'success' | 'danger' | 'neutral'
  dotMatrix?: boolean
  className?: string
  style?: CSSProperties
}

const ACCENT_COLOR: Record<string, string> = {
  gold:    'var(--gold)',
  silver:  'var(--silver)',
  success: '#4CAF7D',
  danger:  '#E05555',
  neutral: 'var(--text-secondary)',
}

export default function KpiCard({
  label, value, sub, trend, accent = 'neutral', dotMatrix = true, className, style,
}: KpiCardProps) {
  const accentColor = ACCENT_COLOR[accent]
  const trendColor  = trend === undefined ? undefined : trend >= 0 ? '#4CAF7D' : '#E05555'
  const trendSymbol = trend === undefined ? null : trend >= 0 ? '▲' : '▼'

  return (
    <div
      className={clsx('card', dotMatrix && 'dot-matrix-subtle', className)}
      style={{ padding: '1.25rem 1.5rem', position: 'relative', overflow: 'hidden', ...style }}
    >
      {/* Accent line */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${accentColor}, transparent)` }} />

      <p className="text-label" style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{label}</p>
      <p style={{ fontSize: 'clamp(1.4rem, 3vw, 1.875rem)', fontWeight: 600, fontFamily: "'Inter', sans-serif", lineHeight: 1, marginBottom: '0.375rem', color: 'var(--text-primary)' }}>
        {value}
      </p>
      {(sub || trend !== undefined) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {trend !== undefined && (
            <span style={{ fontSize: '0.75rem', color: trendColor, fontWeight: 600 }}>
              {trendSymbol} {Math.abs(trend).toFixed(1)}%
            </span>
          )}
          {sub && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{sub}</span>}
        </div>
      )}
    </div>
  )
}
