import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { getMembers } from '../api/client'
import MemberTable from '../components/MemberTable'

const PAGE_SIZE = 50

export default function MembersPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [risk, setRisk] = useState('')
  const [page, setPage] = useState(1)

  const params = { page, limit: PAGE_SIZE, ...(search && { search }), ...(status && { status }), ...(risk === 'high' && { risk: 'high' }) }

  const { data, isLoading } = useQuery({
    queryKey: ['members', params],
    queryFn: () => getMembers(params).then(r => r.data),
    retry: 1,
    keepPreviousData: true,
  })

  const members = Array.isArray(data) ? data : data?.members || data || []
  const total = data?.total || members.length
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const SELECT_STYLE = { padding: '9px 14px', fontSize: '14px', border: '1.5px solid #e5e7eb', borderRadius: '10px', outline: 'none', color: '#374151', background: '#fff', cursor: 'pointer', transition: 'border-color 0.15s' }

  return (
    <div style={{ padding: '32px', maxWidth: '1100px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#111827' }}>Members</h1>
        <span style={{ fontSize: '14px', color: '#6b7280' }}>
          {isLoading ? 'Loading...' : `${members.length} of ${total} members`}
        </span>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1', minWidth: '200px', maxWidth: '320px' }}>
          <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
          <input
            type="text" value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search by name..."
            style={{ width: '100%', padding: '9px 14px 9px 36px', fontSize: '14px', border: '1.5px solid #e5e7eb', borderRadius: '10px', outline: 'none', color: '#111827', background: '#fff', transition: 'border-color 0.15s' }}
            onFocus={e => e.target.style.borderColor = '#f97316'}
            onBlur={e => e.target.style.borderColor = '#e5e7eb'}
          />
        </div>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1) }} style={SELECT_STYLE}
          onFocus={e => e.target.style.borderColor = '#f97316'}
          onBlur={e => e.target.style.borderColor = '#e5e7eb'}>
          <option value="">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
          <option value="Expired">Expired</option>
        </select>
        <select value={risk} onChange={e => { setRisk(e.target.value); setPage(1) }} style={SELECT_STYLE}
          onFocus={e => e.target.style.borderColor = '#f97316'}
          onBlur={e => e.target.style.borderColor = '#e5e7eb'}>
          <option value="">All Risk Levels</option>
          <option value="high">High Risk (&gt;70%)</option>
        </select>
      </div>

      <MemberTable members={members} loading={isLoading} />

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '20px' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 16px', fontSize: '14px', fontWeight: '500', color: page === 1 ? '#9ca3af' : '#374151', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', cursor: page === 1 ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}>
            <ChevronLeft size={16} /> Previous
          </button>
          <span style={{ fontSize: '14px', color: '#6b7280' }}>Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 16px', fontSize: '14px', fontWeight: '500', color: page === totalPages ? '#9ca3af' : '#374151', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', cursor: page === totalPages ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}>
            Next <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
