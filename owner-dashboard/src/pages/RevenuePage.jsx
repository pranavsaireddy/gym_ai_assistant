import { useQuery } from '@tanstack/react-query'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { getRevenue } from '../api/client'
import RevenueChart from '../components/RevenueChart'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const CARD = { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '14px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }

function formatINR(n) {
  if (!n && n !== 0) return '—'
  return '₹' + n.toLocaleString('en-IN')
}

export default function RevenuePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['revenue'],
    queryFn: () => getRevenue(6).then(r => r.data),
    retry: 1,
  })

  const total = data?.reduce((s, d) => s + d.total, 0) || 0
  const totalTxns = data?.reduce((s, d) => s + d.count, 0) || 0
  const avg = data?.length ? total / data.length : 0
  const best = data?.reduce((b, d) => d.total > (b?.total || 0) ? d : b, null)

  const sorted = [...(data || [])].sort((a, b) => b.year - a.year || b.month - a.month)
  const curr = sorted[0]
  const prev = sorted[1]
  const pct = prev?.total ? ((curr?.total - prev.total) / prev.total * 100).toFixed(1) : null

  return (
    <div style={{ padding: '32px', maxWidth: '900px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#111827', marginBottom: '24px' }}>Revenue</h1>

      {/* Chart card */}
      <div style={{ ...CARD, marginBottom: '20px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#111827', marginBottom: '20px' }}>Monthly Revenue — Last 6 Months</h2>
        {isLoading ? (
          <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: '36px', height: '36px', border: '3px solid #e5e7eb', borderTop: '3px solid #f97316', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : (
          <RevenueChart data={data} />
        )}
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '20px' }}>
        {[
          { label: 'Total Collected', value: formatINR(total), color: '#f97316' },
          { label: 'Monthly Average', value: formatINR(Math.round(avg)), color: '#111827' },
          { label: 'Best Month', value: formatINR(best?.total), color: '#16a34a', sub: best ? `${MONTHS[best.month - 1]} ${best.year}` : '' },
          { label: 'Total Transactions', value: totalTxns.toLocaleString('en-IN'), color: '#111827' },
        ].map(c => (
          <div key={c.label} style={CARD}>
            <div style={{ fontSize: '12px', fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>{c.label}</div>
            <div style={{ fontSize: '20px', fontWeight: '700', color: c.color }}>{c.value}</div>
            {c.sub && <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '3px' }}>{c.sub}</div>}
          </div>
        ))}
      </div>

      {/* Current month */}
      {curr && (
        <div style={{ ...CARD, border: '1px solid #fed7aa', background: '#fff7ed' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                {MONTHS[curr.month - 1]} {curr.year} (Current)
              </div>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#f97316' }}>{formatINR(curr.total)}</div>
              <div style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>{curr.count} transactions</div>
            </div>
            {pct !== null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '20px', fontWeight: '700', color: parseFloat(pct) >= 0 ? '#16a34a' : '#dc2626' }}>
                {parseFloat(pct) >= 0 ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
                {parseFloat(pct) >= 0 ? '+' : ''}{pct}%
                <span style={{ fontSize: '13px', fontWeight: '400', color: '#6b7280' }}>vs prev month</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
