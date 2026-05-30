function daysAgo(dateStr) {
  if (!dateStr) return '—'
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Yesterday'
  if (diff < 7) return `${diff} days ago`
  if (diff < 30) return `${Math.floor(diff / 7)}w ago`
  return `${Math.floor(diff / 30)}mo ago`
}

function expiryInfo(dateStr) {
  if (!dateStr) return { text: '—', color: '#6b7280' }
  const days = Math.floor((new Date(dateStr) - new Date()) / 86400000)
  const text = new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  if (days < 0) return { text, color: '#dc2626' }
  if (days <= 7) return { text, color: '#dc2626' }
  if (days <= 30) return { text, color: '#d97706' }
  return { text, color: '#16a34a' }
}

function statusStyle(status) {
  if (status === 'Active') return { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' }
  if (status === 'Inactive') return { color: '#6b7280', bg: '#f9fafb', border: '#e5e7eb' }
  return { color: '#dc2626', bg: '#fef2f2', border: '#fecaca' }
}

function riskBar(score) {
  if (score >= 0.7) return '#dc2626'
  if (score >= 0.4) return '#d97706'
  return '#16a34a'
}

const TH = ({ children }) => (
  <th style={{ textAlign: 'left', fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '12px 16px', background: '#f9fafb', whiteSpace: 'nowrap' }}>
    {children}
  </th>
)

export default function MemberTable({ members, loading }) {
  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {[...Array(8)].map((_, i) => (
        <div key={i} style={{ height: '52px', background: '#e5e7eb', borderRadius: '10px', animation: 'pulse 1.5s infinite' }} />
      ))}
    </div>
  )

  if (!members?.length) return (
    <div style={{ textAlign: 'center', padding: '48px', fontSize: '14px', color: '#6b7280' }}>No members found.</div>
  )

  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '14px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <TH>Name</TH>
              <TH>Status</TH>
              <TH>Last Visit</TH>
              <TH>Visits</TH>
              <TH>Expiry</TH>
              <TH>Dropout Risk</TH>
            </tr>
          </thead>
          <tbody>
            {members.map((m, i) => {
              const ss = statusStyle(m.status)
              const exp = expiryInfo(m.expiry)
              const score = m.dropout_score || 0
              return (
                <tr key={m.id || i} style={{ borderBottom: '1px solid #f3f4f6' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '13px 16px' }}>
                    <div style={{ fontSize: '14px', fontWeight: '600', color: '#111827' }}>{m.name}</div>
                    <div style={{ fontSize: '12px', color: '#9ca3af' }}>ID: {m.id}</div>
                  </td>
                  <td style={{ padding: '13px 16px' }}>
                    <span style={{ fontSize: '13px', fontWeight: '500', color: ss.color, background: ss.bg, border: `1px solid ${ss.border}`, borderRadius: '20px', padding: '3px 10px' }}>
                      {m.status}
                    </span>
                  </td>
                  <td style={{ padding: '13px 16px', fontSize: '14px', color: '#4b5563' }}>{daysAgo(m.last_checkin)}</td>
                  <td style={{ padding: '13px 16px', fontSize: '15px', fontWeight: '700', color: '#f97316' }}>{m.total_checkins ?? 0}</td>
                  <td style={{ padding: '13px 16px', fontSize: '14px', fontWeight: '500', color: exp.color }}>{exp.text}</td>
                  <td style={{ padding: '13px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '80px', height: '6px', background: '#f3f4f6', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${score * 100}%`, background: riskBar(score), borderRadius: '3px' }} />
                      </div>
                      <span style={{ fontSize: '13px', fontWeight: '500', color: '#374151', minWidth: '32px' }}>{Math.round(score * 100)}%</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
