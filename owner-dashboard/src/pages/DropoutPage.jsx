import { useQuery } from '@tanstack/react-query'
import { getDropout } from '../api/client'
import DropoutList from '../components/DropoutList'

export default function DropoutPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dropout'],
    queryFn: () => getDropout(0.5).then(r => r.data),
    retry: 1,
  })

  const high = data?.filter(m => m.dropout_score >= 0.7).length || 0
  const medium = data?.filter(m => m.dropout_score >= 0.5 && m.dropout_score < 0.7).length || 0

  return (
    <div style={{ padding: '32px', maxWidth: '760px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#111827' }}>Dropout Risk</h1>
        {!isLoading && (
          <span style={{ fontSize: '14px', fontWeight: '600', color: '#dc2626', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '20px', padding: '4px 14px' }}>
            {data?.length ?? 0} members at risk
          </span>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '20px', marginBottom: '24px' }}>
        {[
          { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: `High Risk (>70%) — ${high}` },
          { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: `Medium (50–70%) — ${medium}` },
        ].map(b => (
          <div key={b.label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: b.bg, border: `1.5px solid ${b.color}` }} />
            <span style={{ fontSize: '14px', color: '#4b5563' }}>{b.label}</span>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {[...Array(6)].map((_, i) => <div key={i} style={{ height: '100px', background: '#e5e7eb', borderRadius: '12px', animation: 'pulse 1.5s infinite' }} />)}
        </div>
      ) : (
        <DropoutList members={data} />
      )}
    </div>
  )
}
