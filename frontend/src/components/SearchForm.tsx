import { useState } from 'react'
import type { NewsSearchParams, Period, SortOrder } from '../api/types.ts'

type Props = {
  /** Starting values. The parent remounts the form (via `key`) when these change. */
  initial: NewsSearchParams
  onSearch: (params: NewsSearchParams) => void
}

const PERIODS: { value: Period | ''; label: string }[] = [
  { value: '', label: 'Any time' },
  { value: '24h', label: 'Past 24 hours' },
  { value: '7d', label: 'Past week' },
  { value: '30d', label: 'Past month' },
]

export function SearchForm({ initial, onSearch }: Props) {
  const [q, setQ] = useState(initial.q)
  const [sort, setSort] = useState<SortOrder>(initial.sort)
  const [period, setPeriod] = useState<Period | ''>(initial.period ?? '')

  const trimmed = q.trim()

  return (
    <form
      role="search"
      className="flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed) onSearch({ q: trimmed, sort, period: period || null })
      }}
    >
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search a topic, company or person…"
        aria-label="Search terms"
        maxLength={200}
        className="min-w-64 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 focus:border-slate-500 focus:outline-none"
      />
      <select
        value={sort}
        onChange={(e) => setSort(e.target.value as SortOrder)}
        aria-label="Sort by"
        className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
      >
        <option value="latest">Latest</option>
        <option value="relevance">Most relevant</option>
      </select>
      <select
        value={period}
        onChange={(e) => setPeriod(e.target.value as Period | '')}
        aria-label="Published within"
        className="rounded-md border border-slate-300 bg-white px-2 py-2 text-sm"
      >
        {PERIODS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={!trimmed}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        Search
      </button>
    </form>
  )
}
