import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.ts'
import { ArticleCard } from './ArticleCard.tsx'

/** When a search finds nothing new, show stored articles whose titles fuzzily match the
 * query. This reads our own database, so it costs no news quota. */
export function EarlierMatches({
  query,
  selectedId,
  onSelect,
}: {
  query: string
  selectedId: number | null
  onSelect: (articleId: number) => void
}) {
  const similar = useQuery({
    queryKey: ['similar', query],
    queryFn: () => api.similarArticles(query),
  })

  if (!similar.data || similar.data.items.length === 0) return null
  return (
    <section aria-label="From your earlier searches" className="space-y-3">
      <h2 className="text-sm font-medium text-soft">From your earlier searches</h2>
      {similar.data.items.map((article) => (
        <ArticleCard
          key={article.id}
          article={article}
          selected={article.id === selectedId}
          onSelect={() => onSelect(article.id)}
        />
      ))}
    </section>
  )
}
