import { useState } from 'react'
import type { Article, Sentiment } from '../api/types.ts'
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
}

export function ArticleCard({ article, selected = false, onSelect, showSummary = false }: Props) {
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = article.image_url && !imageFailed
  const blurb = showSummary && article.analysis ? article.analysis.tldr : article.description

  return (
    <article
      className={`flex gap-4 rounded-lg border bg-surface p-4 ${
        selected ? 'border-accent ring-1 ring-accent' : 'border-line'
      } ${article.analysis ? SENTIMENT_EDGE[article.analysis.sentiment] : ''}`}
    >
      {showImage ? (
        <img
          src={article.image_url!}
          alt=""
          loading="lazy"
          onError={() => setImageFailed(true)}
          className="h-20 w-28 shrink-0 rounded-md bg-subtle object-cover"
        />
      ) : (
        <div className="h-20 w-28 shrink-0 rounded-md bg-subtle" />
      )}
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
