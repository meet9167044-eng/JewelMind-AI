'use client'
import { useState } from 'react'
import { ChevronDown, LogOut, User, Building2 } from 'lucide-react'
import Link from 'next/link'

interface Props {
  userName: string
  bizName: string
  onLogout: () => void
}

export default function TopBar({ userName, bizName, onLogout }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <header style={{
      position: 'fixed', top: 0, right: 0, left: 'var(--sidebar-w)',
      height: 'var(--topbar-h)', zIndex: 30,
      background: 'rgba(11,11,12,0.88)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 1.75rem',
      transition: 'left 0.2s ease',
    }}>
      {/* Business name badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Building2 size={14} color="var(--gold)" />
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
          {bizName}
        </span>
      </div>

      {/* User menu */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setOpen(!open)}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-pill)', padding: '0.375rem 0.875rem',
            cursor: 'pointer', color: 'var(--text-primary)', fontSize: '0.8125rem',
            transition: 'background 0.15s',
          }}
        >
          <div style={{
            width: 22, height: 22, borderRadius: '50%',
            background: 'linear-gradient(135deg, #C9A227, #8B6A10)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.6875rem', fontWeight: 700, color: '#0B0B0C',
          }}>
            {userName.charAt(0).toUpperCase()}
          </div>
          <span>{userName.split(' ')[0]}</span>
          <ChevronDown size={13} color="var(--text-secondary)" />
        </button>

        {open && (
          <div className="glass" style={{
            position: 'absolute', right: 0, top: 'calc(100% + 0.5rem)',
            borderRadius: 'var(--radius-md)', minWidth: 180, overflow: 'hidden',
            animation: 'fadeUp 0.15s ease both',
          }}>
            <div style={{ padding: '0.75rem 1rem 0.5rem', borderBottom: '1px solid var(--border)' }}>
              <p style={{ margin: 0, fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-primary)' }}>{userName}</p>
            </div>
            <Link href="/businesses" style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '0.6rem 1rem',
              color: 'var(--text-secondary)', fontSize: '0.8125rem', textDecoration: 'none',
            }}
              onClick={() => setOpen(false)}>
              <Building2 size={14} /> Switch Business
            </Link>
            <button onClick={onLogout} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '0.6rem 1rem',
              width: '100%', border: 'none', background: 'none', color: '#E05555',
              fontSize: '0.8125rem', cursor: 'pointer', textAlign: 'left',
            }}>
              <LogOut size={14} /> Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
