import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Users, Activity, Clock, AlertTriangle, RefreshCw } from 'lucide-react'
import { getDashboard, syncMembers, syncStatus, syncBilling, syncAll } from '../api/client'
import StatCard from '../components/StatCard'
import DropoutList from '../components/DropoutList'

function formatINR(n) {
  if (!n && n !== 0) return '—'
  return '₹' + n.toLocaleString('en-IN')
}

function pctChange(curr, prev) {
  if (!prev) return null
  return ((curr - prev) / prev * 100).toFixed(1)
}

const PAGE = { padding: '32px', maxWidth: '1100px' }
const SECTION_TITLE = { fontSize: '17px', fontWeight: '700', color: '#111827', marginBottom: '14px' }
const CARD = { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '14px', padding: '22px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }

export default function OverviewPage() {
  const navigate = useNavigate()
  const [syncLoading, setSyncLoading] = useState({})
  const [syncMsg, setSyncMsg] = useState({ text: '', ok: true })

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => getDashboard().then(r => r.data),
    retry: 1,
  })

  async function handleSync(label, fn) {
    setSyncLoading(p => ({ ...p, [label]: true }))
    setSyncMsg({ text: '', ok: true })
    try {
      await fn()
      setSyncMsg({ text: `${label} sync started.`, ok: true })
    } catch {
      setSyncMsg({ text: 'Sync failed. Check server.', ok: false })
    } finally {
      setSyncLoading(p => ({ ...p, [label]: false }))
      setTimeout(() => setSyncMsg({ text: '', ok: true }), 4000)
    }
  }

  const revPct = data ? pctChange(data.revenue_this_month, data.revenue_last_month) : null

  if (isLoading) return (
    <div style={PAGE}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '20px' }}>
        {[...Array(4)].map((_, i) => <div key={i} style={{ height: '100px', background: '#e5e7eb', borderRadius: '14px', animation: 'pulse 1.5s infinite' }} />)}
      </div>
    </div>
  )

  const syncBtns = [
    { label: 'Members', fn: syncMembers },
    { label: 'Status', fn: syncStatus },
    { label: 'Billing', fn: syncBilling },
    { label: 'Sync All', fn: syncAll },
  ]

  return (
    <div style={PAGE}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#111827', marginBottom: '2px' }}>Overview</h1>
          {data?.as_of && <p style={{ fontSize: '14px', color: '#6b7280' }}>Data as of {new Date(data.as_of).toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' })}</p>}
        </div>
        <button onClick={() => refetch()} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 16px', fontSize: '14px', fontWeight: '500', color: '#374151', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', cursor: 'pointer', transition: 'all 0.15s', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = '#f97316'; e.currentTarget.style.color = '#f97316' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.color = '#374151' }}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '20px' }}>
        <StatCard label="Total Members" value={data?.total_members ?? '—'} icon={Users} accent="#f97316" accentBg="#fff7ed" accentBorder="#fed7aa" />
        <StatCard label="Active Today" value={data?.todays_checkins ?? '—'} icon={Activity} accent="#16a34a" accentBg="#f0fdf4" accentBorder="#bbf7d0" />
        <StatCard label="Expiring (7 days)" value={data?.expiring_7_days ?? '—'} icon={Clock}
          accent={data?.expiring_7_days > 0 ? '#d97706' : '#9ca3af'}
          accentBg={data?.expiring_7_days > 0 ? '#fffbeb' : '#f9fafb'}
          accentBorder={data?.expiring_7_days > 0 ? '#fde68a' : '#e5e7eb'}
        />
        <StatCard label="Not Seen 14d" value={data?.not_seen_14_days ?? '—'} icon={AlertTriangle}
          accent={data?.not_seen_14_days > 20 ? '#dc2626' : '#9ca3af'}
          accentBg={data?.not_seen_14_days > 20 ? '#fef2f2' : '#f9fafb'}
          accentBorder={data?.not_seen_14_days > 20 ? '#fecaca' : '#e5e7eb'}
        />
      </div>

      {/* Revenue + Health cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
        <div style={CARD}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Revenue This Month</div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#f97316' }}>{formatINR(data?.revenue_this_month)}</div>
          {revPct !== null && (
            <div style={{ fontSize: '14px', color: parseFloat(revPct) >= 0 ? '#16a34a' : '#dc2626', marginTop: '6px', fontWeight: '500' }}>
              {parseFloat(revPct) >= 0 ? '↑' : '↓'} {Math.abs(revPct)}% vs last month ({formatINR(data?.revenue_last_month)})
            </div>
          )}
          <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>Top mode: {data?.top_payment_mode || '—'}</div>
        </div>
        <div style={CARD}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Membership Health</div>
          <div style={{ fontSize: '28px', fontWeight: '700', color: '#dc2626' }}>{data?.inactive_members ?? '—'}</div>
          <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '10px' }}>inactive members</div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {[
              { label: `${data?.irregular_members ?? 0} irregular`, color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
              { label: `${data?.not_seen_30_days ?? 0} not seen 30d`, color: '#dc2626', bg: '#fef2f2', border: '#fecaca' },
              { label: `${data?.expiring_30_days ?? 0} expiring 30d`, color: '#6b7280', bg: '#f9fafb', border: '#e5e7eb' },
            ].map(b => (
              <span key={b.label} style={{ fontSize: '13px', fontWeight: '500', color: b.color, background: b.bg, border: `1px solid ${b.border}`, borderRadius: '20px', padding: '3px 10px' }}>{b.label}</span>
            ))}
          </div>
        </div>
      </div>

      {/* At-risk + Sync */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h2 style={SECTION_TITLE}>At Risk Members</h2>
            <button onClick={() => navigate('/dropout')} style={{ fontSize: '14px', fontWeight: '500', color: '#f97316', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>View All →</button>
          </div>
          <DropoutList members={data?.at_risk_members} limit={5} />
        </div>

        <div>
          <h2 style={SECTION_TITLE}>Quick Sync</h2>
          <div style={CARD}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {syncBtns.map(({ label, fn }) => (
                <button
                  key={label}
                  onClick={() => handleSync(label, fn)}
                  disabled={!!syncLoading[label]}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px', padding: '11px', fontSize: '14px', fontWeight: '500', color: syncLoading[label] ? '#9ca3af' : '#374151', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '10px', cursor: syncLoading[label] ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
                  onMouseEnter={e => { if (!syncLoading[label]) { e.currentTarget.style.borderColor = '#f97316'; e.currentTarget.style.color = '#f97316'; e.currentTarget.style.background = '#fff7ed' } }}
                  onMouseLeave={e => { if (!syncLoading[label]) { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.color = '#374151'; e.currentTarget.style.background = '#f9fafb' } }}
                >
                  {syncLoading[label] ? (
                    <svg style={{ animation: 'spin 1s linear infinite', width: '15px', height: '15px' }} viewBox="0 0 24 24" fill="none">
                      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                      <circle cx="12" cy="12" r="10" stroke="#d1d5db" strokeWidth="3" />
                      <path fill="#9ca3af" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                  ) : <RefreshCw size={14} />}
                  {label}
                </button>
              ))}
            </div>
            {syncMsg.text && (
              <div style={{ marginTop: '14px', padding: '10px 14px', background: syncMsg.ok ? '#f0fdf4' : '#fef2f2', border: `1px solid ${syncMsg.ok ? '#bbf7d0' : '#fecaca'}`, borderRadius: '8px', fontSize: '13px', color: syncMsg.ok ? '#15803d' : '#dc2626' }}>
                {syncMsg.text}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
