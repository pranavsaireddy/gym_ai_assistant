import { motion } from 'motion/react'

export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, x: -12, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.25, ease: [0.23, 1, 0.32, 1] }}
      style={{ display: 'flex', justifyContent: 'flex-start', padding: '3px 14px', marginBottom: '6px' }}
    >
      <div style={{
        background: 'rgba(255,255,255,0.06)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.09)',
        padding: '14px 18px',
        borderRadius: '18px 18px 18px 4px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.3)',
        display: 'flex', alignItems: 'center', gap: '5px',
      }}>
        {[0, 1, 2].map(i => (
          <motion.span
            key={i}
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
            style={{
              width: '7px', height: '7px',
              background: '#f97316',
              borderRadius: '50%',
              display: 'inline-block',
              opacity: 0.85,
            }}
          />
        ))}
      </div>
    </motion.div>
  )
}
