import { useState } from 'react'
import type { Article, BatchItemStatus, Sentiment } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'
import { SentimentBadge } from './SentimentBadge.tsx'

// A coloured left edge so analyzed articles' tone reads at a glance in a list. The badge
// still states the sentiment in words, so colour is never the only signal.
const SENTIMENT_EDGE: Record<Sentiment, string> = {
  positive: 'border-l-4 border-l-emerald-500',
  neutral: 'border-l-4 border-l-slate-400 dark:border-l-zinc-500',
  negative: 'border-l-4 border-l-rose-500',
}

type Props = {
  article: Article
  selected?: boolean
  onSelect?: () => void
  /** Show the AI TL;DR (when analyzed) instead of the provider's description. */
  showSummary?: boolean
  /** A checkbox for batch analysis, shown on the thumbnail (so no column is reserved). */
  selection?: { checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }
  /** Progress in a running batch analysis. */
  batchStatus?: BatchItemStatus
  /** Why the batch couldn't analyze this article (when batchStatus is 'failed'). */
  batchError?: string | null
}

const BATCH_ERROR: Record<string, string> = {
  ai_unavailable: 'AI unavailable',
  ai_output_invalid: 'AI gave an unusable answer',
  ai_not_configured: 'AI not set up',
  interrupted: 'interrupted',
}

// 'done' and 'skipped' need no label: the sentiment badge appears instead.
const BATCH_LABEL: Partial<Record<BatchItemStatus, string>> = {
  pending: 'Queued',
  running: 'Analyzing…',
  failed: 'Analysis failed',
}

export function ArticleCard({
  article,
  selected = false,
  onSelect,
  showSummary = false,
  selection,
  batchStatus,
  batchError,
}: Props) {
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = article.image_url && !imageFailed
  const blurb = showSummary && article.analysis ? article.analysis.tldr : article.description

  return (
    <article
      data-article-id={article.id} // lets the detail panel scroll back to this card
      className={`flex gap-4 rounded-lg border bg-surface p-4 ${
        selected ? 'border-accent ring-1 ring-accent' : 'border-line'
      } ${article.analysis ? SENTIMENT_EDGE[article.analysis.sentiment] : ''}`}
    >
      <div className="relative h-20 w-28 shrink-0">
        {showImage ? (
          <img
            src={article.image_url!}
            alt=""
            loading="lazy"
            onError={() => setImageFailed(true)}
            className="h-full w-full rounded-md bg-subtle object-cover"
          />
        ) : (
          <div className="h-full w-full rounded-md bg-subtle" />
        )}
        {selection && (
          // A backed corner chip keeps the box visible on any photo, with a 28px tap target.
          <label className="absolute top-1 left-1 flex size-7 cursor-pointer items-center justify-center rounded-md bg-surface/90 shadow-sm">
            <input
              type="checkbox"
              checked={selection.checked}
              disabled={selection.disabled}
              title={selection.disabled ? 'Up to 10 articles per batch' : undefined}
              onChange={(e) => selection.onChange(e.target.checked)}
              aria-label={`Select for analysis: ${article.title}`}
              className="size-4 cursor-pointer accent-accent disabled:cursor-not-allowed"
            />
          </label>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <span>
            {article.source_name} · {timeAgo(article.published_at)}
          </span>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-fg hover:underline"
          >
            Original ↗
          </a>
          {article.analysis && <SentimentBadge sentiment={article.analysis.sentiment} />}
          {batchStatus && BATCH_LABEL[batchStatus] && (
            <span
              className={
                batchStatus === 'failed'
                  ? 'text-danger-fg'
                  : `font-medium text-soft ${batchStatus === 'running' ? 'animate-pulse' : ''}`
              }
            >
              {BATCH_LABEL[batchStatus]}
              {batchStatus === 'failed' && `: ${BATCH_ERROR[batchError ?? ''] ?? 'try again'}`}
            </span>
          )}
        </p>
        <h2 className="mt-1 leading-snug font-semibold">
          {/* The title selects the article; "Original" opens the source site. */}
          <button
            type="button"
            onClick={onSelect}
            aria-pressed={selected}
            className="text-left hover:underline"
          >
            {article.title}
          </button>
        </h2>
        {blurb && <p className="mt-1 line-clamp-2 text-sm text-soft">{blurb}</p>}
      </div>
    </article>
  )
}

export function ArticleCardSkeleton() {
  return (
    <div className="flex animate-pulse gap-4 rounded-lg border border-line bg-surface p-4">
      <div className="h-20 w-28 shrink-0 rounded-md bg-subtle-strong" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-3 w-1/4 rounded bg-subtle-strong" />
        <div className="h-4 w-3/4 rounded bg-subtle-strong" />
        <div className="h-3 w-full rounded bg-subtle-strong" />
      </div>
    </div>
  )
}
