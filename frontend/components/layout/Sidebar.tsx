'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, TrendingUp, Package, Gem, Activity,
  Lightbulb, Upload, Bot, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { label: 'Dashboard',     href: 'dashboard',  icon: LayoutDashboard },
  { label: 'Profit',        href: 'profit',     icon: TrendingUp       },
  { label: 'Inventory',     href: 'inventory',  icon: Package          },
  { label: 'Metal',         href: 'metal',      icon: Gem              },
  { label: 'Simulator',     href: 'simulator',  icon: Activity         },
  { label: 'Insights',      href: 'insights',   icon: Lightbulb        },
  { label: 'Upload',        href: 'upload',     icon: Upload           },
  { label: 'AI Copilot',    href: 'copilot',    icon: Bot              },
]

interface Props { bizId: number; collapsed: boolean; onToggle: () => void }

export default function Sidebar({ bizId, collapsed, onToggle }: Props) {
  const pathname = usePathname()

  return (
    <nav className={clsx('sidebar', collapsed && 'collapsed')}>
      {/* Logo */}
      <div style={{ padding: '1.25rem 1rem 1rem', display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'linear-gradient(135deg, #C9A227, #8B6A10)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 700, color: '#0B0B0C', flexShrink: 0,
        }}>J</div>
        {!collapsed && (
          <span style={{ fontFamily: "'Playfair Display', serif", fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            JewelMind
          </span>
        )}
      </div>

      <hr className="divider" style={{ margin: '0 0 0.75rem' }} />

      {/* Nav items */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.125rem', padding: '0 0 1rem' }}>
        {NAV.map(({ label, href, icon: Icon }) => {
          const fullHref = `/businesses/${bizId}/${href}`
          const active = pathname === fullHref || pathname.startsWith(fullHref + '/')
          return (
            <Link
              key={href}
              href={fullHref}
              className={clsx('sidebar-item', active && 'active')}
              title={collapsed ? label : undefined}
            >
              <Icon className="icon" size={18} />
              {!collapsed && <span>{label}</span>}
            </Link>
          )
        })}
      </div>

      {/* Collapse toggle */}
      <div style={{ padding: '0 0.5rem 1.25rem' }}>
        <button
          onClick={onToggle}
          className="sidebar-item"
          style={{ width: '100%', border: 'none', background: 'none', cursor: 'pointer' }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span style={{ fontSize: '0.8125rem' }}>Collapse</span></>}
        </button>
      </div>
    </nav>
  )
}
