import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { staffLogin } from '../api/client'

export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await staffLogin(username.trim(), password)
      localStorage.setItem('staff_token', res.data.access_token)
      localStorage.setItem('staff_name', res.data.full_name || 'Owner')
      navigate('/overview')
    } catch (err) {
      if (err.response?.status === 401) setError('Invalid username or password.')
      else if (!err.response) setError('Cannot connect to server.')
      else setError('Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ width: '100%', maxWidth: '420px' }}>

        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '56px', height: '56px', background: '#fff7ed', borderRadius: '16px', marginBottom: '16px', border: '1px solid #fed7aa', fontSize: '28px' }}>🏋️</div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#111827', marginBottom: '4px' }}>Muscletech Fitness</h1>
          <p style={{ fontSize: '14px', color: '#6b7280' }}>Owner Dashboard — Staff Login</p>
        </div>

        <div style={{ background: '#fff', borderRadius: '16px', padding: '32px', boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.06)', border: '1px solid #e5e7eb' }}>

          {error && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', padding: '12px 16px', marginBottom: '20px', fontSize: '14px', color: '#dc2626' }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>Username</label>
              <input
                type="text" value={username} onChange={e => setUsername(e.target.value)}
                placeholder="owner" autoComplete="username"
                style={{ width: '100%', padding: '11px 14px', fontSize: '15px', border: '1.5px solid #e5e7eb', borderRadius: '10px', outline: 'none', color: '#111827', background: '#fff', transition: 'border-color 0.15s' }}
                onFocus={e => e.target.style.borderColor = '#f97316'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'}
              />
            </div>
            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>Password</label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Staff password" autoComplete="current-password"
                style={{ width: '100%', padding: '11px 14px', fontSize: '15px', border: '1.5px solid #e5e7eb', borderRadius: '10px', outline: 'none', color: '#111827', background: '#fff', transition: 'border-color 0.15s' }}
                onFocus={e => e.target.style.borderColor = '#f97316'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'}
              />
            </div>
            <button
              type="submit" disabled={loading}
              style={{ width: '100%', padding: '12px', fontSize: '15px', fontWeight: '600', color: '#fff', background: loading ? '#fdba74' : '#f97316', border: 'none', borderRadius: '10px', cursor: loading ? 'not-allowed' : 'pointer', transition: 'background 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.background = '#ea580c' }}
              onMouseLeave={e => { if (!loading) e.currentTarget.style.background = '#f97316' }}
            >
              {loading ? (
                <>
                  <svg style={{ animation: 'spin 1s linear infinite', width: '18px', height: '18px' }} viewBox="0 0 24 24" fill="none">
                    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                    <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
                    <path fill="white" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Signing in...
                </>
              ) : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
