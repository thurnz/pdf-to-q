/**
 * Types mirroring backend/app/schemas.py
 */

export interface QAItem {
  question: string
  answer: string
  page?: number | null
}

export type Difficulty = 'easy' | 'medium' | 'hard'
export type Detail = 'short' | 'detailed'

export interface GenerationOptions {
  num_questions: number
  difficulty: Difficulty
  detail: Detail
}

export interface QAGenerationResult {
  questions: QAItem[]
}
