import { downloadUrl } from '../api/client'

export interface ResultViewProps {
  jobId: string
  onReset: () => void
}

export function ResultView({ jobId, onReset }: ResultViewProps) {
  const url = downloadUrl(jobId)

  return (
    <div className="w-full rounded-xl border border-border bg-white p-6 sm:p-10 flex flex-col items-center gap-6 text-center shadow-xs">
      <div className="w-14 h-14 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center">
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
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>

      <div className="flex flex-col gap-2 max-w-md">
        <h2 className="text-2xl font-bold font-display text-heading">Your Study Guide is Ready!</h2>
        <p className="text-sm text-muted leading-relaxed">
          Questions and grounded answers have been compiled into a printable PDF study guide.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto mt-2">
        <a
          href={url}
          download
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-lg bg-primary hover:bg-primary-hover text-primary-fg font-medium px-6 py-3 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 shadow-xs"
        >
          <svg
            aria-hidden="true"
            className="w-5 h-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download PDF Guide
        </a>

        <button
          type="button"
          onClick={onReset}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-white hover:bg-page text-heading font-medium px-5 py-3 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Make another
        </button>
      </div>
    </div>
  )
}
