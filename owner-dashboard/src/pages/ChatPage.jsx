import { useState, useEffect, useRef } from 'react'
import { Send } from 'lucide-react'
import { sendChat } from '../api/client'

const QUICK = [
  'How many members are active?',
  'Who are the top dropout risks?',
  'Revenue this month?',
  'How many expire this week?',
  'Members not seen in 14 days?',
]

const AGENT_BADGE = {
  attendance: { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
  membership:  { bg: '#fffbeb', color: '#92400e', border: '#fde68a' },
  diet:        { bg: '#f0fdf4', color: '#166534', border: '#bbf7d0' },
  analytics:   { bg: '#fdf2f8', color: '#9d174d', border: '#fbcfe8' },
  occupancy:   { bg: '#ecfeff', color: '#155e75', border: '#a5f3fc' },
  general:     { bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb' },
}

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
}

export default function ChatPage() {
  const staffName = localStorage.getItem('staff_name') || 'Owner'
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showQuick, setShowQuick] = useState(true)
  const [userTyped, setUserTyped] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    setMessages([{ id: 'welcome', role: 'assistant', content: `Hey ${staffName}! I'm Milo. Ask me anything about gym performance, member stats, revenue, or dropout risk. 📊`, agent: 'analytics', timestamp: new Date().toISOString() }])
  }, [staffName])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  async function handleSend(text) {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput(''); setUserTyped(false); setShowQuick(false)
    setMessages(prev => [...prev, { id: Date.now() + '-u', role: 'user', content: msg, timestamp: new Date().toISOString() }])
    setLoading(true)
    try {
      const res = await sendChat(msg)
      setMessages(prev => [...prev, { id: Date.now() + '-a', role: 'assistant', content: res.data.reply, agent: res.data.agent, timestamp: new Date().toISOString() }])
      setShowQuick(true)
    } catch {
      setMessages(prev => [...prev, { id: Date.now() + '-err', role: 'assistant', content: 'Something went wrong. Try again.', agent: 'general', timestamp: new Date().toISOString() }])
    } finally { setLoading(false) }
  }

  function handleKeyDown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }
  function handleInputChange(e) {
    setInput(e.target.value)
    if (!userTyped && e.target.value.length > 0) { setUserTyped(true); setShowQuick(false) }
    if (e.target.value.length === 0) { setUserTyped(false); setShowQuick(true) }
  }

  const firstAiIdx = messages.findIndex(m => m.role === 'assistant')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Header */}
      <div style={{ padding: '18px 28px', borderBottom: '1px solid #e5e7eb', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '42px', height: '42px', background: '#fff7ed', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '22px', border: '1px solid #fed7aa' }}>🤖</div>
          <div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#111827' }}>Milo — Analytics Chat</div>
            <div style={{ fontSize: '13px', color: '#6b7280' }}>Ask about gym stats, members, revenue, dropout risk</div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 28px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {messages.map((msg, idx) => {
          const isUser = msg.role === 'user'
          const agentKey = (msg.agent || 'general').split(',')[0].trim().toLowerCase()
          const badge = AGENT_BADGE[agentKey] || AGENT_BADGE.general

          return (
            <div key={msg.id} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: '8px' }}>
              <div style={{ maxWidth: '72%' }}>
                {!isUser && idx === firstAiIdx && (
                  <div style={{ fontSize: '12px', fontWeight: '600', color: '#f97316', marginBottom: '5px' }}>Milo 🤖</div>
                )}
                <div style={{
                  padding: '12px 16px', borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                  fontSize: '15px', lineHeight: '1.6', whiteSpace: 'pre-wrap',
                  background: isUser ? '#f97316' : '#fff',
                  color: isUser ? '#fff' : '#1f2937',
                  border: isUser ? 'none' : '1px solid #e5e7eb',
                  boxShadow: isUser ? '0 1px 3px rgba(249,115,22,0.25)' : '0 1px 3px rgba(0,0,0,0.06)',
                }}>
                  {msg.content}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                  {!isUser && msg.agent && (
                    <span style={{ fontSize: '11px', fontWeight: '600', color: badge.color, background: badge.bg, border: `1px solid ${badge.border}`, borderRadius: '20px', padding: '1px 8px' }}>{agentKey}</span>
                  )}
                  <span style={{ fontSize: '11px', color: '#9ca3af' }}>{formatTime(msg.timestamp)}</span>
                </div>
              </div>
            </div>
          )
        })}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '8px' }}>
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', padding: '12px 18px', borderRadius: '18px 18px 18px 4px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: '5px' }}>
              {[0, 150, 300].map(d => <span key={d} style={{ width: '8px', height: '8px', background: '#d1d5db', borderRadius: '50%', display: 'inline-block', animation: 'bounce 1s infinite', animationDelay: `${d}ms` }} />)}
              <style>{`@keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }`}</style>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ background: '#fff', borderTop: '1px solid #e5e7eb', padding: '16px 28px', boxShadow: '0 -1px 6px rgba(0,0,0,0.04)' }}>
        {showQuick && !loading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
            {QUICK.map(s => (
              <button key={s} onClick={() => handleSend(s)}
                style={{ fontSize: '13px', fontWeight: '500', color: '#f97316', background: '#fff7ed', border: '1.5px solid #fed7aa', borderRadius: '20px', padding: '6px 14px', cursor: 'pointer', transition: 'all 0.15s' }}
                onMouseEnter={e => { e.target.style.background = '#fff'; e.target.style.borderColor = '#f97316' }}
                onMouseLeave={e => { e.target.style.background = '#fff7ed'; e.target.style.borderColor = '#fed7aa' }}>
                {s}
              </button>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input
            type="text" value={input} onChange={handleInputChange} onKeyDown={handleKeyDown} disabled={loading}
            placeholder="Ask Milo about gym stats..."
            style={{ flex: 1, padding: '11px 16px', fontSize: '15px', border: '1.5px solid #e5e7eb', borderRadius: '12px', outline: 'none', color: '#111827', background: '#f9fafb', transition: 'border-color 0.15s' }}
            onFocus={e => e.target.style.borderColor = '#f97316'}
            onBlur={e => e.target.style.borderColor = '#e5e7eb'}
          />
          <button
            onClick={() => handleSend()} disabled={loading || !input.trim()}
            style={{ width: '46px', height: '46px', background: input.trim() && !loading ? '#f97316' : '#e5e7eb', color: input.trim() && !loading ? '#fff' : '#9ca3af', border: 'none', borderRadius: '12px', cursor: input.trim() && !loading ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s', flexShrink: 0 }}>
            {loading ? (
              <svg style={{ animation: 'spin 1s linear infinite', width: '18px', height: '18px' }} viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.3" />
                <path fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  )
}
