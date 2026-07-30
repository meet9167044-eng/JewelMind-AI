'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import KpiCard from '@/components/ui/KpiCard'
import { Gem, ShieldCheck, TrendingDown, Scale } from 'lucide-react'

export default function MetalPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [goldExp, setGoldExp] = useState<any>(null)
  const [silverExp, setSilverExp] = useState<any>(null)
  const [rates, setRates] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [g, s, r] = await Promise.all([
          analyticsApi.metalExposure(bizId, 'gold'),
          analyticsApi.metalExposure(bizId, 'silver'),
          analyticsApi.metalRates(bizId),
        ])
        setGoldExp(g)
        setSilverExp(s)
        setRates(r?.rates || null)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [bizId])

  const fmt = (n: number) => {
    const abs = Math.abs(n)
    const str = abs >= 100000 ? `₹${(abs / 100000).toFixed(2)}L` : `₹${(abs / 1000).toFixed(1)}k`
    return n < 0 ? `-${str}` : `+${str}`
  }

  return (
    <div className="page-container">
      <PageHeader
        badge="Commodity Risk"
        title="Metal Exposure"
        description="Weighted Acquisition Rate (WAR) and paper Valuation Exposure based on stored daily commodity reference rates."
      />

      {/* Live / Stored Rate Banner */}
      <div className="card dot-matrix-subtle section-gap fade-up" style={{ padding: '1.25rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Gem size={22} color="var(--gold)" />
          <div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9375rem' }}>Reference Board Rates</p>
            <p className="text-xs" style={{ margin: 0, color: 'var(--text-secondary)' }}>As of {rates?.rate_date || 'latest stored database entry'}</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1.5rem' }}>
          <div>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Gold 24K</span>
            <p style={{ margin: 0, fontWeight: 600, color: 'var(--gold)' }}>₹{rates?.gold_24k || '—'}/g</p>
          </div>
          <div>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Gold 22K</span>
            <p style={{ margin: 0, fontWeight: 600, color: 'var(--gold)' }}>₹{rates?.gold_22k || '—'}/g</p>
          </div>
          <div>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Silver 999</span>
            <p style={{ margin: 0, fontWeight: 600, color: 'var(--silver)' }}>₹{rates?.silver || '—'}/g</p>
          </div>
        </div>
      </div>

      {/* Gold Exposure */}
      <h3 className="text-title fade-up fade-up-2" style={{ marginBottom: '1rem', color: 'var(--gold)' }}>Gold Holdings & Exposure</h3>
      <div className="grid-kpi section-gap fade-up fade-up-2">
        <KpiCard
          label="Gold WAR (Cost Basis)"
          value={loading ? '—' : goldExp?.war ? `₹${goldExp.war.toFixed(0)}/g` : 'N/A'}
          accent="gold"
          sub="Weighted Acquisition Rate"
        />
        <KpiCard
          label="Gold Net Weight"
          value={loading ? '—' : `${(goldExp?.total_net_weight_grams || 0).toFixed(1)} g`}
          accent="silver"
          sub={`${goldExp?.item_count || 0} active items`}
        />
        <KpiCard
          label="Gold Valuation Exposure"
          value={loading ? '—' : fmt(goldExp?.valuation_exposure || 0)}
          accent={(goldExp?.valuation_exposure || 0) >= 0 ? 'success' : 'danger'}
          sub="Paper mark-to-market float"
        />
      </div>

      {/* Silver Exposure */}
      <h3 className="text-title fade-up fade-up-3" style={{ marginBottom: '1rem', color: 'var(--silver)' }}>Silver Holdings & Exposure</h3>
      <div className="grid-kpi section-gap fade-up fade-up-3">
        <KpiCard
          label="Silver WAR (Cost Basis)"
          value={loading ? '—' : silverExp?.war ? `₹${silverExp.war.toFixed(0)}/g` : 'N/A'}
          accent="silver"
          sub="Weighted Acquisition Rate"
        />
        <KpiCard
          label="Silver Net Weight"
          value={loading ? '—' : `${(silverExp?.total_net_weight_grams || 0).toFixed(1)} g`}
          accent="neutral"
          sub={`${silverExp?.item_count || 0} active items`}
        />
        <KpiCard
          label="Silver Valuation Exposure"
          value={loading ? '—' : fmt(silverExp?.valuation_exposure || 0)}
          accent={(silverExp?.valuation_exposure || 0) >= 0 ? 'success' : 'danger'}
          sub="Paper mark-to-market float"
        />
      </div>
    </div>
  )
}
