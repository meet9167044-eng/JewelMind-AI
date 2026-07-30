'use client'
import { useState, FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import { Gem } from 'lucide-react'

export default function RegisterPage() {
  const router = useRouter()
  const [fullName, setFullName] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (password.length < 8) { setError('Password must be at least 8 characters'); return }
    setError(''); setLoading(true)
    try {
      const res = await authApi.register({ email, password, full_name: fullName })
      localStorage.setItem('jewelmind_token', res.access_token)
      router.push('/businesses')
    } catch (err: any) {
      setError(err.message || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="dot-matrix-bg" style={{
      minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1.5rem',
    }}>
      <div style={{
        position: 'fixed', bottom: '20%', left: '50%', transform: 'translateX(-50%)',
        width: 500, height: 350, borderRadius: '50%',
        background: 'radial-gradient(ellipse, rgba(184,188,194,0.05) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div className="card fade-up" style={{ width: '100%', maxWidth: 420, padding: '2.5rem 2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '2rem' }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #C9A227, #8B6A10)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Gem size={18} color="#0B0B0C" />
          </div>
          <span className="font-serif" style={{ fontSize: '1.125rem', fontWeight: 600 }}>JewelMind</span>
        </div>

        <h1 className="text-title" style={{ marginBottom: '0.375rem' }}>Create your account</h1>
        <p className="text-small" style={{ color: 'var(--text-secondary)', marginBottom: '1.75rem' }}>
          Start understanding your jewellery business, deeply.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label className="label" htmlFor="fullname">Full Name</label>
            <input id="fullname" type="text" className="input" value={fullName}
              onChange={e => setFullName(e.target.value)} placeholder="Rajesh Mehta" required />
          </div>
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email}
              onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
          </div>
          <div>
            <label className="label" htmlFor="password">Password <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(min. 8 characters)</span></label>
            <input id="password" type="password" className="input" value={password}
              onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
          </div>

          {error && <p style={{ color: '#E05555', fontSize: '0.8125rem', margin: 0 }}>{error}</p>}

          <button type="submit" className="btn btn-primary" disabled={loading}
            style={{ marginTop: '0.5rem', height: 42 }}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-small" style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
          Already have an account?{' '}
          <Link href="/login" style={{ color: 'var(--gold)', textDecoration: 'none', fontWeight: 500 }}>
            Sign in
          </Link>
        </p>
      </div>
    </main>
  )
}
