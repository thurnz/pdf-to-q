export interface ErrorViewProps {
  error: string
  onRetry: () => void
}

export function ErrorView({ error, onRetry }: ErrorViewProps) {
  return (
    <div className="w-full rounded-xl border border-red-200 bg-white p-6 sm:p-10 flex flex-col items-center gap-6 text-center shadow-xs">
      <div className="w-14 h-14 rounded-full bg-red-50 border border-red-200 text-red-600 flex items-center justify-center">
        <svg
          aria-hidden="true"
          className="w-7 h-7"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>

      <div className="flex flex-col gap-2 max-w-md">
        <h2 className="text-2xl font-bold font-display text-heading">Generation Failed</h2>
        <div
          role="alert"
          className="rounded-lg bg-red-50 border border-red-200 p-3.5 text-sm text-red-800 leading-relaxed text-left"
        >
          {error}
        </div>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary hover:bg-primary-hover text-primary-fg font-medium px-6 py-2.5 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 shadow-xs"
      >
        Try again
      </button>
    </div>
  )
}
