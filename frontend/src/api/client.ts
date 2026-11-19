// Thin typed wrapper around fetch. Every backend error has the shape
// {"error": {"code", "message", "details"}}, which we turn into an ApiError.

import type {
  Analysis,
  Article,
  ArticlePage,
  HistoryFilters,
  NewsSearchParams,
  Quota,
  Search,
  SearchPage,
  Stats,
} from './types.ts'

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

/** Like apiFetch, but also returns the HTTP status for callers that care, e.g. 200 vs 201
 * tells "reused an existing search" apart from "created a new one". */
export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<{ data: T; status: number }> {
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

  if (res.status === 204) return { data: undefined as T, status: 204 }

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
  return { data: body as T, status: res.status }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return (await apiRequest<T>(path, init)).data
}

export type Health = { status: string; database: string }

const PERIOD_MS = { '24h': 864e5, '7d': 7 * 864e5, '30d': 30 * 864e5 } as const

/** Query string shared by /articles and /stats, so the list and the stats always match. */
function historyQuery(filters: HistoryFilters): URLSearchParams {
  const params = new URLSearchParams({ analyzed: 'true' })
  if (filters.sentiment) params.set('sentiment', filters.sentiment)
  if (filters.source) params.set('source', filters.source)
  if (filters.searchId !== null) params.set('search_id', String(filters.searchId))
  if (filters.within) {
    params.set('published_from', new Date(Date.now() - PERIOD_MS[filters.within]).toISOString())
  }
  return params
}
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
  /** `cached`: the API reused an identical search from the last 30 minutes (HTTP 200). */
  createSearch: async ({ q, sort, period }: NewsSearchParams) => {
    const { data, status } = await apiRequest<Search>('/searches', {
      method: 'POST',
      body: JSON.stringify({ q, sort, period }),
    })
    return { search: data, cached: status === 200 }
  },
  getSearch: (id: number) => apiFetch<Search>(`/searches/${id}`),
  listSearches: (limit = 10) => apiFetch<SearchPage>(`/searches?limit=${limit}`),
  quota: () => apiFetch<Quota>('/quota'),

  listArticles: (filters: HistoryFilters, limit: number, offset: number) => {
    const params = historyQuery(filters)
    params.set('sort', filters.sort)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return apiFetch<ArticlePage>(`/articles?${params}`)
  },
  stats: (filters: HistoryFilters) => apiFetch<Stats>(`/stats?${historyQuery(filters)}`),

  getArticle: (id: number) => apiFetch<Article>(`/articles/${id}`),
  /** Analyzes once; asking again returns the stored analysis without calling the AI. */
  /** `created`: a new analysis was made (HTTP 201) rather than the stored one returned. */
  analyzeArticle: async (id: number) => {
    const { data, status } = await apiRequest<Analysis>(`/articles/${id}/analysis`, {
      method: 'POST',
    })
    return { analysis: data, created: status === 201 }
  },
}
