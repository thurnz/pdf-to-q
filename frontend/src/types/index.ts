/**
 * Types mirroring backend/app/schemas.py
 */

export interface QAItem {
  question: string
  answer: string
  page?: number | null
}

