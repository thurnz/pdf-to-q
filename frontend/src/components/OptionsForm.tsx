import { type ChangeEvent } from 'react'
import type { Detail, Difficulty, GenerationOptions } from '../types'

export interface OptionsFormProps {
  options: GenerationOptions
  onChange: (options: GenerationOptions) => void
  disabled?: boolean
}

export function OptionsForm({ options, onChange, disabled = false }: OptionsFormProps) {
  const handleCountChange = (e: ChangeEvent<HTMLInputElement>) => {
    const raw = parseInt(e.target.value, 10)
    const val = Number.isNaN(raw) ? 10 : Math.max(1, Math.min(50, raw))
    onChange({
      ...options,
      num_questions: val,
    })
  }

  const handleDifficultyChange = (e: ChangeEvent<HTMLSelectElement>) => {
    onChange({
      ...options,
      difficulty: e.target.value as Difficulty,
    })
  }

  const handleDetailChange = (e: ChangeEvent<HTMLSelectElement>) => {
    onChange({
      ...options,
      detail: e.target.value as Detail,
    })
  }

  return (
    <fieldset
      disabled={disabled}
      className="w-full rounded-xl border border-border bg-white p-5 sm:p-6 flex flex-col gap-5 shadow-xs"
    >
      <legend className="text-sm font-semibold text-heading px-1">Study Guide Settings</legend>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Number of Questions */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="options-num-questions" className="text-xs font-semibold text-heading">
            Question Count
          </label>
          <input
            id="options-num-questions"
            type="number"
            min={1}
            max={50}
            value={options.num_questions}
            onChange={handleCountChange}
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-heading placeholder:text-muted focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary disabled:opacity-50"
          />
          <span className="text-[11px] text-muted">1 to 50 questions</span>
        </div>

        {/* Difficulty */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="options-difficulty" className="text-xs font-semibold text-heading">
            Difficulty
          </label>
          <select
            id="options-difficulty"
            value={options.difficulty}
            onChange={handleDifficultyChange}
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-heading focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary disabled:opacity-50"
          >
            <option value="easy">Easy (Definitions & recall)</option>
            <option value="medium">Medium (Concepts & explanation)</option>
            <option value="hard">Hard (Analysis & application)</option>
          </select>
          <span className="text-[11px] text-muted">Target cognitive depth</span>
        </div>

        {/* Detail Level */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="options-detail" className="text-xs font-semibold text-heading">
            Answer Length
          </label>
          <select
            id="options-detail"
            value={options.detail}
            onChange={handleDetailChange}
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-heading focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary disabled:opacity-50"
          >
            <option value="short">Short (1–2 concise sentences)</option>
            <option value="detailed">Detailed (3–5 sentences)</option>
          </select>
          <span className="text-[11px] text-muted">Concise vs comprehensive</span>
        </div>
      </div>
    </fieldset>
  )
}
