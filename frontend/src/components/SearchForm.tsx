import { useState } from 'react'
import type { NewsSearchParams, Period, SortOrder } from '../api/types.ts'

type Props = {
  /** Starting values. The parent remounts the form (via `key`) when these change. */
  initial: NewsSearchParams
  onSearch: (params: NewsSearchParams) => void
  /** The query shown is a correction of what was typed: highlight it until edited, and
   * point screen readers at the notice explaining it. */
  correctedNoticeId?: string
}

const PERIODS: { value: Period | ''; label: string }[] = [
  { value: '', label: 'Any time' },
  { value: '24h', label: 'Past 24 hours' },
  { value: '7d', label: 'Past week' },
  { value: '30d', label: 'Past month' },
]

export function SearchForm({ initial, onSearch, correctedNoticeId }: Props) {
  const [q, setQ] = useState(initial.q)
  const [sort, setSort] = useState<SortOrder>(initial.sort)
  const [period, setPeriod] = useState<Period | ''>(initial.period ?? '')

  const trimmed = q.trim()
  // Highlight only while the box still shows the correction; once edited it's the user's text.
  const showingCorrection = Boolean(correctedNoticeId) && q === initial.q

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
        id="search-input"
        placeholder="Search a topic, company or person…  ( / )"
        aria-label="Search terms"
        aria-keyshortcuts="/"
        maxLength={200}
        aria-describedby={showingCorrection ? correctedNoticeId : undefined}
        className={`min-w-64 flex-1 rounded-md border bg-surface px-3 py-2 focus:outline-none ${
          showingCorrection
            ? 'border-accent ring-1 ring-accent'
            : 'border-line-strong focus:border-muted'
        }`}
      />
      <select
        value={sort}
        onChange={(e) => setSort(e.target.value as SortOrder)}
        aria-label="Sort by"
        className="rounded-md border border-line-strong bg-surface px-2 py-2 text-sm"
      >
        <option value="latest">Latest</option>
        <option value="relevance">Most relevant</option>
      </select>
      <select
        value={period}
        onChange={(e) => setPeriod(e.target.value as Period | '')}
        aria-label="Published within"
        className="rounded-md border border-line-strong bg-surface px-2 py-2 text-sm"
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
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-40"
      >
        Search
      </button>
    </form>
  )
}
