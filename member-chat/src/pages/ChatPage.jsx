import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'motion/react'
import { LogOut, Send, Dumbbell } from 'lucide-react'
import { getProfile, getAttendance, sendChat } from '../api/client'
import MemberCard from '../components/MemberCard'
import AttendanceStrip from '../components/AttendanceStrip'
import ChatBubble from '../components/ChatBubble'
import TypingIndicator from '../components/TypingIndicator'
import QuickReplies from '../components/QuickReplies'

export default function ChatPage() {
  const navigate = useNavigate()
  const memberName = localStorage.getItem('gym_member_name') || 'there'

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showQuickReplies, setShowQuickReplies] = useState(true)
  const [userTyped, setUserTyped] = useState(false)
  const [focused, setFocused] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: () => getProfile().then(r => r.data),
    retry: 1,
  })

  const { data: attendance } = useQuery({
    queryKey: ['attendance'],
    queryFn: () => getAttendance().then(r => r.data),
    retry: 1,
  })

  useEffect(() => {
    setMessages([{
      id: 'welcome',
      role: 'assistant',
      content: `Hey ${memberName}! I'm Milo, your AI coach at Muscletech. Ask me about your attendance, membership, diet, or workout tips.`,
      agent: 'general',
      timestamp: new Date().toISOString(),
    }])
  }, [memberName])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleLogout() {
    localStorage.removeItem('gym_token')
    localStorage.removeItem('gym_member_name')
    localStorage.removeItem('gym_member_id')
    navigate('/login')
  }

  async function handleSend(text) {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')
    setUserTyped(false)
    setShowQuickReplies(false)
    setMessages(prev => [...prev, { id: Date.now() + '-u', role: 'user', content: msg, timestamp: new Date().toISOString() }])
    setLoading(true)
    try {
      const res = await sendChat(msg)
      setMessages(prev => [...prev, { id: Date.now() + '-a', role: 'assistant', content: res.data.reply, agent: res.data.agent, timestamp: new Date().toISOString() }])
      setShowQuickReplies(true)
    } catch (err) {
      const errMsg = !err.response ? 'Cannot connect to server.' : err.response?.status === 500 ? 'Server error. Try again.' : 'Something went wrong.'
      setMessages(prev => [...prev, { id: Date.now() + '-err', role: 'assistant', content: errMsg, agent: 'general', timestamp: new Date().toISOString() }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function handleInputChange(e) {
    setInput(e.target.value)
    if (!userTyped && e.target.value.length > 0) { setUserTyped(true); setShowQuickReplies(false) }
    if (e.target.value.length === 0) { setUserTyped(false); setShowQuickReplies(true) }
  }

  const firstAiIdx = messages.findIndex(m => m.role === 'assistant')
  const canSend = input.trim() && !loading

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      maxWidth: '520px', margin: '0 auto',
      background: '#0d0d0f',
      position: 'relative',
    }}>
      {/* Background gradient */}
      <div style={{
        position: 'fixed', top: 0, left: '50%', transform: 'translateX(-50%)',
        width: '520px', height: '300px', pointerEvents: 'none', zIndex: 0,
        background: 'radial-gradient(ellipse at 50% 0%, rgba(249,115,22,0.1) 0%, transparent 70%)',
      }} />

      {/* ── Header ─────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px',
          background: 'rgba(13,13,15,0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          position: 'sticky', top: 0, zIndex: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(249,115,22,0.25), rgba(249,115,22,0.1))',
            border: '1px solid rgba(249,115,22,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px',
            boxShadow: '0 0 16px rgba(249,115,22,0.2)',
          }}>
            🤖
          </div>
          <div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#f9fafb', letterSpacing: '-0.02em' }}>Milo</div>
            <div style={{ fontSize: '12px', color: '#4b5563', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4ade80', display: 'inline-block', boxShadow: '0 0 6px rgba(74,222,128,0.6)' }} />
              Muscletech Fitness · AI Coach
            </div>
          </div>
        </div>
        <motion.button
          whileHover={{ scale: 1.05, background: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.3)', color: '#f87171' }}
          whileTap={{ scale: 0.95 }}
          onClick={handleLogout}
          style={{
            padding: '8px 10px', color: '#4b5563',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '10px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '13px', fontWeight: '500',
            transition: 'all 0.15s',
          }}
          title="Logout"
        >
          <LogOut size={15} />
          <span>Sign out</span>
        </motion.button>
      </motion.div>

      {/* ── Member info cards ───────────────────────────────────────── */}
      <div style={{ paddingBottom: '10px', position: 'relative', zIndex: 1 }}>
        <MemberCard profile={profile} />
        <AttendanceStrip attendance={attendance} />
      </div>

      {/* ── Section divider ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '4px 14px 8px', position: 'relative', zIndex: 1 }}>
        <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />
        <span style={{ fontSize: '11px', color: '#374151', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Dumbbell size={10} />
          Chat with Milo
        </span>
        <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />
      </div>

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', paddingTop: '4px', position: 'relative', zIndex: 1 }}>
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              isFirst={msg.role === 'assistant' && idx === firstAiIdx}
            />
          ))}
        </AnimatePresence>
        <AnimatePresence>
          {loading && <TypingIndicator key="typing" />}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* ── Input area ──────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
        style={{
          background: 'rgba(13,13,15,0.9)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(255,255,255,0.07)',
          position: 'relative', zIndex: 10,
        }}
      >
        <QuickReplies visible={showQuickReplies && !loading} onSelect={text => handleSend(text)} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px' }}>
          <div style={{
            flex: 1, position: 'relative',
            borderRadius: '14px',
            border: `1.5px solid ${focused ? 'rgba(249,115,22,0.5)' : 'rgba(255,255,255,0.08)'}`,
            background: focused ? 'rgba(249,115,22,0.04)' : 'rgba(255,255,255,0.04)',
            transition: 'all 0.2s',
            boxShadow: focused ? '0 0 0 4px rgba(249,115,22,0.08)' : 'none',
          }}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              disabled={loading}
              placeholder="Ask Milo anything..."
              style={{
                width: '100%', padding: '12px 16px',
                fontSize: '15px', border: 'none', outline: 'none',
                color: '#f1f5f9', background: 'transparent',
                fontFamily: 'inherit',
              }}
            />
          </div>

          <motion.button
            whileHover={canSend ? { scale: 1.08, boxShadow: '0 0 24px rgba(249,115,22,0.5)' } : {}}
            whileTap={canSend ? { scale: 0.92 } : {}}
            onClick={() => handleSend()}
            disabled={!canSend}
            style={{
              width: '44px', height: '44px', flexShrink: 0,
              background: canSend ? 'linear-gradient(135deg, #f97316, #ea580c)' : 'rgba(255,255,255,0.06)',
              color: canSend ? '#fff' : '#374151',
              border: 'none', borderRadius: '12px',
              cursor: canSend ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s',
              boxShadow: canSend ? '0 4px 16px rgba(249,115,22,0.3)' : 'none',
            }}
          >
            {loading
              ? <SpinnerIcon />
              : <Send size={17} />
            }
          </motion.button>
        </div>
      </motion.div>
    </div>
  )
}

function SpinnerIcon() {
  return (
    <motion.svg
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      style={{ width: '18px', height: '18px' }}
      viewBox="0 0 24 24" fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.25)" strokeWidth="3" />
      <path fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </motion.svg>
  )
}
