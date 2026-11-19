// Thin typed wrapper around fetch. Every backend error has the shape
// {"error": {"code", "message", "details"}}, which we turn into an ApiError.

import type { NewsSearchParams, NewsSearchResponse } from './types.ts'

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
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
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

export type Health = { status: string }

export const api = {
  health: () => apiFetch<Health>('/health'),

  searchNews: ({ q, sort, period }: NewsSearchParams) => {
    const params = new URLSearchParams({ q, sort })
    if (period) params.set('period', period)
    return apiFetch<NewsSearchResponse>(`/news/search?${params}`)
  },
}
