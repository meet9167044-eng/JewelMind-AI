'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import { ShieldAlert, AlertTriangle, Lightbulb, CheckCircle2, ArrowRight, RefreshCw, FileText } from 'lucide-react'
import Link from 'next/link'

interface AlertItem {
  rule_id: string
  priority: 'high' | 'medium' | 'low'
  title: string
  detail: string
  action_link: string
  evidence: Record<string, any>
}

interface InsightsResponse {
  business_id: number
  as_of: string
  count: number
  alerts: AlertItem[]
}

export default function InsightsPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [insights, setInsights] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedEvidence, setSelectedEvidence] = useState<any>(null)

  const fetchInsights = async () => {
    setLoading(true)
    try {
      const res = await api.get<InsightsResponse>(`/api/businesses/${bizId}/insights`)
      setInsights(res)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (bizId) fetchInsights()
  }, [bizId])

  const alerts = insights?.alerts || []

  return (
    <div className="page-container">
      <PageHeader
        badge="Action Center"
        title="Proactive Insights"
        description="Automated alerts and actionable intelligence derived from your latest sales, inventory, and commodity data."
        action={
          <button onClick={fetchInsights} className="btn btn-ghost" disabled={loading} style={{ fontSize: '0.8125rem', gap: 6 }}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            Refresh Rules
          </button>
        }
      />

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Scanning business datasets across Rule 1 (Aged Stock), Rule 2 (Stockouts), and Rule 3 (Discounts)…
        </div>
      ) : alerts.length === 0 ? (
        <div className="card fade-up" style={{ padding: '2.5rem', textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'rgba(58,143,95,0.15)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
            <CheckCircle2 size={24} color="#4CAF7D" />
          </div>
          <h3 className="text-title" style={{ margin: '0 0 0.5rem' }}>All Systems Healthy</h3>
          <p className="text-small" style={{ color: 'var(--text-secondary)', maxWidth: 460, margin: '0 auto' }}>
            No priority alerts or anomalies detected. Your inventory coverage, ageing profile, and discount rates are within optimal operating thresholds.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }} className="fade-up">
          {alerts.map((item, idx) => {
            const isHigh   = item.priority === 'high'
            const isMedium = item.priority === 'medium'

            return (
              <div key={idx} className="card" style={{
                padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                flexWrap: 'wrap', gap: '1rem',
                borderLeft: isHigh ? '3px solid #E05555' : isMedium ? '3px solid var(--gold)' : '3px solid var(--silver)'
              }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', flex: 1, minWidth: 280 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                    background: isHigh ? 'rgba(224,85,85,0.15)' : isMedium ? 'rgba(201,162,39,0.15)' : 'rgba(184,188,194,0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {isHigh && <ShieldAlert size={20} color="#E05555" />}
                    {isMedium && <AlertTriangle size={20} color="var(--gold)" />}
                    {!isHigh && !isMedium && <Lightbulb size={20} color="var(--silver)" />}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.375rem' }}>
                      <span className={`badge ${isHigh ? 'badge-danger' : isMedium ? 'badge-gold' : 'badge-neutral'}`} style={{ textTransform: 'uppercase', fontSize: '0.6875rem' }}>
                        {item.priority} Priority
                      </span>
                      <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>{item.title}</h4>
                    </div>
                    <p className="text-small" style={{ margin: '0 0 0.5rem', color: 'var(--text-secondary)', maxWidth: 640 }}>{item.detail}</p>

                    {item.evidence && (
                      <button
                        onClick={() => setSelectedEvidence(item)}
                        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                        className="text-xs text-gold"
                      >
                        <FileText size={12} /> View Trigger Evidence
                      </button>
                    )}
                  </div>
                </div>

                <Link href={`/businesses/${bizId}/${item.action_link}`} className="btn btn-ghost" style={{ fontSize: '0.8125rem' }}>
                  Resolve in {item.action_link.charAt(0).toUpperCase() + item.action_link.slice(1)} <ArrowRight size={14} />
                </Link>
              </div>
            )
          })}
        </div>
      )}

      {/* Evidence Payload Modal */}
      {selectedEvidence && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem'
        }}>
          <div className="card fade-up" style={{ width: '100%', maxWidth: 540, padding: '1.75rem', background: 'var(--bg-elevated)' }}>
            <h3 className="text-title" style={{ marginBottom: '0.5rem' }}>Trigger Evidence Payload</h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Rule: <code>{selectedEvidence.rule_id}</code> • Priority: {selectedEvidence.priority}
            </p>
            <pre style={{
              background: 'rgba(0,0,0,0.4)', padding: '0.875rem 1rem', borderRadius: 8,
              border: '1px solid var(--border)', fontSize: '0.75rem', color: '#A0D2EB',
              overflowX: 'auto', maxHeight: 240, margin: '0 0 1.25rem'
            }}>
              {JSON.stringify(selectedEvidence.evidence, null, 2)}
            </pre>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setSelectedEvidence(null)}>
              Close Trace
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
