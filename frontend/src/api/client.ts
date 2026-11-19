// Thin typed wrapper around fetch. Every backend error has the shape
// {"error": {"code", "message", "details"}}, which we turn into an ApiError.

import type { Analysis, Article, NewsSearchParams, Quota, Search, SearchPage } from './types.ts'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

type ErrorBody = { error?: { code?: string; message?: string; details?: unknown } }

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Absolute URL from the origin, not a relative path: if the page was opened via a
  // https://user:pass@host link (basic auth), the page's base URL keeps those credentials and
  // the browser refuses relative fetches. The origin never includes them, and the browser
  // still sends the cached login.
  const url = new URL(`/api${path}`, window.location.origin)
  let res: Response
  try {
    res = await fetch(url, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the server')
  }

  if (res.status === 204) return undefined as T

  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const err = (body as ErrorBody | null)?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'http_error',
      err?.message ?? `Request failed (${res.status})`,
      err?.details ?? null,
    )
  }
  return body as T
}

export type Health = { status: string; database: string }
export type Session = { auth_required: boolean; authenticated: boolean }

/** TanStack Query cache key for the session; invalidate it to re-check sign-in. */
export const SESSION_KEY = ['session']

/** True for a 401 meaning "not signed in / session expired". */
export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'unauthenticated'
}

export const api = {
  health: () => apiFetch<Health>('/health'),

  session: () => apiFetch<Session>('/auth/session'),
  login: (password: string) =>
    apiFetch<void>('/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  logout: () => apiFetch<void>('/auth/logout', { method: 'POST' }),

  /** Runs a search, or returns an identical one from the last 30 minutes (no quota spent). */
  createSearch: ({ q, sort, period }: NewsSearchParams) =>
    apiFetch<Search>('/searches', { method: 'POST', body: JSON.stringify({ q, sort, period }) }),
  getSearch: (id: number) => apiFetch<Search>(`/searches/${id}`),
  listSearches: (limit = 10) => apiFetch<SearchPage>(`/searches?limit=${limit}`),
  quota: () => apiFetch<Quota>('/quota'),

  getArticle: (id: number) => apiFetch<Article>(`/articles/${id}`),
  /** Analyzes once; asking again returns the stored analysis without calling the AI. */
  analyzeArticle: (id: number) =>
    apiFetch<Analysis>(`/articles/${id}/analysis`, { method: 'POST' }),
}
