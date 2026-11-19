import { useState } from 'react'
import type { Article } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'
import { SentimentBadge } from './SentimentBadge.tsx'

type Props = {
  article: Article
  selected?: boolean
  onSelect?: () => void
}

export function ArticleCard({ article, selected = false, onSelect }: Props) {
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = article.image_url && !imageFailed

  return (
    <article
      className={`flex gap-4 rounded-lg border bg-white p-4 ${
        selected ? 'border-slate-900 ring-1 ring-slate-900' : 'border-slate-200'
      }`}
    >
      {showImage ? (
        <img
          src={article.image_url!}
          alt=""
          loading="lazy"
          onError={() => setImageFailed(true)}
          className="h-20 w-28 shrink-0 rounded-md bg-slate-100 object-cover"
        />
      ) : (
        <div className="h-20 w-28 shrink-0 rounded-md bg-slate-100" />
      )}
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
          <span>
            {article.source_name} · {timeAgo(article.published_at)}
          </span>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-slate-900 hover:underline"
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
        {article.description && (
          <p className="mt-1 line-clamp-2 text-sm text-slate-600">{article.description}</p>
        )}
      </div>
    </article>
  )
}

export function ArticleCardSkeleton() {
  return (
    <div className="flex animate-pulse gap-4 rounded-lg border border-slate-200 bg-white p-4">
      <div className="h-20 w-28 shrink-0 rounded-md bg-slate-200" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-3 w-1/4 rounded bg-slate-200" />
        <div className="h-4 w-3/4 rounded bg-slate-200" />
        <div className="h-3 w-full rounded bg-slate-200" />
      </div>
    </div>
  )
}
