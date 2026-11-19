import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { ApiError, api } from '../api/client.ts'
import type { NewsSearchParams } from '../api/types.ts'
import { ArticleCard, ArticleCardSkeleton } from '../components/ArticleCard.tsx'
import { QuotaBadge } from '../components/QuotaBadge.tsx'
import { RecentSearches } from '../components/RecentSearches.tsx'
import { SearchForm } from '../components/SearchForm.tsx'
import { timeAgo } from '../lib/format.ts'

const EMPTY_FORM: NewsSearchParams = { q: '', sort: 'latest', period: null }

function errorMessage(error: Error): string {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.'
  switch (error.code) {
    case 'invalid_query':
      return `That search couldn't be understood: ${error.message}`
    case 'news_quota_exceeded':
    case 'news_rate_limited':
    case 'network_error':
      return error.message
    case 'search_not_found':
      return "That search doesn't exist. Run a new one above."
    default:
      return 'The news service is having trouble right now. Try again in a moment.'
  }
}

/** The URL holds the stored search's id (?search=42), so refresh, back/forward and shared
 * links reopen the same results without calling the news API again. */
function readSearchId(sp: URLSearchParams): number | null {
  const id = Number(sp.get('search'))
  return Number.isInteger(id) && id > 0 ? id : null
}

export function SearchPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchId = readSearchId(searchParams)

  const stored = useQuery({
    queryKey: ['search', searchId],
    queryFn: () => api.getSearch(searchId!),
    enabled: searchId !== null,
    staleTime: Infinity, // a stored search never changes
    retry: false,
  })

  const create = useMutation({
    mutationFn: api.createSearch,
    // Each new search can spend one of the day's news-API requests; never auto-retry.
    retry: false,
    onSuccess: (search) => {
      queryClient.setQueryData(['search', search.id], search)
      queryClient.invalidateQueries({ queryKey: ['searches'] })
      queryClient.invalidateQueries({ queryKey: ['quota'] })
      setSearchParams({ search: String(search.id) })
    },
    // A quota error changes what the badge should show.
    onError: () => queryClient.invalidateQueries({ queryKey: ['quota'] }),
  })

  const search = stored.data
  const formValues = search
    ? { q: search.query, sort: search.sort, period: search.period }
    : EMPTY_FORM
  const error = create.error ?? (searchId !== null ? stored.error : null)

  return (
    <div className="grid grid-cols-[14rem_1fr] gap-8">
      <aside>
        <RecentSearches currentId={searchId} />
      </aside>

      <section className="min-w-0 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Search the news</h1>
          <p className="mt-1 text-slate-600">
            Find recent articles on a topic, then get an AI summary and sentiment for any of them.
          </p>
        </div>

        <div className="space-y-2">
          <SearchForm
            // Remount when the shown search changes (e.g. back/forward) so inputs match it.
            key={search?.id ?? 'new'}
            initial={formValues}
            onSearch={(params) => create.mutate(params)}
          />
          <QuotaBadge />
        </div>

        {create.isPending || (searchId !== null && stored.isPending) ? (
          <div className="space-y-3" aria-busy="true" aria-label="Loading results">
            {Array.from({ length: 4 }, (_, i) => (
              <ArticleCardSkeleton key={i} />
            ))}
          </div>
        ) : error ? (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm">
            <p className="text-red-800">{errorMessage(error)}</p>
            {create.error && create.variables && (
              <button
                onClick={() => create.mutate(create.variables)}
                className="mt-2 font-medium text-red-900 underline"
              >
                Try again
              </button>
            )}
          </div>
        ) : !search ? (
          <p className="text-sm text-slate-500">
            Enter a topic above, or reopen a recent search.
          </p>
        ) : search.items.length === 0 ? (
          <p className="text-sm text-slate-500">
            No articles found for “{search.query}”. Try broader terms or a longer time window.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              {search.items.length} articles · fetched {timeAgo(search.created_at)} · free news
              plan, so articles can be up to ~12 hours old
            </p>
            {search.items.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
