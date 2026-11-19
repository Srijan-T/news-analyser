import type { Stats } from '../api/types.ts'

const SEGMENTS = [
  { key: 'positive', label: 'Positive', bar: 'bg-emerald-500' },
  { key: 'neutral', label: 'Neutral', bar: 'bg-slate-400' },
  { key: 'negative', label: 'Negative', bar: 'bg-rose-500' },
] as const

/** Sentiment breakdown of the articles the current filters match. */
export function StatsStrip({ stats }: { stats: Stats }) {
  if (stats.total === 0) return null
  const average = stats.average_score

  return (
    <section
      aria-label="Sentiment summary"
      className="space-y-3 rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
        <span>
          <span className="text-lg font-semibold tabular-nums">{stats.total}</span>{' '}
          <span className="text-slate-500">analyzed</span>
        </span>
        {SEGMENTS.map(({ key, label }) => (
          <span key={key} className="text-slate-600">
            {label} <span className="font-medium tabular-nums">{stats.by_sentiment[key]}</span>
          </span>
        ))}
        {average !== null && (
          <span className="text-slate-600">
            Average score{' '}
            <span className="font-medium tabular-nums">
              {average > 0 ? '+' : ''}
              {average.toFixed(2)}
            </span>
          </span>
        )}
      </div>
      {/* Proportion bar: each segment's width is its share of the analyzed articles. */}
      <div className="flex h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
        {SEGMENTS.map(({ key, bar }) => (
          <div
            key={key}
            className={bar}
            style={{
              width: `${(stats.by_sentiment[key] / stats.total) * 100}%`,
            }}
          />
        ))}
      </div>
    </section>
  )
}
