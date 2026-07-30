'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { businessApi, type Business } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Plus, Building2, ArrowRight, Gem } from 'lucide-react'

export default function BusinessHubPage() {
  const router = useRouter()
  const { user, loading, logout } = useAuth()
  const [businesses, setBusinesses] = useState<Business[]>([])
  const [newName, setNewName]       = useState('')
  const [creating, setCreating]     = useState(false)
  const [showForm, setShowForm]     = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    if (!loading && !user) router.push('/login')
  }, [user, loading, router])

  useEffect(() => {
    if (user) businessApi.list().then(setBusinesses).catch(console.error)
  }, [user])

  const createBusiness = async () => {
    if (!newName.trim()) return
    setCreating(true); setError('')
    try {
      const biz = await businessApi.create(newName.trim())
      setBusinesses(prev => [...prev, biz])
      setNewName(''); setShowForm(false)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <LoadingScreen />

  return (
    <main className="dot-matrix-bg" style={{ minHeight: '100dvh', padding: '2.5rem 1.5rem' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: 800, margin: '0 auto 3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #C9A227, #8B6A10)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Gem size={16} color="#0B0B0C" />
          </div>
          <span className="font-serif" style={{ fontSize: '1rem', fontWeight: 600 }}>JewelMind</span>
        </div>
        <button onClick={logout} className="btn btn-ghost" style={{ fontSize: '0.8125rem' }}>Sign out</button>
      </div>

      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {/* Hero */}
        <div className="fade-up" style={{ marginBottom: '3rem' }}>
          <h1 className="text-display" style={{ marginBottom: '0.75rem' }}>
            Your Businesses
          </h1>
          <p className="text-body" style={{ color: 'var(--text-secondary)' }}>
            Select a business to explore its analytics, or create a new one.
          </p>
        </div>

        {/* Business Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          {businesses.map((biz, i) => (
            <button key={biz.business_id}
              className={`card card-glow fade-up fade-up-${Math.min(i + 1, 4)}`}
              onClick={() => router.push(`/businesses/${biz.business_id}/dashboard`)}
              style={{ padding: '1.5rem', text: 'left', cursor: 'pointer', border: '1px solid var(--border)', background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', gap: '1rem', transition: 'all 0.2s', textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Building2 size={20} color="var(--gold)" />
                </div>
                <ArrowRight size={16} color="var(--text-muted)" />
              </div>
              <div>
                <p style={{ margin: '0 0 0.25rem', fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>{biz.business_name}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)', margin: 0 }}>
                  Created {new Date(biz.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}
                </p>
              </div>
            </button>
          ))}

          {/* Create New Card */}
          {!showForm ? (
            <button onClick={() => setShowForm(true)}
              className="card fade-up"
              style={{ padding: '1.5rem', cursor: 'pointer', border: '1px dashed var(--border)', background: 'transparent', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', minHeight: 140, color: 'var(--text-muted)', transition: 'all 0.2s' }}>
              <Plus size={24} />
              <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>New Business</span>
            </button>
          ) : (
            <div className="card" style={{ padding: '1.5rem', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 500 }}>Business Name</p>
              <input className="input" value={newName} onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Mehta Jewellers" autoFocus onKeyDown={e => e.key === 'Enter' && createBusiness()} />
              {error && <p style={{ color: '#E05555', fontSize: '0.8125rem', margin: 0 }}>{error}</p>}
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-primary" style={{ flex: 1, height: 36 }} onClick={createBusiness} disabled={creating}>
                  {creating ? 'Creating…' : 'Create'}
                </button>
                <button className="btn btn-ghost" style={{ height: 36, padding: '0 0.875rem' }} onClick={() => { setShowForm(false); setError('') }}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

function LoadingScreen() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100dvh' }}>
      <div style={{ display: 'flex', gap: 6 }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--gold)', animation: `pulse-gold 1.2s ${i * 0.2}s ease-in-out infinite` }} />
        ))}
      </div>
    </div>
  )
}
