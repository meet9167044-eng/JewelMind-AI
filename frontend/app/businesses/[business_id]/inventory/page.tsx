'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import KpiCard from '@/components/ui/KpiCard'
import { Package, AlertTriangle, Clock, ShieldAlert } from 'lucide-react'

export default function InventoryPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [ageData, setAgeData] = useState<any>(null)
  const [perfData, setPerfData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [age, perf] = await Promise.all([
          analyticsApi.inventoryAge(bizId),
          analyticsApi.inventoryPerformance(bizId),
        ])
        setAgeData(age)
        setPerfData(perf)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [bizId])

  const buckets = ageData?.buckets || {}
  const deadStock = perfData?.dead_stock || []
  const slowMovers = perfData?.slow_movers || []
  const stockoutRisks = perfData?.stockout_risks || []

  return (
    <div className="page-container">
      <PageHeader
        badge="Stock & Coverage"
        title="Inventory Intelligence"
        description="Monitor unsold inventory ageing, dead stock detection (>180d no sales), and stockout risks."
      />

      {/* KPI summary */}
      <div className="grid-kpi section-gap fade-up">
        <KpiCard
          label="Total Unsold Items"
          value={loading ? '—' : (ageData?.total_items ?? 0)}
          accent="gold"
        />
        <KpiCard
          label="Total Inventory Weight"
          value={loading ? '—' : `${(ageData?.total_weight ?? 0).toFixed(1)} g`}
          accent="silver"
        />
        <KpiCard
          label="Dead Stock Count"
          value={loading ? '—' : deadStock.length}
          accent="danger"
          sub=">180d age, 0 sales in 90d"
        />
        <KpiCard
          label="Stockout Risks"
          value={loading ? '—' : stockoutRisks.length}
          accent="warning"
          sub="Fast movers <15d coverage"
        />
      </div>

      {/* Ageing Buckets Bar */}
      <div className="card dot-matrix-subtle section-gap fade-up fade-up-2" style={{ padding: '1.5rem' }}>
        <h3 className="text-title" style={{ marginBottom: '1.25rem' }}>Ageing Breakdown (Days Unsold)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
          {['0-30d', '31-90d', '91-180d', '181-365d', '365+d'].map((bKey) => {
            const b = buckets[bKey] || { count: 0, weight: 0, value: 0 }
            const w = b.weight ?? b.total_weight ?? 0
            const v = b.value ?? b.total_value ?? 0
            return (
              <div key={bKey} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                <p className="text-label" style={{ color: 'var(--gold)', marginBottom: 4 }}>{bKey}</p>
                <p style={{ fontSize: '1.25rem', fontWeight: 600, margin: '0 0 4px' }}>{b.count ?? 0} items</p>
                <p className="text-xs" style={{ color: 'var(--text-secondary)', margin: 0 }}>{w.toFixed(1)} g • ₹{(v / 1000).toFixed(1)}k</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Classification lists */}
      <div className="grid-2 fade-up fade-up-3">
        {/* Dead Stock */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <ShieldAlert size={18} color="#E05555" />
            <h3 className="text-title" style={{ margin: 0 }}>Dead Stock ({deadStock.length})</h3>
          </div>
          {deadStock.length === 0 ? (
            <p className="text-small" style={{ color: 'var(--text-muted)' }}>No dead stock detected.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: 260, overflowY: 'auto' }}>
              {deadStock.map((item: any, idx: number) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.625rem 0.875rem', background: 'rgba(255,255,255,0.02)', borderRadius: 8 }}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600, fontSize: '0.875rem' }}>{item.product_name || item.sku}</p>
                    <p className="text-xs" style={{ margin: 0, color: 'var(--text-secondary)' }}>{item.category} • {item.age_days}d old</p>
                  </div>
                  <span className="badge badge-danger">{item.remaining_weight}g</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Slow Movers */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Clock size={18} color="var(--gold)" />
            <h3 className="text-title" style={{ margin: 0 }}>Slow Movers ({slowMovers.length})</h3>
          </div>
          {slowMovers.length === 0 ? (
            <p className="text-small" style={{ color: 'var(--text-muted)' }}>No slow movers identified.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: 260, overflowY: 'auto' }}>
              {slowMovers.map((item: any, idx: number) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.625rem 0.875rem', background: 'rgba(255,255,255,0.02)', borderRadius: 8 }}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600, fontSize: '0.875rem' }}>{item.product_name || item.sku}</p>
                    <p className="text-xs" style={{ margin: 0, color: 'var(--text-secondary)' }}>Coverage: {item.stock_coverage_days?.toFixed(0)}d</p>
                  </div>
                  <span className="badge badge-gold">{item.remaining_weight}g</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
