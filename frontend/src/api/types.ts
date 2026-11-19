// Mirrors the backend's pydantic response models (see /docs for the OpenAPI schema).

export type SortOrder = 'relevance' | 'latest'
export type Period = '24h' | '7d' | '30d'

export type Article = {
  provider: string
  provider_article_id: string
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

export type NewsSearchResponse = {
  provider: string
  query: string
  items: Article[]
}
