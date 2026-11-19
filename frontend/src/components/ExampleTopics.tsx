// Starting points for a first visit: one click runs a real search. Broad, newsworthy topics
// so each reliably returns results; repeats within 30 minutes are served from the cache.
const TOPICS = [
  'Nvidia earnings',
  'AI regulation',
  'Interest rates',
  'Climate policy',
  'Electric vehicles',
  'UK housing market',
]

export function ExampleTopics({ onPick }: { onPick: (topic: string) => void }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">Enter a topic above, or try one of these:</p>
      <ul className="flex flex-wrap gap-2" aria-label="Example topics">
        {TOPICS.map((topic) => (
          <li key={topic}>
            <button
              type="button"
              onClick={() => onPick(topic)}
              className="rounded-full border border-line-strong bg-surface px-3 py-1.5 text-sm text-soft hover:border-muted hover:text-fg"
            >
              {topic}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
