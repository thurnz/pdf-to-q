export interface ProgressViewProps {
  status: 'uploading' | 'queued' | 'processing'
  progress: number // 0.0 to 1.0
  fileName?: string
}

function getProgressWidthClass(percent: number): string {
  if (percent <= 0) return 'w-0'
  if (percent <= 10) return 'w-[10%]'
  if (percent <= 20) return 'w-[20%]'
  if (percent <= 30) return 'w-[30%]'
  if (percent <= 40) return 'w-[40%]'
  if (percent <= 50) return 'w-[50%]'
  if (percent <= 60) return 'w-[60%]'
  if (percent <= 70) return 'w-[70%]'
  if (percent <= 80) return 'w-[80%]'
  if (percent <= 90) return 'w-[90%]'
  return 'w-full'
}

function getStatusDescription(
  status: 'uploading' | 'queued' | 'processing',
  progress: number,
): string {
  if (status === 'uploading') {
    return 'Uploading your PDF document...'
  }
  if (status === 'queued') {
    return 'Queued in line, preparing processing...'
  }
  if (progress < 0.35) {
    return 'Extracting text and verifying pages...'
  }
  if (progress < 0.75) {
    return 'Generating question-and-answer pairs...'
  }
  return 'Formatting and assembling PDF study guide...'
}

export function ProgressView({ status, progress, fileName }: ProgressViewProps) {
  const percent = Math.min(100, Math.max(0, Math.round(progress * 100)))
  const description = getStatusDescription(status, progress)
  const widthClass = getProgressWidthClass(percent)

  return (
    <div className="w-full rounded-xl border border-border bg-white p-6 sm:p-8 flex flex-col items-center gap-6 shadow-xs">
      <div className="flex flex-col items-center gap-2 text-center max-w-md">
        {fileName && (
          <span className="text-xs font-semibold text-muted tracking-wide uppercase truncate max-w-xs">
            {fileName}
          </span>
        )}
        <div aria-live="polite" className="text-lg font-semibold text-heading">
          {description}
        </div>
        <p className="text-xs text-muted">
          This usually takes 10 to 30 seconds depending on document length.
        </p>
      </div>

      <div className="w-full max-w-md flex flex-col gap-2">
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Generation progress"
          className="w-full bg-border rounded-full h-3 overflow-hidden"
        >
          <div
            className={`bg-primary h-full rounded-full transition-all duration-300 ${widthClass}`}
          />
        </div>
        <div className="flex justify-between items-center text-xs text-muted px-0.5">
          <span>{status === 'uploading' ? 'Upload' : 'Processing'}</span>
          <span className="font-semibold text-heading">{percent}%</span>
        </div>
      </div>
    </div>
  )
}
