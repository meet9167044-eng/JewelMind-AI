'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { analyticsApi } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import { Lightbulb, AlertTriangle, ShieldAlert, CheckCircle, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function InsightsPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [deadCount, setDeadCount] = useState(0)
  const [stockoutCount, setStockoutCount] = useState(0)
  const [goldExp, setGoldExp] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchInsights = async () => {
      setLoading(true)
      try {
        const [perf, exp] = await Promise.all([
          analyticsApi.inventoryPerformance(bizId),
          analyticsApi.metalExposure(bizId, 'gold'),
        ])
        setDeadCount(perf?.dead_stock?.length || 0)
        setStockoutCount(perf?.stockout_risks?.length || 0)
        setGoldExp(exp?.valuation_exposure || 0)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchInsights()
  }, [bizId])

  const insightsList = [
    {
      title: 'Dead Stock Clearance Recommended',
      level: deadCount > 0 ? 'high' : 'ok',
      desc: deadCount > 0
        ? `You have ${deadCount} items in inventory over 180 days old with zero sales in the last 90 days. Consider offering targeted discounts or melting.`
        : 'No dead stock detected across active inventory.',
      actionHref: `/businesses/${bizId}/inventory`,
      actionLabel: 'View Inventory',
    },
    {
      title: 'Stockout Warning for Fast Movers',
      level: stockoutCount > 0 ? 'warning' : 'ok',
      desc: stockoutCount > 0
        ? `${stockoutCount} fast-moving products have less than 15 days of stock coverage remaining.`
        : 'Stock coverage is healthy across high-velocity categories.',
      actionHref: `/businesses/${bizId}/inventory`,
      actionLabel: 'Check Coverage',
    },
    {
      title: 'Gold Valuation Exposure Float',
      level: goldExp < 0 ? 'warning' : 'info',
      desc: goldExp < 0
        ? `Your active gold inventory is currently valued below acquisition cost (${(goldExp/1000).toFixed(1)}k paper loss). Hold inventory until market rates recover.`
        : `Gold valuation is currently positive (+${(goldExp/1000).toFixed(1)}k above acquisition cost).`,
      actionHref: `/businesses/${bizId}/metal`,
      actionLabel: 'Inspect Metal',
    },
  ]

  return (
    <div className="page-container">
      <PageHeader
        badge="Action Center"
        title="Proactive Insights"
        description="Automated alerts and actionable intelligence derived from your latest sales, inventory, and commodity data."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }} className="fade-up">
        {insightsList.map((item, idx) => (
          <div key={idx} className="card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: item.level === 'high' ? 'rgba(161,51,51,0.15)' : item.level === 'warning' ? 'rgba(201,162,39,0.15)' : 'rgba(58,143,95,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {item.level === 'high' && <ShieldAlert size={18} color="#E05555" />}
                {item.level === 'warning' && <AlertTriangle size={18} color="var(--gold)" />}
                {item.level === 'ok' && <CheckCircle size={18} color="#4CAF7D" />}
                {item.level === 'info' && <Lightbulb size={18} color="var(--gold)" />}
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.25rem', fontSize: '1rem', fontWeight: 600 }}>{item.title}</h4>
                <p className="text-small" style={{ margin: 0, color: 'var(--text-secondary)', maxWidth: 620 }}>{item.desc}</p>
              </div>
            </div>
            <Link href={item.actionHref} className="btn btn-ghost" style={{ fontSize: '0.8125rem' }}>
              {item.actionLabel} <ArrowRight size={14} />
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}
