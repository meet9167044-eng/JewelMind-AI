'use client'
import { FileText, X, ShieldCheck, Database, Calculator } from 'lucide-react'

interface Props {
  evidence: {
    tool: string
    params: Record<string, any>
    result: Record<string, any>
    formula: string
    source_tables?: string[]
    scoped_to_business_id?: number
  } | null
  onClose: () => void
}

export default function ViewEvidenceModal({ evidence, onClose }: Props) {
  if (!evidence) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem'
    }}>
      <div className="card fade-up" style={{
        width: '100%', maxWidth: 640, maxHeight: '85vh', overflowY: 'auto',
        padding: '1.75rem', position: 'relative', background: 'var(--bg-elevated)'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ShieldCheck size={18} color="var(--gold)" />
            </div>
            <div>
              <h3 className="text-title" style={{ margin: 0 }}>View Evidence — Explainability Trace</h3>
              <p className="text-xs" style={{ margin: 0, color: 'var(--text-secondary)' }}>Tool: {evidence.tool}</p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {/* Multi-tenancy Isolation Badge */}
        {evidence.scoped_to_business_id && (
          <div style={{ marginBottom: '1rem', padding: '0.625rem 0.875rem', background: 'rgba(58,143,95,0.12)', border: '1px solid rgba(58,143,95,0.25)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldCheck size={16} color="#4CAF7D" />
            <span className="text-xs" style={{ color: '#4CAF7D', fontWeight: 500 }}>
              Deterministic SQL execution isolated to Business ID #{evidence.scoped_to_business_id}
            </span>
          </div>
        )}

        {/* Mathematical Formula */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.375rem' }}>
            <Calculator size={14} color="var(--gold)" />
            <span className="text-label" style={{ color: 'var(--gold)' }}>Calculation Formula</span>
          </div>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem 1rem', borderRadius: 8, border: '1px solid var(--border)' }}>
            <code style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', fontFamily: 'monospace' }}>{evidence.formula}</code>
          </div>
        </div>

        {/* Source Tables */}
        {evidence.source_tables && (
          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.375rem' }}>
              <Database size={14} color="var(--silver)" />
              <span className="text-label" style={{ color: 'var(--silver)' }}>Queried MySQL Tables</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {evidence.source_tables.map((t, idx) => (
                <span key={idx} className="badge badge-neutral" style={{ fontFamily: 'monospace' }}>{t}</span>
              ))}
            </div>
          </div>
        )}

        {/* Raw Tool Payload Output */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.375rem' }}>
            <FileText size={14} color="var(--text-secondary)" />
            <span className="text-label" style={{ color: 'var(--text-secondary)' }}>Verified Tool Payload</span>
          </div>
          <pre style={{
            background: 'rgba(0,0,0,0.4)', padding: '0.875rem 1rem', borderRadius: 8,
            border: '1px solid var(--border)', fontSize: '0.75rem', color: '#A0D2EB',
            overflowX: 'auto', maxHeight: 220, margin: 0
          }}>
            {JSON.stringify(evidence.result, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}
