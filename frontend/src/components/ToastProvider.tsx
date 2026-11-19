import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { type ToastTone, ToastContext } from '../lib/toast.ts'

type Toast = { id: number; message: string; tone: ToastTone }

const DURATION_MS = 4500
const MAX_VISIBLE = 3

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id))
    timers.current.delete(id)
    setToasts((all) => all.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (message: string, tone: ToastTone = 'info') => {
      const id = nextId.current++
      setToasts((all) => [...all, { id, message, tone }].slice(-MAX_VISIBLE))
      timers.current.set(
        id,
        window.setTimeout(() => dismiss(id), DURATION_MS),
      )
    },
    [dismiss],
  )

  // Clear any pending timers if the provider unmounts.
  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => window.clearTimeout(timer))
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      {/* Always rendered, so screen readers announce toasts as they're added. */}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto flex items-start gap-3 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-fg shadow-lg"
          >
            <span
              aria-hidden="true"
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                toast.tone === 'success' ? 'bg-emerald-500' : 'bg-sky-500'
              }`}
            />
            <p className="flex-1">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss"
              className="text-muted hover:text-fg"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
