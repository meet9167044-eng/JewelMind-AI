'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'

interface AuthUser { user_id: number; email: string; full_name: string }

export function useAuth() {
  const router = useRouter()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('jewelmind_token')
    if (!token) { setLoading(false); return }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      localStorage.removeItem('jewelmind_token')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadUser() }, [loadUser])

  const logout = () => {
    localStorage.removeItem('jewelmind_token')
    setUser(null)
    router.push('/login')
  }

  return { user, loading, logout, refetch: loadUser }
}

export function requireAuth() {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('jewelmind_token')
    if (!token) window.location.href = '/login'
  }
}
