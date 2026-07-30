'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import KpiCard from '@/components/ui/KpiCard'
import { Activity, Sliders, TrendingUp, TrendingDown } from 'lucide-react'

export default function SimulatorPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [metal, setMetal] = useState<'gold' | 'silver'>('gold')
  const [shiftPct, setShiftPct] = useState<number>(-10)
  const [simResult, setSimResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const runSim = async () => {
      setLoading(true)
      try {
        const res = await analyticsApi.simulate(bizId, metal, shiftPct)
        setSimResult(res)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    runSim()
  }, [bizId, metal, shiftPct])

  const fmt = (n: number) => {
    const abs = Math.abs(n)
    const str = abs >= 100000 ? `₹${(abs / 100000).toFixed(2)}L` : `₹${(abs / 1000).toFixed(1)}k`
    return n < 0 ? `-${str}` : `+${str}`
  }

  return (
    <div className="page-container">
      <PageHeader
        badge="Scenario Engine"
        title="Rate-Shift Scenario Simulator"
        description="Simulate potential paper valuation gain/loss under hypothetical gold or silver rate fluctuations."
      />

      {/* Control Panel */}
      <div className="card dot-matrix-subtle section-gap fade-up" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
          <Sliders size={18} color="var(--gold)" />
          <h3 className="text-title" style={{ margin: 0 }}>Simulation Parameters</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', alignItems: 'center' }}>
          {/* Metal Selector */}
          <div>
            <label className="label">Target Metal</label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className={`btn ${metal === 'gold' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1 }}
                onClick={() => setMetal('gold')}
              >
                Gold
              </button>
              <button
                className={`btn ${metal === 'silver' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1 }}
                onClick={() => setMetal('silver')}
              >
                Silver
              </button>
            </div>
          </div>

          {/* Rate Shift Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
              <label className="label" style={{ margin: 0 }}>Rate Shift Percentage</label>
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: shiftPct >= 0 ? '#4CAF7D' : '#E05555' }}>
                {shiftPct > 0 ? `+${shiftPct}%` : `${shiftPct}%`}
              </span>
            </div>
            <input
              type="range"
              min="-30"
              max="30"
              step="1"
              value={shiftPct}
              onChange={e => setShiftPct(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--gold)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              <span>-30% Drop</span>
              <span>0% (Current)</span>
              <span>+30% Rise</span>
            </div>
          </div>
        </div>
      </div>

      {/* Results KPIs */}
      <div className="grid-kpi section-gap fade-up fade-up-2">
        <KpiCard
          label="Current Valuation Exposure"
          value={loading ? '—' : fmt(simResult?.current_exposure || 0)}
          accent="neutral"
        />
        <KpiCard
          label="Simulated Exposure"
          value={loading ? '—' : fmt(simResult?.simulated_exposure || 0)}
          accent={shiftPct >= 0 ? 'success' : 'danger'}
        />
        <KpiCard
          label="Valuation Movement (Delta Impact)"
          value={loading ? '—' : fmt(simResult?.delta_value || 0)}
          accent={(simResult?.delta_value || 0) >= 0 ? 'success' : 'danger'}
          sub="Paper valuation shift"
        />
      </div>
    </div>
  )
}
