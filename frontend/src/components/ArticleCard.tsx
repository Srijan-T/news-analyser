import { useState } from 'react'
import type { Article } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'

export function ArticleCard({ article }: { article: Article }) {
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = article.image_url && !imageFailed

  return (
    <article className="flex gap-4 rounded-lg border border-slate-200 bg-white p-4">
      {showImage ? (
        <img
          src={article.image_url!}
          alt=""
          loading="lazy"
          onError={() => setImageFailed(true)}
          className="h-24 w-36 shrink-0 rounded-md bg-slate-100 object-cover"
        />
      ) : (
        <div className="h-24 w-36 shrink-0 rounded-md bg-slate-100" />
      )}
      <div className="min-w-0">
        <p className="text-xs text-slate-500">
          {article.source_name} · {timeAgo(article.published_at)}
        </p>
        <h2 className="mt-1 font-semibold leading-snug">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
          >
            {article.title}
          </a>
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
      <div className="h-24 w-36 shrink-0 rounded-md bg-slate-200" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-3 w-1/4 rounded bg-slate-200" />
        <div className="h-4 w-3/4 rounded bg-slate-200" />
        <div className="h-3 w-full rounded bg-slate-200" />
      </div>
    </div>
  )
}
