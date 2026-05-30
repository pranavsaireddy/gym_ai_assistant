function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function riskConfig(score) {
  if (score >= 0.7) return { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'High Risk' }
  if (score >= 0.5) return { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Medium Risk' }
  return { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Low Risk' }
}

export default function DropoutList({ members, limit }) {
  const list = limit ? members?.slice(0, limit) : members
  if (!list?.length) return <div style={{ fontSize: '14px', color: '#6b7280', padding: '16px 0' }}>No members found.</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {list.map((m, i) => {
        const rc = riskConfig(m.dropout_score)
        return (
          <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
              <div>
                <div style={{ fontSize: '15px', fontWeight: '600', color: '#111827' }}>{m.name}</div>
                {m.plan && <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '1px' }}>{m.plan}</div>}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '20px', fontWeight: '700', color: rc.color }}>{Math.round(m.dropout_score * 100)}%</div>
                <span style={{ fontSize: '11px', fontWeight: '600', color: rc.color, background: rc.bg, border: `1px solid ${rc.border}`, borderRadius: '20px', padding: '1px 8px', display: 'inline-block' }}>{rc.label}</span>
              </div>
            </div>
            <div style={{ height: '6px', background: '#f3f4f6', borderRadius: '3px', overflow: 'hidden', marginBottom: '10px' }}>
              <div style={{ height: '100%', width: `${m.dropout_score * 100}%`, background: rc.color, borderRadius: '3px', transition: 'width 0.3s' }} />
            </div>
            <div style={{ display: 'flex', gap: '16px', fontSize: '13px' }}>
              <span style={{ color: m.days_absent > 14 ? '#dc2626' : '#6b7280', fontWeight: m.days_absent > 14 ? '600' : '400' }}>
                {m.days_absent} days absent
              </span>
              <span style={{ color: '#6b7280' }}>Expires {formatDate(m.expiry)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
