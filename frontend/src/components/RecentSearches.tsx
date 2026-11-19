import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api } from '../api/client.ts'
import type { SearchSummary } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'

const SORT_LABEL = { latest: 'Latest', relevance: 'Relevant' } as const
const PERIOD_LABEL = { '24h': '24h', '7d': 'week', '30d': 'month' } as const

function describe(search: SearchSummary): string {
  const parts: string[] = [SORT_LABEL[search.sort]]
  if (search.period) parts.push(`past ${PERIOD_LABEL[search.period]}`)
  parts.push(`${search.result_count} articles`)
  return parts.join(' · ')
}

/** Reopening a past search reads stored results, so it costs no news-API quota. */
export function RecentSearches({ currentId }: { currentId: number | null }) {
  const recent = useQuery({ queryKey: ['searches'], queryFn: () => api.listSearches(10) })

  return (
    <nav aria-label="Recent searches" className="space-y-2">
      <h2 className="text-xs font-semibold tracking-wide text-muted uppercase">
        Recent searches
      </h2>
      {recent.isPending ? (
        <p className="text-sm text-faint">Loading…</p>
      ) : recent.isError ? (
        <p className="text-sm text-faint">Couldn't load history.</p>
      ) : recent.data.items.length === 0 ? (
        <p className="text-sm text-faint">No searches yet.</p>
      ) : (
        <ul className="space-y-1">
          {recent.data.items.map((search) => (
            <li key={search.id}>
              <Link
                to={`/?search=${search.id}`}
                aria-current={search.id === currentId ? 'page' : undefined}
                className={`block rounded-md px-2 py-1.5 ${
                  search.id === currentId ? 'bg-subtle-strong' : 'hover:bg-subtle'
                }`}
              >
                <span className="block truncate text-sm font-medium">{search.query}</span>
                <span className="block text-xs text-muted">
                  {describe(search)} · {timeAgo(search.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  )
}
