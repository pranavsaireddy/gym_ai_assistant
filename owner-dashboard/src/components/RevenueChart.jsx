import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function formatLakh(n) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)}K`
  return `₹${n}`
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', padding: '12px 16px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
      <div style={{ fontSize: '14px', fontWeight: '600', color: '#111827', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '16px', fontWeight: '700', color: '#f97316' }}>₹{payload[0].value?.toLocaleString('en-IN')}</div>
      {payload[0].payload.count !== undefined && (
        <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '2px' }}>{payload[0].payload.count} transactions</div>
      )}
    </div>
  )
}

export default function RevenueChart({ data }) {
  if (!data?.length) return <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', fontSize: '14px' }}>No data available</div>

  const chartData = data.map(d => ({ name: MONTHS[d.month - 1], amount: d.total, count: d.count }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 13 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={formatLakh} tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} width={58} />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f9fafb' }} />
        <Bar dataKey="amount" fill="#f97316" radius={[6, 6, 0, 0]} maxBarSize={52} />
      </BarChart>
    </ResponsiveContainer>
  )
}
