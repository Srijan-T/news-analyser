import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { ApiError, api } from '../api/client.ts'
import type { NewsSearchParams, Period, SortOrder } from '../api/types.ts'
import { ArticleCard, ArticleCardSkeleton } from '../components/ArticleCard.tsx'
import { SearchForm } from '../components/SearchForm.tsx'

const SORTS: SortOrder[] = ['latest', 'relevance']
const PERIODS: Period[] = ['24h', '7d', '30d']

/** The search lives in the URL (?q=…&sort=…&period=…) so refresh, back and sharing work. */
function readParams(sp: URLSearchParams): NewsSearchParams {
  const sort = sp.get('sort') as SortOrder
  const period = sp.get('period') as Period
  return {
    q: sp.get('q')?.trim() ?? '',
    sort: SORTS.includes(sort) ? sort : 'latest',
    period: PERIODS.includes(period) ? period : null,
  }
}

function errorMessage(error: Error): string {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.'
  switch (error.code) {
    case 'invalid_query':
      return `That search couldn't be understood: ${error.message}`
    case 'news_quota_exceeded':
    case 'news_rate_limited':
    case 'network_error':
      return error.message
    default:
      return 'The news service is having trouble right now. Try again in a moment.'
  }
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const params = readParams(searchParams)

  const search = useQuery({
    queryKey: ['news-search', params],
    queryFn: () => api.searchNews(params),
    enabled: params.q !== '',
    // Each search spends one of 100 daily API requests, so reuse results for 5 minutes.
    staleTime: 5 * 60 * 1000,
    // Retrying a quota or bad-query error can't succeed and would waste quota.
    retry: false,
  })

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Search the news</h1>
        <p className="mt-1 text-slate-600">
          Find recent articles on a topic, then get an AI summary and sentiment for any of them.
        </p>
      </div>

      <SearchForm
        // Remount when the URL's search changes (e.g. back/forward) so the inputs match it.
        key={searchParams.toString()}
        initial={params}
        onSearch={({ q, sort, period }) =>
          setSearchParams({ q, sort, ...(period ? { period } : {}) })
        }
      />

      {params.q === '' ? (
        <p className="text-sm text-slate-500">Enter a topic above to see recent coverage.</p>
      ) : search.isPending ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading results">
          {Array.from({ length: 4 }, (_, i) => (
            <ArticleCardSkeleton key={i} />
          ))}
        </div>
      ) : search.isError ? (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm">
          <p className="text-red-800">{errorMessage(search.error)}</p>
          <button
            onClick={() => search.refetch()}
            className="mt-2 font-medium text-red-900 underline"
          >
            Try again
          </button>
        </div>
      ) : search.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">
          No articles found for “{params.q}”. Try broader terms or a longer time window.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">
            {search.data.items.length} articles · free news plan, so articles can be up to ~12
            hours old
          </p>
          {search.data.items.map((article) => (
            <ArticleCard key={article.url} article={article} />
          ))}
        </div>
      )}
    </section>
  )
}
