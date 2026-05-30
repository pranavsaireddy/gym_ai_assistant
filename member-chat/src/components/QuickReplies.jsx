import { motion, AnimatePresence } from 'motion/react'

const SUGGESTIONS = [
  { text: 'My visits this month?', icon: '📅' },
  { text: 'When does my membership expire?', icon: '🎫' },
  { text: 'What to eat before workout?', icon: '🥗' },
  { text: 'Am I regular this month?', icon: '📊' },
  { text: 'How many people in gym now?', icon: '👥' },
]

export default function QuickReplies({ onSelect, visible }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25, ease: [0.23, 1, 0.32, 1] }}
          style={{ overflow: 'hidden' }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '7px', padding: '10px 14px 6px' }}>
            {SUGGESTIONS.map((s, i) => (
              <motion.button
                key={s.text}
                initial={{ opacity: 0, scale: 0.85, y: 6 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
                whileHover={{ scale: 1.04, background: 'rgba(249,115,22,0.15)', borderColor: 'rgba(249,115,22,0.5)' }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onSelect(s.text)}
                style={{
                  fontSize: '13px', fontWeight: '500',
                  color: '#f97316',
                  background: 'rgba(249,115,22,0.08)',
                  border: '1px solid rgba(249,115,22,0.2)',
                  borderRadius: '20px', padding: '6px 13px',
                  cursor: 'pointer', whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: '5px',
                  transition: 'background 0.15s, border-color 0.15s',
                }}
              >
                <span style={{ fontSize: '12px' }}>{s.icon}</span>
                {s.text}
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
