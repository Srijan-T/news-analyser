import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client.ts'
import type { AnalysisBatch, Search } from '../api/types.ts'
import { timeAgo } from '../lib/format.ts'
import { useToast } from '../lib/toast.ts'
import { ArticleCard } from './ArticleCard.tsx'

const MAX_BATCH = 10 // the API's limit per batch
const POLL_MS = 1000

function summary(batch: AnalysisBatch): string {
  const { done, skipped, failed } = batch.counts
  const parts = [`Analyzed ${done} article${done === 1 ? '' : 's'}`]
  if (skipped) parts.push(`${skipped} already done`)
  if (failed) parts.push(`${failed} failed`)
  return parts.join(' · ')
}

/** A search's articles, with checkboxes to analyze several at once. The batch runs on the
 * server; this polls it and fills in each card's sentiment as its analysis lands. Remount
 * (key) per search so selection and progress never leak between searches. */
export function SearchResults({
  search,
  selectedId,
  onSelect,
}: {
  search: Search
  selectedId: number | null
  onSelect: (articleId: number) => void
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [checked, setChecked] = useState<ReadonlySet<number>>(new Set())
  const [batchId, setBatchId] = useState<number | null>(null)
  const announced = useRef<number | null>(null) // the batch whose summary was shown

  const start = useMutation({
    mutationFn: api.createAnalysisBatch,
    retry: false, // AI calls cost money: let the user decide to retry
    onSuccess: (batch) => {
      setChecked(new Set())
      queryClient.setQueryData(['analysis-batch', batch.id], batch)
      setBatchId(batch.id)
    },
  })

  const batch = useQuery({
    queryKey: ['analysis-batch', batchId],
    queryFn: () => api.getAnalysisBatch(batchId!),
    enabled: batchId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'done' ? false : POLL_MS),
  })
  const running = start.isPending || batch.data?.status === 'running'

  // As analyses land, show them on the cards straight away (patching the cached search),
  // then, once the batch is done, refresh everything that lists analyses.
  const data = batch.data
  useEffect(() => {
    if (!data) return
    const finished = new Map(
      data.items.flatMap((item) => (item.analysis ? [[item.article_id, item.analysis]] : [])),
    )
    queryClient.setQueryData<Search>(['search', search.id], (old) =>
      old
        ? {
            ...old,
            items: old.items.map((a) =>
              a.analysis ? a : { ...a, analysis: finished.get(a.id) ?? null },
            ),
          }
        : old,
    )
    if (data.status === 'done' && announced.current !== data.id) {
      announced.current = data.id
      toast(summary(data), data.counts.failed ? 'info' : 'success')
      queryClient.invalidateQueries({ queryKey: ['article'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    }
  }, [data, queryClient, search.id, toast])

  const unanalyzed = search.items.filter((a) => !a.analysis).map((a) => a.id)
  const statusOf = new Map(data?.items.map((item) => [item.article_id, item.status]))
  const finishedCount = data ? data.items.length - data.counts.pending - data.counts.running : 0
  const toggle = (id: number, on: boolean) =>
    setChecked((old) => {
      const next = new Set(old)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        {search.items.length} articles · fetched {timeAgo(search.created_at)} · free news plan, so
        articles can be up to ~12 hours old
      </p>

      {running && data ? (
        <div role="status" className="space-y-1.5 rounded-lg border border-line bg-surface p-3">
          <p className="text-sm text-soft">
            Analyzing {finishedCount} of {data.items.length}…
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-subtle-strong">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-500"
              style={{ width: `${(finishedCount / data.items.length) * 100}%` }}
            />
          </div>
        </div>
      ) : (
        unanalyzed.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={checked.size === 0 || running}
              onClick={() => start.mutate([...checked])}
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg disabled:opacity-50"
            >
              Analyze selected ({checked.size})
            </button>
            <button
              type="button"
              disabled={running}
              onClick={() => start.mutate(unanalyzed.slice(0, MAX_BATCH))}
              className="rounded-md border border-line-strong px-3 py-1.5 text-sm font-medium text-soft hover:text-fg disabled:opacity-50"
            >
              Analyze all unanalyzed ({Math.min(unanalyzed.length, MAX_BATCH)})
            </button>
            {start.error && (
              <p role="alert" className="text-sm text-danger-fg">
                {start.error instanceof ApiError
                  ? start.error.message
                  : "Couldn't start the analysis. Try again."}
              </p>
            )}
          </div>
        )
      )}

      {search.items.map((article) => (
        <ArticleCard
          key={article.id}
          article={article}
          selected={article.id === selectedId}
          onSelect={() => onSelect(article.id)}
          selection={
            article.analysis || running
              ? null
              : {
                  checked: checked.has(article.id),
                  disabled: !checked.has(article.id) && checked.size >= MAX_BATCH,
                  onChange: (on) => toggle(article.id, on),
                }
          }
          batchStatus={statusOf.get(article.id)}
        />
      ))}
    </div>
  )
}
