import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api } from '../api/client.ts'
import type { Analysis, Article } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'
import { SentimentBadge } from './SentimentBadge.tsx'

function analysisError(error: Error): string {
  if (error instanceof ApiError) {
    if (error.code === 'ai_output_invalid') return "The AI couldn't produce an analysis. Try again."
    if (error.code === 'ai_unavailable' || error.code === 'network_error') return error.message
  }
  return 'Analysis failed. Try again.'
}

/** Detail panel for the selected article: its AI analysis, or a button to create one. */
export function ArticleDetail({ articleId, searchId }: { articleId: number; searchId: number | null }) {
  const queryClient = useQueryClient()
  const article = useQuery({ queryKey: ['article', articleId], queryFn: () => api.getArticle(articleId) })

  const analyze = useMutation({
    mutationFn: () => api.analyzeArticle(articleId),
    // An AI call costs money and time; let the user decide whether to retry.
    retry: false,
    onSuccess: (analysis) => {
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
    return <div className="h-64 animate-pulse rounded-lg bg-slate-100" aria-label="Loading article" />
  }
  if (article.isError) {
    return <p className="text-sm text-slate-500">Couldn't load this article.</p>
  }

  const { analysis } = article.data
  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <p className="text-xs text-slate-500">
          {article.data.source_name} · {timeAgo(article.data.published_at)}
        </p>
        <h2 className="mt-1 leading-snug font-semibold">{article.data.title}</h2>
        <a
          href={article.data.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-block text-xs text-slate-500 hover:text-slate-900 hover:underline"
        >
          Read the original ↗
        </a>
      </div>

      {analysis ? (
        <AnalysisView analysis={analysis} />
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => analyze.mutate()}
            disabled={analyze.isPending}
            className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {analyze.isPending ? 'Analyzing…' : 'Summarize & analyze sentiment'}
          </button>
          {analyze.isError && (
            <p role="alert" className="text-sm text-red-700">
              {analysisError(analyze.error)}
            </p>
          )}
          <p className="text-xs text-slate-500">
            Uses AI on the headline, description and opening lines.
          </p>
        </div>
      )}
    </div>
  )
}

function AnalysisView({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <SentimentBadge sentiment={analysis.sentiment} score={analysis.score} />
        {analysis.text_source === 'snippet' && (
          <span
            className="text-xs text-slate-500"
            title="The free news plan only provides the article's opening, not the full text"
          >
            Based on the article's opening
          </span>
        )}
      </div>

      <p className="font-medium">{analysis.tldr}</p>

      {analysis.key_points.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          {analysis.key_points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      )}

      <div className="space-y-2 text-sm">
        <p className="text-slate-600">
          <span className="font-medium text-slate-900">Why this sentiment: </span>
          {analysis.rationale}
        </p>
        {analysis.evidence.map((quote) => (
          <blockquote key={quote} className="border-l-2 border-slate-300 pl-3 text-slate-600 italic">
            “{quote}”
          </blockquote>
        ))}
      </div>

      <p className="text-xs text-slate-400">
        {analysis.model} · prompt {analysis.prompt_version} · {timeAgo(analysis.created_at)}
      </p>
    </div>
  )
}
