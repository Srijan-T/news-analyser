import type { Search } from '../api/types.ts'

export const SEARCH_NOTICE_ID = 'search-correction'

/** Shown right under the search box when the query that ran differs from what was typed:
 * a corrected typo, or results broadened to "any word". The link re-runs exactly what was
 * typed (no corrections), like a search engine's "Search instead for ...". */
export function SearchNotice({
  search,
  onSearchExactly,
}: {
  search: Search
  onSearchExactly: (typed: string) => void
}) {
  const typed = search.original_query
  if (!typed) return null

  return (
    <p id={SEARCH_NOTICE_ID} role="status" className="flex flex-wrap items-baseline gap-x-2 text-sm">
      <span aria-hidden="true" className="text-muted">
        ✎
      </span>
      {search.match_mode === 'any' ? (
        <span className="text-soft">
          Nothing matched every word of “{typed}”, so results match{' '}
          <span className="font-medium text-fg">any</span> of them.
        </span>
      ) : (
        <span className="text-soft">
          Auto-corrected from <span className="font-medium text-fg">“{typed}”</span>.
        </span>
      )}
      <button
        type="button"
        onClick={() => onSearchExactly(typed)}
        className="text-muted underline hover:text-fg"
      >
        Search exactly as typed
      </button>
    </p>
  )
}
