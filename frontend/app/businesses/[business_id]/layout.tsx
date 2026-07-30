'use client'
import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import { useAuth } from '@/hooks/useAuth'
import { businessApi, type Business } from '@/lib/api'

export default function BusinessLayout({ children }: { children: React.ReactNode }) {
  const params = useParams()
  const router = useRouter()
  const bizId = Number(params.business_id)

  const { user, loading, logout } = useAuth()
  const [biz, setBiz]         = useState<Business | null>(null)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    if (!loading && !user) router.push('/login')
  }, [user, loading, router])

  useEffect(() => {
    if (user && bizId) {
      businessApi.get(bizId).then(setBiz).catch(() => router.push('/businesses'))
    }
  }, [user, bizId, router])

  if (loading || !user) return <LoadingOverlay />

  return (
    <>
      <Sidebar bizId={bizId} collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <TopBar
        userName={user.full_name}
        bizName={biz?.business_name ?? '…'}
        onLogout={logout}
      />
      <div
        className="main-layout"
        style={{ marginLeft: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-w)', paddingTop: 'var(--topbar-h)' }}
      >
        {children}
      </div>
    </>
  )
}

function LoadingOverlay() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100dvh', background: 'var(--bg)' }}>
      <div style={{ display: 'flex', gap: 6 }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--gold)', animation: `pulse-gold 1.2s ${i * 0.2}s ease-in-out infinite` }} />
        ))}
      </div>
    </div>
  )
}
