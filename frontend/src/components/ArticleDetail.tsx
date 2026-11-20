import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useRef } from 'react'
import { ApiError, api } from '../api/client.ts'
import type { Analysis, Article } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'
import { useToast } from '../lib/toast.ts'
import { SentimentBadge } from './SentimentBadge.tsx'

function analysisError(error: Error): string {
  if (error instanceof ApiError) {
    if (error.code === 'ai_not_configured') {
      return "AI analysis isn't set up on the server (no OpenAI key), so it can't run yet."
    }
    if (error.code === 'ai_output_invalid') return "The AI couldn't produce an analysis. Try again."
    if (error.code === 'ai_unavailable' || error.code === 'network_error') return error.message
  }
  return 'Analysis failed. Try again.'
}

// Matches Tailwind's `lg`: from here the panel sits beside the list; below it, under the list.
const SIDE_BY_SIDE = '(min-width: 1024px)'

/** Detail panel for the selected article: its AI analysis, or a button to create one. Mount
 * it with key={articleId} so each selection is a fresh mount. */
export function ArticleDetail({
  articleId,
  searchId,
  onClose,
}: {
  articleId: number
  searchId: number | null
  onClose: () => void
}) {
  const panel = useRef<HTMLElement>(null)

  // Below `lg` the panel renders after the whole results list, far off screen, so a tap on a
  // headline would seem to do nothing: bring the panel into view and move focus to it.
  useEffect(() => {
    if (window.matchMedia(SIDE_BY_SIDE).matches) return
    panel.current?.scrollIntoView({ block: 'start' })
    panel.current?.focus({ preventScroll: true })
  }, [])

  function close() {
    onClose()
    if (window.matchMedia(SIDE_BY_SIDE).matches) return
    // Back to where the user was in the list.
    const card = document.querySelector<HTMLElement>(`[data-article-id="${articleId}"]`)
    card?.scrollIntoView({ block: 'center' })
    card?.querySelector<HTMLElement>('h2 button')?.focus({ preventScroll: true })
  }

  return (
    <section
      ref={panel}
      tabIndex={-1}
      aria-label="Article analysis"
      className="scroll-mt-4 space-y-2 outline-none"
    >
      <button
        type="button"
        onClick={close}
        className="text-sm text-muted hover:text-fg lg:float-right lg:text-xs"
      >
        <span className="lg:hidden">← Back to results</span>
        <span className="hidden lg:inline">✕ Close</span>
      </button>
      <DetailBody articleId={articleId} searchId={searchId} />
    </section>
  )
}

function DetailBody({ articleId, searchId }: { articleId: number; searchId: number | null }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const article = useQuery({ queryKey: ['article', articleId], queryFn: () => api.getArticle(articleId) })

  const analyze = useMutation({
    mutationFn: () => api.analyzeArticle(articleId),
    // An AI call costs money and time; let the user decide whether to retry.
    retry: false,
    onSuccess: ({ analysis, created }) => {
      if (created) toast('Analysis saved to your history', 'success')
      queryClient.setQueryData<Article>(['article', articleId], (old) =>
        old ? { ...old, analysis } : old,
      )
      // The results list shows sentiment badges, so refresh it too.
      if (searchId !== null) queryClient.invalidateQueries({ queryKey: ['search', searchId] })
      // History and its stats now include this article.
      queryClient.invalidateQueries({ queryKey: ['history'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  if (article.isPending) {
    return (
      <div role="status" aria-busy="true" className="clear-both h-64 animate-pulse rounded-lg bg-subtle">
        <span className="sr-only">Loading article…</span>
      </div>
    )
  }
  if (article.isError) {
    return <Card>Couldn't load this article. It may have been removed; pick another headline.</Card>
  }

  const { analysis } = article.data
  return (
    <div className="clear-both space-y-4 rounded-lg border border-line bg-surface p-5">
      <div>
        <p className="text-xs text-muted">
          {article.data.source_name} · {timeAgo(article.data.published_at)}
        </p>
        <h2 className="mt-1 leading-snug font-semibold">{article.data.title}</h2>
        <a
          href={article.data.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-block text-xs text-muted hover:text-fg hover:underline"
        >
          Read the original ↗
        </a>
      </div>

      {analysis ? (
        <AnalysisView analysis={analysis} />
      ) : analyze.isPending ? (
        <AnalysisSkeleton />
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => analyze.mutate()}
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg"
          >
            Summarize & analyze sentiment
          </button>
          {analyze.isError && (
            <p role="alert" className="text-sm text-danger-fg">
              {analysisError(analyze.error)}
            </p>
          )}
          <p className="text-xs text-muted">
            Uses AI on the headline, description and opening lines (the free news plan doesn't
            include full articles).
          </p>
        </div>
      )}
    </div>
  )
}

function Card({ children }: { children: ReactNode }) {
  return (
    <p className="clear-both rounded-lg border border-line bg-surface p-5 text-sm text-muted">
      {children}
    </p>
  )
}

/** Placeholder in the shape of the analysis while the AI works, so the wait feels expected. */
function AnalysisSkeleton() {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <p className="text-sm text-muted">Analyzing with AI… usually 3–10 seconds.</p>
      <div className="animate-pulse space-y-4" aria-hidden="true">
        <div className="h-5 w-28 rounded-full bg-subtle-strong" />
        <div className="space-y-2">
          <div className="h-4 w-full rounded bg-subtle-strong" />
          <div className="h-4 w-4/5 rounded bg-subtle-strong" />
        </div>
        <div className="space-y-2 pl-5">
          <div className="h-3 w-11/12 rounded bg-subtle" />
          <div className="h-3 w-3/4 rounded bg-subtle" />
          <div className="h-3 w-5/6 rounded bg-subtle" />
        </div>
        <div className="h-10 border-l-2 border-line-strong pl-3">
          <div className="h-3 w-2/3 rounded bg-subtle" />
        </div>
      </div>
    </div>
  )
}

function AnalysisView({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <SentimentBadge sentiment={analysis.sentiment} score={analysis.score} />
        {analysis.text_source === 'snippet' && (
          <span className="text-xs text-muted">
            Based on the article's opening; the free news plan doesn't include full text
          </span>
        )}
      </div>

      <p className="font-medium">{analysis.tldr}</p>

      {analysis.key_points.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-soft">
          {analysis.key_points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      )}

      <div className="space-y-2 text-sm">
        <p className="text-soft">
          <span className="font-medium text-fg">Why this sentiment: </span>
          {analysis.rationale}
        </p>
        {analysis.evidence.map((quote) => (
          <blockquote key={quote} className="border-l-2 border-line-strong pl-3 text-soft italic">
            “{quote}”
          </blockquote>
        ))}
      </div>

      <p className="text-xs text-faint">
        {analysis.model} · prompt {analysis.prompt_version} · {timeAgo(analysis.created_at)}
      </p>
    </div>
  )
}
