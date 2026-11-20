import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { ApiError, api } from '../api/client.ts'
import type { NewsSearchParams } from '../api/types.ts'
import { ArticleCardSkeleton } from '../components/ArticleCard.tsx'
import { ArticleDetail } from '../components/ArticleDetail.tsx'
import { EarlierMatches } from '../components/EarlierMatches.tsx'
import { ExampleTopics } from '../components/ExampleTopics.tsx'
import { QuotaBadge } from '../components/QuotaBadge.tsx'
import { RecentSearches } from '../components/RecentSearches.tsx'
import { SEARCH_NOTICE_ID, SearchNotice } from '../components/SearchNotice.tsx'
import { SearchForm } from '../components/SearchForm.tsx'
import { SearchResults } from '../components/SearchResults.tsx'
import { timeAgo } from '../lib/format.ts'
import { useKeyboardShortcuts } from '../lib/shortcuts.ts'
import { useToast } from '../lib/toast.ts'

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
    case 'news_provider_not_configured':
      return "News search isn't set up on the server (no news API key), so searching can't work yet."
    case 'search_not_found':
      return "That search doesn't exist. Run a new one above."
    default:
      return 'The news service is having trouble right now. Try again in a moment.'
  }
}

/** A server set-up problem: retrying can't help, so don't offer it. */
function isConfigError(error: Error): boolean {
  return error instanceof ApiError && error.code.endsWith('_not_configured')
}

/** The URL holds the stored search's id (?search=42), so refresh, back/forward and shared
 * links reopen the same results without calling the news API again. */
function readId(sp: URLSearchParams, name: string): number | null {
  const id = Number(sp.get(name))
  return Number.isInteger(id) && id > 0 ? id : null
}

export function SearchPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
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
    onSuccess: ({ search, cached }) => {
      // Make the cache visible: reusing a recent search costs no news-API quota.
      if (cached) {
        toast(`Reused results fetched ${timeAgo(search.created_at)}, no news quota used`)
      }
      queryClient.setQueryData(['search', search.id], search)
      queryClient.invalidateQueries({ queryKey: ['searches'] })
      queryClient.invalidateQueries({ queryKey: ['quota'] })
      setSearchParams({ search: String(search.id) })
    },
    // A quota error changes what the badge should show.
    onError: () => queryClient.invalidateQueries({ queryKey: ['quota'] }),
  })

  // A failed search's error belongs to that attempt: once the user moves to another search
  // (recent searches, back/forward), show that search instead of the old error.
  const resetCreate = create.reset
  useEffect(() => resetCreate(), [searchId, resetCreate])

  // Closing keeps the current search (if any) and drops only the article.
  const closeArticle = () =>
    setSearchParams(searchId !== null ? { search: String(searchId) } : {})

  useKeyboardShortcuts({
    onSlash: () => document.getElementById('search-input')?.focus(),
    // Esc closes the detail panel, keeping the current search.
    onEscape: () => {
      if (articleId !== null) closeArticle()
    },
  })

  const search = stored.data
  // The form shows what ran, except for "any word" searches, whose OR query is an internal
  // detail: there it shows what was typed.
  const formValues = search
    ? {
        q: search.match_mode === 'any' ? (search.original_query ?? search.query) : search.query,
        sort: search.sort,
        period: search.period,
      }
    : EMPTY_FORM
  const selectArticle = (articleId: number) =>
    search && setSearchParams({ search: String(search.id), article: String(articleId) })
  const error = create.error ?? (searchId !== null ? stored.error : null)

  return (
    // Desktop-first: from 1024px, recent searches and results, plus the article column only
    // while an article is open (otherwise the page is centred, with no empty column). Below
    // that, one column (results, then the selected article, then history) so phones and
    // tablets never scroll sideways.
    <div
      className={
        articleId !== null
          ? 'grid gap-6 lg:grid-cols-[12rem_minmax(0,1fr)_20rem] xl:grid-cols-[13rem_minmax(0,1fr)_24rem]'
          : 'mx-auto grid max-w-6xl gap-6 lg:grid-cols-[12rem_minmax(0,1fr)] xl:grid-cols-[13rem_minmax(0,1fr)]'
      }
    >
      <aside className="order-last lg:order-none">
        <RecentSearches currentId={searchId} />
      </aside>

      <section className="min-w-0 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Search the news</h1>
          <p className="mt-1 text-soft">
            Find recent articles on a topic, then select a headline for its AI summary and
            sentiment.
          </p>
        </div>

        <div className="space-y-2">
          <SearchForm
            // Remount when the shown search changes (e.g. back/forward) so inputs match it.
            key={search?.id ?? 'new'}
            initial={formValues}
            onSearch={(params) => create.mutate(params)}
            pending={create.isPending}
            correctedNoticeId={
              search?.original_query && search.match_mode === 'all' ? SEARCH_NOTICE_ID : undefined
            }
            // Right under the box, so the user sees why its text differs from what they typed.
            notice={
              search &&
              !create.isPending && (
                <SearchNotice
                  search={search}
                  onSearchExactly={(typed) =>
                    create.mutate({ q: typed, sort: search.sort, period: search.period, exact: true })
                  }
                />
              )
            }
          />
          <QuotaBadge />
        </div>

        {create.isPending || (searchId !== null && stored.isPending) ? (
          <div className="space-y-3" role="status" aria-busy="true">
            <span className="sr-only">Loading results…</span>
            {Array.from({ length: 4 }, (_, i) => (
              <ArticleCardSkeleton key={i} />
            ))}
          </div>
        ) : error ? (
          <div role="alert" className="rounded-md border border-danger-line bg-danger-bg p-4 text-sm">
            <p className="text-danger-fg">{errorMessage(error)}</p>
            {create.error && create.variables && !isConfigError(create.error) && (
              <button
                onClick={() => create.mutate(create.variables)}
                className="mt-2 font-medium text-danger-fg underline"
              >
                Try again
              </button>
            )}
            {!create.error && stored.isError && (
              <button
                onClick={() => stored.refetch()}
                className="mt-2 font-medium text-danger-fg underline"
              >
                Try again
              </button>
            )}
          </div>
        ) : !search ? (
          <ExampleTopics onPick={(q) => create.mutate({ q, sort: 'latest', period: null })} />
        ) : search.items.length === 0 ? (
          <div className="space-y-6">
            <p className="text-sm text-muted">
              No new articles found for “{search.query}”. Try broader terms or a longer time
              window.
            </p>
            <EarlierMatches
              query={search.query}
              selectedId={articleId}
              onSelect={selectArticle}
            />
          </div>
        ) : (
          <SearchResults
            key={search.id}
            search={search}
            selectedId={articleId}
            onSelect={selectArticle}
          />
        )}
      </section>

      {articleId !== null && (
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <ArticleDetail
            key={articleId}
            articleId={articleId}
            searchId={searchId}
            onClose={closeArticle}
          />
        </aside>
      )}
    </div>
  )
}
