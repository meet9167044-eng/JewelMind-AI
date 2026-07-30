'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import KpiCard from '@/components/ui/KpiCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts'
import { TrendingUp, TrendingDown, HelpCircle, ArrowRight } from 'lucide-react'

export default function ProfitPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [targetYear, setTargetYear] = useState(2026)
  const [targetMonth, setTargetMonth] = useState(6)
  const [baseYear, setBaseYear] = useState(2026)
  const [baseMonth, setBaseMonth] = useState(5)

  const [diagnosis, setDiagnosis] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDiagnosis = async () => {
      setLoading(true)
      try {
        const res = await analyticsApi.profitDiagnosis(bizId, targetYear, targetMonth, baseYear, baseMonth)
        setDiagnosis(res)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchDiagnosis()
  }, [bizId, targetYear, targetMonth, baseYear, baseMonth])

  const drivers = diagnosis?.driver_breakdown || {}
  const chartData = [
    { name: 'Volume', value: drivers.volume_effect?.impact || 0, desc: 'Sales volume change' },
    { name: 'Discount', value: drivers.discount_effect?.impact || 0, desc: 'Discount depth shift' },
    { name: 'Making Chg', value: drivers.making_charge_effect?.impact || 0, desc: 'Making charge rate shift' },
    { name: 'Product Mix', value: drivers.product_mix_effect?.impact || 0, desc: 'High vs low margin category mix' },
    { name: 'Metal Margin', value: drivers.metal_margin_effect?.impact || 0, desc: 'Raw metal cost vs selling rate' },
  ]

  const totalDelta = diagnosis?.total_gross_profit_change || 0

  const fmt = (n: number) => {
    const abs = Math.abs(n)
    const str = abs >= 100000 ? `₹${(abs / 100000).toFixed(2)}L` : `₹${(abs / 1000).toFixed(1)}k`
    return n < 0 ? `-${str}` : `+${str}`
  }

  return (
    <div className="page-container">
      <PageHeader
        badge="Variance Decomposition"
        title="Profit Diagnosis"
        description="Deconstruct your month-over-month profit movement into 5 additive financial drivers."
      />

      {/* Selector Controls */}
      <div className="card" style={{ padding: '1rem 1.5rem', marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="text-small" style={{ color: 'var(--text-secondary)' }}>Target Month:</span>
          <select className="input" style={{ width: 'auto', padding: '0.375rem 0.75rem' }} value={`${targetYear}-${targetMonth}`} onChange={e => {
            const [y, m] = e.target.value.split('-').map(Number)
            setTargetYear(y); setTargetMonth(m)
          }}>
            <option value="2026-6">June 2026</option>
            <option value="2026-5">May 2026</option>
            <option value="2026-4">April 2026</option>
          </select>
        </div>

        <ArrowRight size={16} color="var(--text-muted)" />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="text-small" style={{ color: 'var(--text-secondary)' }}>Baseline Month:</span>
          <select className="input" style={{ width: 'auto', padding: '0.375rem 0.75rem' }} value={`${baseYear}-${baseMonth}`} onChange={e => {
            const [y, m] = e.target.value.split('-').map(Number)
            setBaseYear(y); setBaseMonth(m)
          }}>
            <option value="2026-5">May 2026</option>
            <option value="2026-4">April 2026</option>
            <option value="2026-3">March 2026</option>
          </select>
        </div>
      </div>

      {/* Main KPI */}
      <div className="grid-kpi section-gap fade-up">
        <KpiCard
          label="Total Profit Variance"
          value={loading ? '—' : fmt(totalDelta)}
          accent={totalDelta >= 0 ? 'success' : 'danger'}
          sub={`vs ${baseYear}-${String(baseMonth).padStart(2,'0')}`}
        />
        <KpiCard
          label="Target Gross Profit"
          value={loading ? '—' : `₹${((diagnosis?.target_period_profit || 0)/1000).toFixed(1)}k`}
          accent="gold"
        />
        <KpiCard
          label="Baseline Gross Profit"
          value={loading ? '—' : `₹${((diagnosis?.baseline_period_profit || 0)/1000).toFixed(1)}k`}
          accent="silver"
        />
      </div>

      {/* Waterfall / Driver Bar Chart */}
      <div className="card dot-matrix-subtle section-gap fade-up fade-up-2" style={{ padding: '1.5rem' }}>
        <div style={{ marginBottom: '1.5rem' }}>
          <p className="text-label" style={{ color: 'var(--text-muted)', marginBottom: 4 }}>5-Driver Variance Breakdown</p>
          <p className="text-title" style={{ margin: 0 }}>What drove the change in profit?</p>
        </div>

        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip
              formatter={(val: any) => [fmt(Number(val)), 'Impact']}
              contentStyle={{ background: 'rgba(20,20,22,0.92)', border: '1px solid var(--border)', borderRadius: 8 }}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={entry.value >= 0 ? '#4CAF7D' : '#E05555'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Driver Detail Cards */}
      <div className="grid-2 fade-up fade-up-3">
        {chartData.map((d) => (
          <div key={d.name} className="card" style={{ padding: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ margin: '0 0 0.25rem', fontWeight: 600, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>{d.name}</p>
              <p className="text-small" style={{ margin: 0, color: 'var(--text-secondary)' }}>{d.desc}</p>
            </div>
            <span style={{ fontSize: '1.125rem', fontWeight: 600, color: d.value >= 0 ? '#4CAF7D' : '#E05555' }}>
              {fmt(d.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
