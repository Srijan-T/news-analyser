import { useEffect, useState } from 'react'
import {
  type ThemePreference,
  applyTheme,
  followSystemTheme,
  getThemePreference,
  setThemePreference,
} from '../lib/theme.ts'

const OPTIONS: { value: ThemePreference; label: string; icon: string }[] = [
  { value: 'system', label: 'Match system theme', icon: '◐' },
  { value: 'light', label: 'Light theme', icon: '☀' },
  { value: 'dark', label: 'Dark theme', icon: '☾' },
]

/** Three-way switch: System / Light / Dark. */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference)

  // Sync the page with the preference on mount (in case the inline script in index.html
  // couldn't), then follow OS changes while on 'system'. The DOM class and the OS theme
  // are external systems, so an effect fits here.
  useEffect(() => {
    applyTheme(preference)
    return followSystemTheme(preference)
  }, [preference])

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="flex rounded-md border border-line bg-subtle p-0.5"
    >
      {OPTIONS.map((option) => {
        const active = option.value === preference
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={option.label}
            title={option.label}
            onClick={() => {
              setThemePreference(option.value)
              setPreference(option.value)
            }}
            className={`h-6 w-7 rounded text-xs leading-none ${
              active ? 'bg-surface text-fg shadow-sm' : 'text-muted hover:text-fg'
            }`}
          >
            {option.icon}
          </button>
        )
      })}
    </div>
  )
}
