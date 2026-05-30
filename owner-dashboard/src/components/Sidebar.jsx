import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { BarChart2, Users, AlertTriangle, DollarSign, Bot, LogOut } from 'lucide-react'
import SyncStatus from './SyncStatus'

const NAV = [
  { to: '/overview', label: 'Overview', icon: BarChart2 },
  { to: '/members', label: 'Members', icon: Users },
  { to: '/dropout', label: 'Dropout Risk', icon: AlertTriangle },
  { to: '/revenue', label: 'Revenue', icon: DollarSign },
  { to: '/chat', label: 'AI Chat', icon: Bot },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  function handleLogout() {
    localStorage.removeItem('staff_token')
    localStorage.removeItem('staff_name')
    navigate('/login')
  }

  return (
    <aside style={{ position: 'fixed', top: 0, left: 0, height: '100%', width: '240px', background: '#fff', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', zIndex: 20, boxShadow: '2px 0 8px rgba(0,0,0,0.04)' }}>

      {/* Brand */}
      <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid #f3f4f6' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '38px', height: '38px', background: '#fff7ed', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px', border: '1px solid #fed7aa', flexShrink: 0 }}>🏋️</div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: '700', color: '#111827', lineHeight: '1.2' }}>Muscletech</div>
            <div style={{ fontSize: '12px', color: '#6b7280', lineHeight: '1.2' }}>Owner Dashboard</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to
          return (
            <NavLink
              key={to}
              to={to}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '10px 12px', borderRadius: '10px', fontSize: '14px', fontWeight: '500',
                textDecoration: 'none', transition: 'all 0.15s',
                color: active ? '#f97316' : '#4b5563',
                background: active ? '#fff7ed' : 'transparent',
                borderLeft: active ? '3px solid #f97316' : '3px solid transparent',
              }}
              onMouseEnter={e => { if (!active) { e.currentTarget.style.background = '#f9fafb'; e.currentTarget.style.color = '#111827' } }}
              onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#4b5563' } }}
            >
              <Icon size={17} />
              {label}
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom */}
      <div style={{ padding: '12px 10px 16px', borderTop: '1px solid #f3f4f6', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SyncStatus />
        <button
          onClick={handleLogout}
          style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', borderRadius: '10px', fontSize: '14px', fontWeight: '500', color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', transition: 'all 0.15s', width: '100%' }}
          onMouseEnter={e => { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.color = '#dc2626' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#6b7280' }}
        >
          <LogOut size={17} />
          Logout
        </button>
      </div>
    </aside>
  )
}
