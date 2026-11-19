import type { Sentiment } from '../api/types.ts'

// Meaningful colours (green/grey/red) stay explicit, with tuned dark-mode variants:
// translucent tinted backgrounds and lighter text keep contrast on dark surfaces.
const STYLES: Record<Sentiment, string> = {
  positive:
    'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30',
  neutral: 'bg-subtle text-soft ring-line',
  negative:
    'bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:ring-rose-500/30',
}

const LABELS: Record<Sentiment, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
}

export function SentimentBadge({ sentiment, score }: { sentiment: Sentiment; score?: number }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STYLES[sentiment]}`}
    >
      {LABELS[sentiment]}
      {score !== undefined && (
        <span className="tabular-nums opacity-70">
          {score > 0 ? '+' : ''}
          {score.toFixed(2)}
        </span>
      )}
    </span>
  )
}
