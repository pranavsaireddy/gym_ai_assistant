import { motion } from 'motion/react'

const AGENT_BADGE = {
  attendance: { bg: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: 'rgba(59,130,246,0.25)' },
  membership: { bg: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: 'rgba(245,158,11,0.25)' },
  diet:       { bg: 'rgba(34,197,94,0.15)',  color: '#4ade80', border: 'rgba(34,197,94,0.25)'  },
  fitness:    { bg: 'rgba(168,85,247,0.15)', color: '#c084fc', border: 'rgba(168,85,247,0.25)' },
  analytics:  { bg: 'rgba(236,72,153,0.15)', color: '#f472b6', border: 'rgba(236,72,153,0.25)' },
  occupancy:  { bg: 'rgba(6,182,212,0.15)',  color: '#22d3ee', border: 'rgba(6,182,212,0.25)'  },
  general:    { bg: 'rgba(255,255,255,0.06)', color: '#9ca3af', border: 'rgba(255,255,255,0.1)' },
}

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
}

export default function ChatBubble({ message, isFirst }) {
  const isUser = message.role === 'user'
  const agentKey = (message.agent || 'general').split(',')[0].trim().toLowerCase()
  const badge = AGENT_BADGE[agentKey] || AGENT_BADGE.general

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 20, scale: 0.95 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
        style={{ display: 'flex', justifyContent: 'flex-end', padding: '3px 14px', marginBottom: '4px' }}
      >
        <div style={{ maxWidth: '78%' }}>
          <div style={{
            background: 'linear-gradient(135deg, #f97316, #ea580c)',
            color: '#fff',
            padding: '11px 16px',
            borderRadius: '18px 18px 4px 18px',
            fontSize: '15px', lineHeight: '1.55',
            boxShadow: '0 4px 20px rgba(249,115,22,0.35)',
            fontWeight: '450',
          }}>
            {message.content}
          </div>
          <div style={{ fontSize: '11px', color: '#4b5563', textAlign: 'right', marginTop: '4px', paddingRight: '2px' }}>
            {formatTime(message.timestamp)}
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
      style={{ display: 'flex', justifyContent: 'flex-start', padding: '3px 14px', marginBottom: '4px' }}
    >
      <div style={{ maxWidth: '84%' }}>
        {isFirst && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            style={{ fontSize: '12px', fontWeight: '700', color: '#f97316', marginBottom: '5px', paddingLeft: '2px', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            Milo · AI Coach
          </motion.div>
        )}
        <div style={{
          background: 'rgba(255,255,255,0.06)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.09)',
          color: '#f1f5f9',
          padding: '12px 16px',
          borderRadius: '18px 18px 18px 4px',
          fontSize: '15px', lineHeight: '1.65',
          boxShadow: '0 2px 12px rgba(0,0,0,0.3)',
          whiteSpace: 'pre-wrap',
        }}>
          {message.content}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px', paddingLeft: '2px' }}>
          {message.agent && agentKey !== 'general' && (
            <span style={{
              fontSize: '11px', fontWeight: '600',
              color: badge.color,
              background: badge.bg,
              border: `1px solid ${badge.border}`,
              borderRadius: '20px', padding: '1px 8px',
            }}>
              {agentKey}
            </span>
          )}
          <span style={{ fontSize: '11px', color: '#4b5563' }}>{formatTime(message.timestamp)}</span>
        </div>
      </div>
    </motion.div>
  )
}
