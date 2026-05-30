export default function StatCard({ label, value, icon: Icon, accent = '#f97316', accentBg = '#fff7ed', accentBorder = '#fed7aa', subtitle }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '14px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
      {Icon && (
        <div style={{ width: '44px', height: '44px', background: accentBg, border: `1px solid ${accentBorder}`, borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={20} color={accent} />
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '12px', fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>{label}</div>
        <div style={{ fontSize: '26px', fontWeight: '700', color: accent, lineHeight: '1' }}>{value}</div>
        {subtitle && <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>{subtitle}</div>}
      </div>
    </div>
  )
}
