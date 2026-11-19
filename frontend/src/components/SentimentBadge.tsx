import type { Sentiment } from '../api/types.ts'

const STYLES: Record<Sentiment, string> = {
  positive: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  negative: 'bg-rose-50 text-rose-800 ring-rose-200',
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
