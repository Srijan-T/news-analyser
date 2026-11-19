// Theme preference: 'system' follows the OS; 'light' / 'dark' override it.
// index.html runs the same logic inline before first paint, so there's no flash of the
// wrong theme on load; keep the two in sync (storage key and class name).

export type ThemePreference = 'system' | 'light' | 'dark'

export const THEME_STORAGE_KEY = 'theme'
const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

export function getThemePreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Storage can be blocked (private mode, strict settings); fall back to the OS.
  }
  return 'system'
}

export function setThemePreference(preference: ThemePreference): void {
  try {
    if (preference === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
    else localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // Not remembered, but still applied for this visit.
  }
  applyTheme(preference)
}

export function applyTheme(preference: ThemePreference): void {
  const dark = preference === 'dark' || (preference === 'system' && darkQuery().matches)
  document.documentElement.classList.toggle('dark', dark)
}

/** While the preference is 'system', follow OS theme changes live. Returns a cleanup. */
export function followSystemTheme(preference: ThemePreference): () => void {
  if (preference !== 'system') return () => {}
  const query = darkQuery()
  const onChange = () => applyTheme('system')
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}
