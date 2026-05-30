import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import { login } from '../api/client'

export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [focusedField, setFocusedField] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await login(username.trim(), password)
      localStorage.setItem('gym_token', res.data.access_token)
      localStorage.setItem('gym_member_name', res.data.member_name)
      localStorage.setItem('gym_member_id', res.data.member_id)
      navigate('/chat')
    } catch (err) {
      if (err.response?.status === 401) setError('Invalid username or password.')
      else if (!err.response) setError('Cannot connect to server. Try again.')
      else setError('Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0d0d0f',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glow orbs */}
      <div style={{
        position: 'absolute', top: '-10%', left: '50%', transform: 'translateX(-50%)',
        width: '600px', height: '600px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(249,115,22,0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: '-20%', left: '10%',
        width: '400px', height: '400px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(249,115,22,0.06) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <motion.div
        initial={{ opacity: 0, y: 32, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
        style={{ width: '100%', maxWidth: '400px', position: 'relative', zIndex: 1 }}
      >
        {/* Logo mark */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <motion.div
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '64px', height: '64px', borderRadius: '20px',
              background: 'linear-gradient(135deg, rgba(249,115,22,0.2), rgba(249,115,22,0.08))',
              border: '1px solid rgba(249,115,22,0.3)',
              marginBottom: '18px',
              boxShadow: '0 0 30px rgba(249,115,22,0.2), inset 0 1px 0 rgba(255,255,255,0.1)',
            }}
          >
            <span style={{ fontSize: '32px' }}>🏋️</span>
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.4 }}
            style={{ fontSize: '24px', fontWeight: '800', color: '#f9fafb', marginBottom: '6px', letterSpacing: '-0.02em' }}
          >
            Muscletech Fitness
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32, duration: 0.4 }}
            style={{ fontSize: '14px', color: '#6b7280' }}
          >
            Sign in to chat with Milo, your AI coach
          </motion.p>
        </div>

        {/* Card */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
          style={{
            background: 'rgba(255,255,255,0.04)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '20px',
            padding: '32px',
            boxShadow: '0 24px 64px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
          }}
        >
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -8, height: 0 }}
                transition={{ duration: 0.25 }}
                style={{
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
                  borderRadius: '12px', padding: '12px 16px', marginBottom: '20px',
                  fontSize: '14px', color: '#f87171', overflow: 'hidden',
                }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit}>
            {/* Username */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#9ca3af', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Username
              </label>
              <motion.input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                onFocus={() => setFocusedField('username')}
                onBlur={() => setFocusedField(null)}
                placeholder="e.g. pranavsa7500"
                autoComplete="username"
                style={{
                  width: '100%', padding: '13px 16px', fontSize: '15px',
                  border: `1.5px solid ${focusedField === 'username' ? 'rgba(249,115,22,0.6)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: '12px', outline: 'none',
                  color: '#f9fafb',
                  background: focusedField === 'username' ? 'rgba(249,115,22,0.05)' : 'rgba(255,255,255,0.04)',
                  transition: 'all 0.2s',
                  boxShadow: focusedField === 'username' ? '0 0 0 4px rgba(249,115,22,0.1)' : 'none',
                }}
              />
            </div>

            {/* Password */}
            <div style={{ marginBottom: '28px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#9ca3af', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Password
              </label>
              <motion.input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                placeholder="Your password"
                autoComplete="current-password"
                style={{
                  width: '100%', padding: '13px 16px', fontSize: '15px',
                  border: `1.5px solid ${focusedField === 'password' ? 'rgba(249,115,22,0.6)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: '12px', outline: 'none',
                  color: '#f9fafb',
                  background: focusedField === 'password' ? 'rgba(249,115,22,0.05)' : 'rgba(255,255,255,0.04)',
                  transition: 'all 0.2s',
                  boxShadow: focusedField === 'password' ? '0 0 0 4px rgba(249,115,22,0.1)' : 'none',
                }}
              />
            </div>

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={!loading ? { scale: 1.02, boxShadow: '0 0 30px rgba(249,115,22,0.4)' } : {}}
              whileTap={!loading ? { scale: 0.97 } : {}}
              style={{
                width: '100%', padding: '14px', fontSize: '15px', fontWeight: '700',
                color: '#fff',
                background: loading
                  ? 'rgba(249,115,22,0.4)'
                  : 'linear-gradient(135deg, #f97316, #ea580c)',
                border: 'none', borderRadius: '12px',
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                boxShadow: loading ? 'none' : '0 4px 20px rgba(249,115,22,0.3)',
                letterSpacing: '-0.01em',
              }}
            >
              {loading ? (
                <>
                  <LoadingSpinner />
                  Signing in...
                </>
              ) : 'Sign In →'}
            </motion.button>
          </form>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          style={{ textAlign: 'center', fontSize: '13px', color: '#6b7280', marginTop: '20px' }}
        >
          Contact the gym to get your login credentials.
        </motion.p>
      </motion.div>
    </div>
  )
}

function LoadingSpinner() {
  return (
    <motion.svg
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      style={{ width: '18px', height: '18px' }}
      viewBox="0 0 24 24" fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
      <path fill="white" d="M4 12a8 8 0 018-8v8H4z" />
    </motion.svg>
  )
}
