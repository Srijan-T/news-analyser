// Mirrors the backend's pydantic response models (see /docs for the OpenAPI schema).

export type SortOrder = 'relevance' | 'latest'
export type Period = '24h' | '7d' | '30d'

export type Sentiment = 'positive' | 'neutral' | 'negative'

export type Analysis = {
  id: number
  article_id: number
  tldr: string
  key_points: string[]
  sentiment: Sentiment
  score: number // -1 (very negative) .. 1 (very positive)
  rationale: string
  evidence: string[] // short quotes copied from the article text
  text_source: 'snippet' | 'full'
  model: string
  prompt_version: string
  created_at: string
}

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
  analysis: Analysis | null
}

export type NewsSearchParams = {
  q: string
  sort: SortOrder
  period: Period | null
  /** Search exactly as typed: no typo correction or "match any word" fallback. */
  exact?: boolean
}

export type SearchSummary = {
  id: number
  provider: string
  query: string
  sort: SortOrder
  period: Period | null
  result_count: number
  /** What was typed, when the query that ran differs (typo corrected or broadened). */
  original_query: string | null
  /** 'any': nothing matched every word, so results match any of them. */
  match_mode: 'all' | 'any'
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

export type ArticleSort =
  | 'published_desc'
  | 'published_asc'
  | 'analyzed_desc'
  | 'score_desc'
  | 'score_asc'

/** History filters as the UI holds them (and as they appear in the URL). */
export type HistoryFilters = {
  sentiment: Sentiment | null
  source: string | null
  searchId: number | null
  within: Period | null // published within the last 24h / 7d / 30d
  sort: ArticleSort
}

export type ArticlePage = {
  items: Article[]
  total: number
  limit: number
  offset: number
}

export type Stats = {
  total: number
  by_sentiment: Record<Sentiment, number>
  average_score: number | null
  sources: string[]
}

export type BatchItemStatus = 'pending' | 'running' | 'done' | 'skipped' | 'failed'

export type AnalysisBatch = {
  id: number
  /** 'done' once no item is pending or running. */
  status: 'running' | 'done'
  counts: Record<BatchItemStatus, number>
  items: {
    article_id: number
    position: number
    /** 'skipped': the article was already analyzed. */
    status: BatchItemStatus
    error_code: string | null
    analysis: Analysis | null
  }[]
  created_at: string
}
