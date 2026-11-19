import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { api } from '../api/client.ts'
import type { ArticleSort, HistoryFilters, Period, Sentiment } from '../api/types.ts'
import { ArticleCard, ArticleCardSkeleton } from '../components/ArticleCard.tsx'
import { ArticleDetail } from '../components/ArticleDetail.tsx'
import { StatsStrip } from '../components/StatsStrip.tsx'

const PAGE_SIZE = 10
const SENTIMENTS: Sentiment[] = ['positive', 'neutral', 'negative']
const PERIODS: Period[] = ['24h', '7d', '30d']
const SORTS: { value: ArticleSort; label: string }[] = [
  { value: 'published_desc', label: 'Newest first' },
  { value: 'published_asc', label: 'Oldest first' },
  { value: 'analyzed_desc', label: 'Recently analyzed' },
  { value: 'score_desc', label: 'Most positive' },
  { value: 'score_asc', label: 'Most negative' },
]
const PERIOD_LABEL: Record<Period, string> = {
  '24h': 'Past 24 hours',
  '7d': 'Past week',
  '30d': 'Past month',
}

function positiveInt(value: string | null): number | null {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : null
}

/** Filters, page and selected article all live in the URL, so views can be shared. */
function readFilters(sp: URLSearchParams): HistoryFilters {
  const sentiment = sp.get('sentiment') as Sentiment
  const within = sp.get('within') as Period
  const sort = sp.get('sort') as ArticleSort
  return {
    sentiment: SENTIMENTS.includes(sentiment) ? sentiment : null,
    source: sp.get('source') || null,
    searchId: positiveInt(sp.get('search')),
    within: PERIODS.includes(within) ? within : null,
    sort: SORTS.some((s) => s.value === sort) ? sort : 'published_desc',
  }
}

const selectClass = 'rounded-md border border-line-strong bg-surface px-2 py-1.5 text-sm'

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = readFilters(searchParams)
  const page = positiveInt(searchParams.get('page')) ?? 1
  const articleId = positiveInt(searchParams.get('article'))

  const list = useQuery({
    queryKey: ['history', filters, page],
    queryFn: () => api.listArticles(filters, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    placeholderData: keepPreviousData, // keep the old page visible while the next loads
  })
  const stats = useQuery({
    queryKey: ['stats', filters],
    queryFn: () => api.stats(filters),
  })
  const searches = useQuery({
    queryKey: ['searches', 50],
    queryFn: () => api.listSearches(50),
  })

  /** Change one URL param; any filter change resets to page 1 and closes the detail panel. */
  function update(name: string, value: string | null, keep: string[] = []) {
    const next = new URLSearchParams()
    for (const [key, val] of searchParams) {
      if (key !== name && (keep.includes(key) || !['page', 'article'].includes(key))) {
        next.set(key, val)
      }
    }
    if (value) next.set(name, value)
    setSearchParams(next)
  }

  const total = list.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const filtered = Object.entries(filters).some(([k, v]) => k !== 'sort' && v !== null)

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="min-w-0 space-y-5">
        <div>
          <h1 className="text-2xl font-semibold">Analysis history</h1>
          <p className="mt-1 text-soft">
            Every article you've analyzed, with its sentiment. Filter to see how coverage leans.
          </p>
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Filters">
          <select
            aria-label="Sentiment"
            className={selectClass}
            value={filters.sentiment ?? ''}
            onChange={(e) => update('sentiment', e.target.value)}
          >
            <option value="">All sentiments</option>
            {SENTIMENTS.map((s) => (
              <option key={s} value={s}>
                {s[0].toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
          <select
            aria-label="Source"
            className={selectClass}
            value={filters.source ?? ''}
            onChange={(e) => update('source', e.target.value)}
          >
            <option value="">All sources</option>
            {stats.data?.sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
          <select
            aria-label="From search"
            className={`${selectClass} max-w-56`}
            value={filters.searchId ?? ''}
            onChange={(e) => update('search', e.target.value)}
          >
            <option value="">From any search</option>
            {searches.data?.items.map((s) => (
              <option key={s.id} value={s.id}>
                “{s.query}”
              </option>
            ))}
          </select>
          <select
            aria-label="Published within"
            className={selectClass}
            value={filters.within ?? ''}
            onChange={(e) => update('within', e.target.value)}
          >
            <option value="">Any time</option>
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {PERIOD_LABEL[p]}
              </option>
            ))}
          </select>
          <select
            aria-label="Sort"
            className={selectClass}
            value={filters.sort}
            onChange={(e) =>
              update('sort', e.target.value === 'published_desc' ? null : e.target.value)
            }
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {filtered && (
            <button
              type="button"
              onClick={() => setSearchParams({})}
              className="px-2 text-sm text-muted underline hover:text-fg"
            >
              Clear filters
            </button>
          )}
        </div>

        {stats.data && <StatsStrip stats={stats.data} />}

        {list.isPending ? (
          <div className="space-y-3" aria-busy="true" aria-label="Loading history">
            {Array.from({ length: 3 }, (_, i) => (
              <ArticleCardSkeleton key={i} />
            ))}
          </div>
        ) : list.isError ? (
          <p role="alert" className="text-sm text-danger-fg">
            Couldn't load your history. Refresh to try again.
          </p>
        ) : list.data.items.length === 0 ? (
          <p className="text-sm text-muted">
            {filtered
              ? 'No analyzed articles match these filters.'
              : 'Nothing analyzed yet. Search for a topic and analyze an article to see it here.'}
          </p>
        ) : (
          <>
            <div className="space-y-3">
              {list.data.items.map((article) => (
                <ArticleCard
                  key={article.id}
                  article={article}
                  showSummary
                  selected={article.id === articleId}
                  onSelect={() => update('article', String(article.id), ['page'])}
                />
              ))}
            </div>
            {pages > 1 && (
              <nav aria-label="Pages" className="flex items-center justify-between text-sm">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => update('page', page > 2 ? String(page - 1) : null)}
                  className="rounded-md border border-line-strong bg-surface px-3 py-1.5 disabled:opacity-40"
                >
                  ← Previous
                </button>
                <span className="text-muted">
                  Page {page} of {pages}
                </span>
                <button
                  type="button"
                  disabled={page >= pages}
                  onClick={() => update('page', String(page + 1))}
                  className="rounded-md border border-line-strong bg-surface px-3 py-1.5 disabled:opacity-40"
                >
                  Next →
                </button>
              </nav>
            )}
          </>
        )}
      </section>

      <aside className="lg:sticky lg:top-6 lg:self-start">
        {articleId !== null ? (
          <ArticleDetail key={articleId} articleId={articleId} searchId={null} />
        ) : list.data && list.data.items.length > 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong p-5 text-sm text-muted">
            Select a headline to see its full analysis.
          </p>
        ) : null}
      </aside>
    </div>
  )
}
