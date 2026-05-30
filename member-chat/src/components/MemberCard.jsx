import { motion } from 'motion/react'

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function daysUntil(dateStr) {
  if (!dateStr) return null
  const now = new Date(); now.setHours(0, 0, 0, 0)
  const exp = new Date(dateStr); exp.setHours(0, 0, 0, 0)
  return Math.floor((exp - now) / 86400000)
}

function expiryColor(days) {
  if (days === null) return { color: '#6b7280', bg: 'rgba(107,114,128,0.15)', border: 'rgba(107,114,128,0.2)' }
  if (days < 0)  return { color: '#f87171', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.2)' }
  if (days <= 7) return { color: '#f87171', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.2)' }
  if (days <= 30) return { color: '#fbbf24', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.2)' }
  return { color: '#4ade80', bg: 'rgba(34,197,94,0.12)', border: 'rgba(34,197,94,0.2)' }
}

function expiryLabel(days) {
  if (days === null) return 'Unknown'
  if (days < 0) return `Expired ${Math.abs(days)}d ago`
  if (days === 0) return 'Expires today!'
  if (days === 1) return '1 day left'
  return `${days} days left`
}

const statVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: i => ({ opacity: 1, y: 0, transition: { delay: 0.1 + i * 0.08, duration: 0.35, ease: [0.23,1,0.32,1] } }),
}

export default function MemberCard({ profile }) {
  if (!profile) {
    return (
      <div style={{ margin: '12px 12px 0', borderRadius: '16px', padding: '20px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ height: '18px', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', width: '55%', marginBottom: '10px', animation: 'pulse 1.5s infinite' }} />
        <div style={{ height: '13px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', width: '35%' }} />
      </div>
    )
  }

  const days = daysUntil(profile.membership_expiry)
  const expStyle = expiryColor(days)
  const isActive = profile.status === 'Active'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      style={{
        margin: '12px 12px 0',
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '16px',
        padding: '18px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle top gradient */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '1px',
        background: 'linear-gradient(90deg, transparent, rgba(249,115,22,0.4), transparent)',
      }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '17px', fontWeight: '700', color: '#f9fafb', letterSpacing: '-0.02em' }}>{profile.name}</div>
          <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '2px' }}>{profile.service_plan || 'Gym Member'}</div>
        </div>
        <span style={{
          fontSize: '12px', fontWeight: '600',
          color: isActive ? '#4ade80' : '#6b7280',
          background: isActive ? 'rgba(34,197,94,0.12)' : 'rgba(107,114,128,0.12)',
          border: `1px solid ${isActive ? 'rgba(34,197,94,0.25)' : 'rgba(107,114,128,0.2)'}`,
          borderRadius: '20px', padding: '3px 10px',
        }}>
          {profile.status}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '0', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '14px' }}>
        {[
          {
            label: 'Membership',
            value: <span style={{ fontSize: '12px', fontWeight: '600', color: expStyle.color, background: expStyle.bg, border: `1px solid ${expStyle.border}`, borderRadius: '6px', padding: '2px 8px' }}>{expiryLabel(days)}</span>,
          },
          {
            label: 'Last Visit',
            value: <span style={{ fontSize: '14px', fontWeight: '500', color: '#d1d5db' }}>{formatDate(profile.last_checkin)}</span>,
          },
          {
            label: 'Total Visits',
            value: <span style={{ fontSize: '20px', fontWeight: '800', color: '#f97316', letterSpacing: '-0.03em' }}>{profile.total_checkins ?? 0}</span>,
          },
        ].map((stat, i) => (
          <motion.div key={stat.label} custom={i} variants={statVariants} initial="hidden" animate="visible" style={{ flex: 1 }}>
            <div style={{ fontSize: '10px', fontWeight: '700', color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '5px' }}>{stat.label}</div>
            {stat.value}
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}
