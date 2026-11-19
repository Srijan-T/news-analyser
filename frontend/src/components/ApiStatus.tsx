import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.ts'

// Re-check periodically so the badge recovers after a backend restart (and notices an outage).
const HEALTH_POLL_MS = 30_000

/** Small badge showing whether the backend is reachable. */
export function ApiStatus() {
  const { isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: HEALTH_POLL_MS,
  })

  const [label, dot] = isPending
    ? ['Connecting…', 'bg-slate-400']
    : isError
      ? ['API offline', 'bg-red-500']
      : ['API online', 'bg-emerald-500']

  return (
    <span className="flex items-center gap-2 text-xs text-slate-500">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </span>
  )
}
