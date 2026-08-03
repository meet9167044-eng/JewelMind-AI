'use client'
import { useState, useEffect, useRef } from 'react'
import { useParams } from 'next/navigation'
import PageHeader from '@/components/ui/PageHeader'
import ViewEvidenceModal from '@/components/copilot/ViewEvidenceModal'
import { api } from '@/lib/api'
import { Bot, Send, User, Sparkles, FileText, RefreshCw, Clock } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  evidence?: any
  isQuotaError?: boolean
}

const QUOTA_KEYWORDS = ['quota exceeded', 'Quota Exceeded', 'rate limit', 'RESOURCE_EXHAUSTED', '429']
const isQuotaError = (content: string) => QUOTA_KEYWORDS.some(k => content.includes(k))

export default function CopilotPage() {
  const { business_id } = useParams()
  const bizId = Number(business_id)

  const [input, setInput] = useState('')
  const [lastQuestion, setLastQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I am your JewelMind AI Copilot. Ask me anything about your revenue, profit variance, inventory ageing, or metal exposure float.',
    },
  ])
  const [thinking, setThinking] = useState(false)
  const [selectedEvidence, setSelectedEvidence] = useState<any>(null)
  const [retryCountdown, setRetryCountdown] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  // Countdown timer for quota retry
  useEffect(() => {
    if (retryCountdown <= 0) return
    const t = setTimeout(() => setRetryCountdown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [retryCountdown])

  const sendQuestion = async (question: string) => {
    if (!question.trim() || thinking) return
    setLastQuestion(question)
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setThinking(true)

    try {
      const res = await api.post<{ response_text: string; evidence: any }>(
        `/api/businesses/${bizId}/copilot/ask`,
        { question }
      )
      const quotaHit = isQuotaError(res.response_text)
      if (quotaHit) setRetryCountdown(90)   // suggest retrying after 90s
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.response_text,
          evidence: res.evidence,
          isQuotaError: quotaHit,
        },
      ])
    } catch (e: any) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Sorry, I encountered an error: ${e.message}` },
      ])
    } finally {
      setThinking(false)
    }
  }

  const handleSend = () => {
    const q = input.trim()
    setInput('')
    sendQuestion(q)
  }

  const handleRetry = () => {
    if (retryCountdown > 0 || !lastQuestion) return
    sendQuestion(lastQuestion)
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
                background: m.role === 'user'
                  ? 'var(--gold-dim)'
                  : m.isQuotaError
                    ? 'rgba(255,140,0,0.06)'
                    : 'rgba(255,255,255,0.03)',
                border: `1px solid ${m.isQuotaError ? 'rgba(255,140,0,0.35)' : 'var(--border)'}`,
                color: 'var(--text-primary)', fontSize: '0.875rem'
              }}>
                <p style={{ margin: 0 }}>{m.content}</p>

                {/* Quota error: show retry button with countdown */}
                {m.isQuotaError && i === messages.length - 1 && (
                  <div style={{ marginTop: '0.875rem', paddingTop: '0.625rem', borderTop: '1px solid rgba(255,140,0,0.2)', display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={handleRetry}
                      disabled={retryCountdown > 0 || thinking}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.375rem',
                        fontSize: '0.75rem', padding: '0.35rem 0.875rem',
                        borderRadius: 6, border: '1px solid var(--gold)',
                        background: retryCountdown > 0 ? 'transparent' : 'var(--gold-dim)',
                        color: retryCountdown > 0 ? 'var(--text-muted)' : 'var(--gold)',
                        cursor: retryCountdown > 0 ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                      }}
                    >
                      {retryCountdown > 0
                        ? <><Clock size={12} /> Retry in {retryCountdown}s</>
                        : <><RefreshCw size={12} /> Retry question</>
                      }
                    </button>
                    {retryCountdown > 0 && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        Free-tier quota resets every minute
                      </span>
                    )}
                  </div>
                )}

                {/* Evidence link */}
                {m.evidence && (
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <FileText size={12} color="var(--gold)" />
                    <button
                      onClick={() => setSelectedEvidence(m.evidence)}
                      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
                      className="text-xs text-gold"
                    >
                      View Evidence ({m.evidence.tool})
                    </button>
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
          <div ref={bottomRef} />
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

      {/* Evidence Modal */}
      <ViewEvidenceModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
    </div>
  )
}
