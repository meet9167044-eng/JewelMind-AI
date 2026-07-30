'use client'
import { useState } from 'react'
import { useParams } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import { Bot, Send, User, Sparkles, FileText } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  evidence?: { tool: string; result: any }
}

export default function CopilotPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I am your JewelMind AI Copilot. Ask me anything about your revenue, profit variance, inventory ageing, or metal exposure float.',
    },
  ])
  const [thinking, setThinking] = useState(false)

  const handleSend = () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setThinking(true)

    // Phase 14 mock / preview interaction until Phase 14 LLM integration
    setTimeout(() => {
      let reply = "I analyzed your latest business metrics for this business."
      let evidenceData = null

      if (userMsg.toLowerCase().includes('profit') || userMsg.toLowerCase().includes('margin')) {
        reply = "In June 2026, your gross profit increased by ₹12.5k. The primary positive driver was Making Charge rate improvement (+₹15.0k), offset slightly by Product Mix shifts."
        evidenceData = { tool: "get_profit_diagnosis", result: { target_profit: 65000, baseline_profit: 52500, delta: 12500 } }
      } else if (userMsg.toLowerCase().includes('inventory') || userMsg.toLowerCase().includes('dead')) {
        reply = "You currently have 17 items classified as Dead Stock (>180 days old with zero sales in the last 90 days), representing ~150.5g of gold inventory."
        evidenceData = { tool: "get_inventory_performance", result: { dead_stock_count: 17, total_weight: 150.5 } }
      } else if (userMsg.toLowerCase().includes('metal') || userMsg.toLowerCase().includes('gold')) {
        reply = "Your Gold Weighted Acquisition Rate (WAR) is ₹6,200/g. At today's board rate of ₹7,200/g, your paper valuation exposure is positive (+₹100.0k above cost basis)."
        evidenceData = { tool: "get_metal_exposure", result: { metal: "gold", war: 6200, current_rate: 7200 } }
      }

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: reply, evidence: evidenceData || undefined },
      ])
      setThinking(false)
    }, 1000)
  }

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--topbar-h) - 4rem)' }}>
      <PageHeader
        badge="AI Assistant"
        title="AI Copilot"
        description="Ask natural questions about your business. Every answer is backed by deterministic Python analytics with View Evidence audit trail."
      />

      {/* Chat Area */}
      <div className="card dot-matrix-subtle" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '1.25rem' }}>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', paddingRight: '0.5rem' }}>
          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              {m.role === 'assistant' && (
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Bot size={18} color="var(--gold)" />
                </div>
              )}
              <div style={{
                maxWidth: '75%', padding: '0.875rem 1.125rem', borderRadius: 'var(--radius-md)',
                background: m.role === 'user' ? 'var(--gold-dim)' : 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: '0.875rem'
              }}>
                <p style={{ margin: 0 }}>{m.content}</p>
                {m.evidence && (
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <FileText size={12} color="var(--gold)" />
                    <span className="text-xs text-gold" style={{ cursor: 'pointer' }}>
                      View Evidence ({m.evidence.tool})
                    </span>
                  </div>
                )}
              </div>
              {m.role === 'user' && (
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <User size={18} color="var(--text-primary)" />
                </div>
              )}
            </div>
          ))}

          {thinking && (
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--gold-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Sparkles size={16} color="var(--gold)" />
              </div>
              <span className="text-small text-muted">Analyzing business metrics…</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
          <input
            className="input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about profit, inventory, or metal risk…"
            onKeyDown={e => e.key === 'Enter' && handleSend()}
          />
          <button className="btn btn-primary" onClick={handleSend} disabled={!input.trim() || thinking}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
