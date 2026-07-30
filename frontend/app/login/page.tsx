'use client'
import { useState, FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import { Eye, EyeOff, Gem } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd]   = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const res = await authApi.login({ email, password })
      localStorage.setItem('jewelmind_token', res.access_token)
      router.push('/businesses')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="dot-matrix-bg" style={{
      minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1.5rem',
    }}>
      {/* Background gradient orb */}
      <div style={{
        position: 'fixed', top: '30%', left: '50%', transform: 'translateX(-50%)',
        width: 600, height: 400, borderRadius: '50%',
        background: 'radial-gradient(ellipse, rgba(201,162,39,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div className="card fade-up" style={{ width: '100%', maxWidth: 420, padding: '2.5rem 2rem' }}>
        {/* Logo */}
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

        <h1 className="text-title" style={{ marginBottom: '0.375rem' }}>Welcome back</h1>
        <p className="text-small" style={{ color: 'var(--text-secondary)', marginBottom: '1.75rem' }}>
          Sign in to your account to continue.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email}
              onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
          </div>

          <div>
            <label className="label" htmlFor="password">Password</label>
            <div style={{ position: 'relative' }}>
              <input id="password" type={showPwd ? 'text' : 'password'} className="input"
                value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" required style={{ paddingRight: '2.75rem' }} />
              <button type="button" onClick={() => setShowPwd(!showPwd)} style={{
                position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0,
              }}>
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <p style={{ color: '#E05555', fontSize: '0.8125rem', margin: 0 }}>{error}</p>
          )}

          <button type="submit" className="btn btn-primary" disabled={loading}
            style={{ marginTop: '0.5rem', height: 42 }}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="text-small" style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
          Don&apos;t have an account?{' '}
          <Link href="/register" style={{ color: 'var(--gold)', textDecoration: 'none', fontWeight: 500 }}>
            Register
          </Link>
        </p>
      </div>
    </main>
  )
}
