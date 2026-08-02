'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import KpiCard from '@/components/ui/KpiCard'
import PageHeader from '@/components/ui/PageHeader'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { TrendingUp, Package, Gem, AlertTriangle } from 'lucide-react'
import Link from 'next/link'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass" style={{ padding: '0.625rem 0.875rem', borderRadius: 'var(--radius-md)', fontSize: '0.8125rem' }}>
      <p style={{ margin: '0 0 0.25rem', color: 'var(--text-secondary)' }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ margin: 0, color: p.color, fontWeight: 600 }}>
          ₹{(p.value / 1000).toFixed(1)}k
        </p>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)
  const now = new Date()
  const [metrics, setMetrics] = useState<any>(null)
  const [chartData, setChartData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const prevDate = new Date(now.getFullYear(), now.getMonth() - 1, 1)
        const [cur, prev] = await Promise.all([
          analyticsApi.grossProfit(bizId, now.getFullYear(), now.getMonth() + 1),
          analyticsApi.grossProfit(bizId, prevDate.getFullYear(), prevDate.getMonth() + 1),
        ])
        setMetrics({ current: cur, previous: prev })

        // Build 6-month sparkline
        const months = await Promise.all(
          Array.from({ length: 6 }, (_, i) => {
            const d = new Date(now.getFullYear(), now.getMonth() - 5 + i, 1)
            return analyticsApi.grossProfit(bizId, d.getFullYear(), d.getMonth() + 1)
              .then((r: any) => ({ month: MONTHS[d.getMonth()], revenue: r.net_revenue, profit: r.gross_profit }))
              .catch(() => ({ month: MONTHS[d.getMonth()], revenue: 0, profit: 0 }))
          })
        )
        setChartData(months)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [bizId])

  const cur = metrics?.current as any
  const prev = metrics?.previous as any
  const revTrend = cur && prev && prev.net_revenue > 0
    ? ((cur.net_revenue - prev.net_revenue) / prev.net_revenue) * 100 : undefined
  const profitTrend = cur && prev && prev.gross_profit > 0
    ? ((cur.gross_profit - prev.gross_profit) / prev.gross_profit) * 100 : undefined

  const fmt = (n: number) => n >= 100000 ? `₹${(n / 100000).toFixed(2)}L` : `₹${(n / 1000).toFixed(1)}k`

  const quickLinks = [
    { label: 'Profit Diagnosis', href: 'profit', icon: TrendingUp, desc: 'What drove this month\'s margin?' },
    { label: 'Inventory Health', href: 'inventory', icon: Package, desc: 'Dead stock & stockout risks' },
    { label: 'Metal Exposure', href: 'metal', icon: Gem, desc: 'Valuation risk on gold & silver' },
    { label: 'Action Center', href: 'insights', icon: AlertTriangle, desc: 'What needs your attention now' },
  ]

  return (
    <div className="page-container">
      <PageHeader
        badge="Command Center"
        title="Dashboard"
        description={`Overview for ${MONTHS[now.getMonth()]} ${now.getFullYear()}`}
      />

      {/* KPI Grid */}
      <div className="grid-kpi section-gap fade-up">
        <KpiCard label="Total Revenue" value={loading ? '—' : fmt(cur?.net_revenue ?? 0)} trend={revTrend} accent="gold" />
        <KpiCard label="Gross Profit" value={loading ? '—' : fmt(cur?.gross_profit ?? 0)} trend={profitTrend} accent="success" />
        <KpiCard label="Gross Margin" value={loading ? '—' : `${(cur?.gross_margin_pct ?? 0).toFixed(1)}%`} accent="silver" />
        <KpiCard label="Making Charge/g" value={loading ? '—' : `₹${(cur?.making_charge_per_gram ?? 0).toFixed(0)}`} accent="neutral" sub="per gram" />
      </div>

      {/* Revenue Chart */}
      <div className="card dot-matrix-subtle section-gap fade-up fade-up-2" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <p className="text-label" style={{ color: 'var(--text-muted)', marginBottom: 4 }}>6-Month Trend</p>
            <p className="text-title" style={{ margin: 0 }}>Revenue & Profit</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#C9A227" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#C9A227" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4CAF7D" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#4CAF7D" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="revenue" stroke="#C9A227" strokeWidth={2} fill="url(#revGrad)" dot={false} name="Revenue" />
            <Area type="monotone" dataKey="profit" stroke="#4CAF7D" strokeWidth={2} fill="url(#profitGrad)" dot={false} name="Profit" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Quick Links */}
      <div className="grid-2 fade-up fade-up-3">
        {quickLinks.map(({ label, href, icon: Icon, desc }) => (
          <Link key={href} href={`/businesses/${bizId}/${href}`}
            className="card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem', textDecoration: 'none', cursor: 'pointer' }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: 'var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Icon size={20} color="var(--gold)" />
            </div>
            <div>
              <p style={{ margin: '0 0 0.25rem', fontWeight: 600, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>{label}</p>
              <p className="text-small" style={{ margin: 0, color: 'var(--text-secondary)' }}>{desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
