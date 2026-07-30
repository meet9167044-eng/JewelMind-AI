import { ReactNode, CSSProperties } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  action?: ReactNode
  badge?: string
}

export default function PageHeader({ title, description, action, badge }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
      <div>
        {badge && (
          <span className="badge badge-gold" style={{ marginBottom: '0.5rem', display: 'inline-flex' }}>{badge}</span>
        )}
        <h1 className="text-headline" style={{ margin: '0 0 0.375rem', color: 'var(--text-primary)' }}>{title}</h1>
        {description && (
          <p className="text-body" style={{ margin: 0, color: 'var(--text-secondary)', maxWidth: 560 }}>{description}</p>
        )}
      </div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  )
}
