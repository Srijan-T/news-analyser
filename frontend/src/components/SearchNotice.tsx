import type { Search } from '../api/types.ts'

/** Explains a forgiving search: a corrected typo, or results broadened to "any word". The
 * link re-runs exactly what was typed (no corrections), like a search engine's
 * "Search instead for …". */
export function SearchNotice({
  search,
  onSearchExactly,
}: {
  search: Search
  onSearchExactly: (typed: string) => void
}) {
  const typed = search.original_query
  if (!typed) return null

  const searchExactly = (
    <button
      type="button"
      onClick={() => onSearchExactly(typed)}
      className="text-muted underline hover:text-fg"
    >
      Search instead for “{typed}”
    </button>
  )

  return (
    <div role="status" className="rounded-md border border-line bg-subtle px-4 py-3 text-sm">
      {search.match_mode === 'any' ? (
        <p className="text-soft">
          No articles matched every word of “{typed}”, so these match{' '}
          <span className="font-medium text-fg">any</span> of them. {searchExactly}
        </p>
      ) : (
        <p className="text-soft">
          Showing results for <span className="font-medium text-fg">{search.query}</span>.{' '}
          {searchExactly}
        </p>
      )}
    </div>
  )
}
