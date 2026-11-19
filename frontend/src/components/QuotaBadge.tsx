import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.ts'

/** "87 of 95 new searches left today". Hidden for providers without a quota. */
export function QuotaBadge() {
  const quota = useQuery({ queryKey: ['quota'], queryFn: api.quota })

  if (!quota.data || quota.data.limit === null || quota.data.remaining === null) return null
  const { remaining, limit } = quota.data
  return (
    <p className={`text-xs ${remaining === 0 ? 'text-red-700' : 'text-slate-500'}`}>
      {remaining === 0
        ? 'No new searches left today (resets 00:00 UTC). Recent searches still work.'
        : `${remaining} of ${limit} new searches left today`}
    </p>
  )
}
