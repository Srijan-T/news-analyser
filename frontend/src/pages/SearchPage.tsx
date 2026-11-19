import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { ApiError, api } from '../api/client.ts'
import type { NewsSearchParams } from '../api/types.ts'
import { ArticleCard, ArticleCardSkeleton } from '../components/ArticleCard.tsx'
import { ArticleDetail } from '../components/ArticleDetail.tsx'
import { QuotaBadge } from '../components/QuotaBadge.tsx'
import { RecentSearches } from '../components/RecentSearches.tsx'
import { SearchForm } from '../components/SearchForm.tsx'
import { timeAgo } from '../lib/format.ts'
import { useKeyboardShortcuts } from '../lib/shortcuts.ts'

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
function readId(sp: URLSearchParams, name: string): number | null {
  const id = Number(sp.get(name))
  return Number.isInteger(id) && id > 0 ? id : null
}

export function SearchPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchId = readId(searchParams, 'search')
  // The selected article is in the URL too (?search=1&article=5), so it survives refresh.
  const articleId = readId(searchParams, 'article')

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

  useKeyboardShortcuts({
    onSlash: () => document.getElementById('search-input')?.focus(),
    // Esc closes the detail panel, keeping the current search.
    onEscape: () => {
      if (articleId !== null && searchId !== null) setSearchParams({ search: String(searchId) })
    },
  })

  const search = stored.data
  const formValues = search
    ? { q: search.query, sort: search.sort, period: search.period }
    : EMPTY_FORM
  const error = create.error ?? (searchId !== null ? stored.error : null)

  return (
    // Desktop-first: three columns from 1024px; below that, one column (results, then the
    // selected article, then history) so phones and tablets never scroll sideways.
    <div className="grid gap-6 lg:grid-cols-[12rem_minmax(0,1fr)_20rem] xl:grid-cols-[13rem_minmax(0,1fr)_24rem]">
      <aside className="order-last lg:order-none">
        <RecentSearches currentId={searchId} />
      </aside>

      <section className="min-w-0 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Search the news</h1>
          <p className="mt-1 text-soft">
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
          <div role="alert" className="rounded-md border border-danger-line bg-danger-bg p-4 text-sm">
            <p className="text-danger-fg">{errorMessage(error)}</p>
            {create.error && create.variables && (
              <button
                onClick={() => create.mutate(create.variables)}
                className="mt-2 font-medium text-danger-fg underline"
              >
                Try again
              </button>
            )}
          </div>
        ) : !search ? (
          <p className="text-sm text-muted">
            Enter a topic above, or reopen a recent search.
          </p>
        ) : search.items.length === 0 ? (
          <p className="text-sm text-muted">
            No articles found for “{search.query}”. Try broader terms or a longer time window.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted">
              {search.items.length} articles · fetched {timeAgo(search.created_at)} · free news
              plan, so articles can be up to ~12 hours old
            </p>
            {search.items.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                selected={article.id === articleId}
                onSelect={() =>
                  setSearchParams({ search: String(search.id), article: String(article.id) })
                }
              />
            ))}
          </div>
        )}
      </section>

      <aside className="lg:sticky lg:top-6 lg:self-start">
        {articleId !== null ? (
          <ArticleDetail key={articleId} articleId={articleId} searchId={searchId} />
        ) : search && search.items.length > 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong p-5 text-sm text-muted">
            Select an article's headline to see its AI summary and sentiment.
          </p>
        ) : null}
      </aside>
    </div>
  )
}
