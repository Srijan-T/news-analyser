import { useEffect, useRef } from 'react'

type Handlers = {
  /** "/" pressed while not typing: e.g. jump to the search box. */
  onSlash?: () => void
  /** Escape pressed while not typing: e.g. close the detail panel. */
  onEscape?: () => void
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  )
}

/** Page-level keyboard shortcuts. While typing in a field, "/" types normally and Escape
 * just leaves the field, so shortcuts never steal keystrokes. */
export function useKeyboardShortcuts(handlers: Handlers): void {
  // Read the latest handlers from a ref so the listener is attached once, not every render.
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const typing = isTyping(event.target)
      if (event.key === 'Escape') {
        if (typing) (event.target as HTMLElement).blur()
        else latest.current.onEscape?.()
      } else if (event.key === '/' && !typing && latest.current.onSlash) {
        event.preventDefault() // don't type "/" into the field we're about to focus
        latest.current.onSlash()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
