// Mirrors the backend's pydantic response models (see /docs for the OpenAPI schema).

export type SortOrder = 'relevance' | 'latest'
export type Period = '24h' | '7d' | '30d'

export type Article = {
  id: number
  title: string
  description: string | null
  snippet: string | null
  url: string
  image_url: string | null
  source_name: string
  source_url: string | null
  published_at: string // ISO 8601
}

export type NewsSearchParams = {
  q: string
  sort: SortOrder
  period: Period | null
}

export type SearchSummary = {
  id: number
  provider: string
  query: string
  sort: SortOrder
  period: Period | null
  result_count: number
  created_at: string // ISO 8601
}

export type Search = SearchSummary & { items: Article[] }

export type SearchPage = {
  items: SearchSummary[]
  total: number
  limit: number
  offset: number
}

export type Quota = {
  provider: string
  limit: number | null
  used: number
  remaining: number | null
}
