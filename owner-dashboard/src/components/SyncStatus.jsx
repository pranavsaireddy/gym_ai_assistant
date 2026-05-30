import { useQuery } from '@tanstack/react-query'
import { getCookieHealth } from '../api/client'

export default function SyncStatus() {
  const { data, isLoading } = useQuery({
    queryKey: ['cookieHealth'],
    queryFn: () => getCookieHealth().then(r => r.data),
    refetchInterval: 5 * 60 * 1000,
    retry: 1,
  })

  const valid = data?.cookies_valid

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', background: '#f9fafb', borderRadius: '10px', border: '1px solid #e5e7eb' }}>
      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLoading ? '#d1d5db' : valid ? '#16a34a' : '#dc2626', flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: '13px', fontWeight: '500', color: isLoading ? '#6b7280' : valid ? '#15803d' : '#dc2626' }}>
          {isLoading ? 'Checking...' : valid ? 'Session Active' : 'Session Expired'}
        </div>
        {!isLoading && !valid && (
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>Check browser extension</div>
        )}
      </div>
    </div>
  )
}
