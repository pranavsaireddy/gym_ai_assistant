import { motion } from 'motion/react'

export default function AttendanceStrip({ attendance }) {
  const today = new Date()
  const presentDates = new Set((attendance || []).map(a => a.date))

  const days = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() - (29 - i))
    const key = d.toISOString().split('T')[0]
    return { key, isToday: i === 29, present: presentDates.has(key), index: i }
  })

  const presentCount = days.filter(d => d.present).length
  const pct = Math.round((presentCount / 30) * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      style={{
        margin: '10px 12px 0',
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '16px',
        padding: '16px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <span style={{ fontSize: '13px', fontWeight: '600', color: '#9ca3af' }}>Last 30 Days</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: '700', color: '#f97316' }}>{presentCount}/30</span>
          <span style={{
            fontSize: '11px', fontWeight: '600',
            color: pct >= 60 ? '#4ade80' : pct >= 30 ? '#fbbf24' : '#f87171',
            background: pct >= 60 ? 'rgba(34,197,94,0.12)' : pct >= 30 ? 'rgba(245,158,11,0.12)' : 'rgba(239,68,68,0.12)',
            border: `1px solid ${pct >= 60 ? 'rgba(34,197,94,0.2)' : pct >= 30 ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)'}`,
            borderRadius: '10px', padding: '1px 7px',
          }}>
            {pct}%
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '3px', alignItems: 'flex-end' }}>
        {days.map(({ key, isToday, present, index }) => (
          <motion.div
            key={key}
            title={key}
            initial={{ scaleY: 0, opacity: 0 }}
            animate={{ scaleY: 1, opacity: 1 }}
            transition={{ delay: index * 0.012, duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
            style={{
              flex: 1,
              height: present ? '22px' : '14px',
              borderRadius: '3px',
              background: present
                ? isToday
                  ? '#f97316'
                  : 'rgba(249,115,22,0.7)'
                : 'rgba(255,255,255,0.06)',
              border: isToday ? '1.5px solid rgba(249,115,22,0.8)' : '1px solid transparent',
              boxShadow: present && isToday ? '0 0 8px rgba(249,115,22,0.5)' : 'none',
              transformOrigin: 'bottom',
              minWidth: 0,
              transition: 'height 0.3s ease',
            }}
          />
        ))}
      </div>

      <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: 'rgba(249,115,22,0.7)' }} />
          <span style={{ fontSize: '11px', color: '#6b7280' }}>Present</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }} />
          <span style={{ fontSize: '11px', color: '#6b7280' }}>Absent</span>
        </div>
      </div>
    </motion.div>
  )
}
