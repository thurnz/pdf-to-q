import { useState, type ChangeEvent, type DragEvent } from 'react'

export interface UploadDropzoneProps {
  file: File | null
  onFileSelect: (file: File | null) => void
  error: string | null
  disabled?: boolean
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

export function UploadDropzone({
  file,
  onFileSelect,
  error,
  disabled = false,
}: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (disabled) return
    setIsDragOver(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    if (disabled) return

    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      onFileSelect(droppedFile)
    }
  }

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) {
      onFileSelect(selected)
    }
    // Reset value so re-selecting the same file triggers change
    e.target.value = ''
  }

  const handleRemove = () => {
    if (disabled) return
    onFileSelect(null)
  }

  return (
    <div className="w-full flex flex-col gap-3">
      <section
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`w-full rounded-xl border-2 border-dashed p-8 sm:p-10 text-center transition-colors flex flex-col items-center justify-center gap-4 ${
          isDragOver
            ? 'border-primary bg-zone-bg/80'
            : 'border-border bg-zone-bg/50 hover:bg-zone-bg'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        aria-label="Upload area"
      >
        <input
          id="pdf-upload-input"
          type="file"
          accept=".pdf,application/pdf"
          disabled={disabled}
          onChange={handleFileInputChange}
          className="sr-only"
        />

        {/* Cloud Upload Icon */}
        <div className="w-12 h-12 rounded-full bg-white shadow-xs border border-border flex items-center justify-center text-primary">
          <svg
            aria-hidden="true"
            className="w-6 h-6"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="16 16 12 12 8 16" />
            <line x1="12" y1="12" x2="12" y2="21" />
            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
          </svg>
        </div>

        {file ? (
          <div className="flex flex-col items-center gap-1.5 max-w-full">
            <p className="text-base font-semibold text-heading truncate max-w-sm sm:max-w-md">
              {file.name}
            </p>
            <p className="text-xs text-muted">{formatFileSize(file.size)}</p>
            <div className="flex items-center gap-2 mt-2">
              <label
                htmlFor="pdf-upload-input"
                className={`text-xs font-medium text-primary hover:text-primary-hover underline cursor-pointer focus-visible:ring-2 focus-visible:ring-primary rounded px-1.5 py-0.5 ${
                  disabled ? 'pointer-events-none' : ''
                }`}
              >
                Choose another file
              </label>
              <span className="text-muted text-xs" aria-hidden="true">
                •
              </span>
              <button
                type="button"
                onClick={handleRemove}
                disabled={disabled}
                className="text-xs font-medium text-red-600 hover:text-red-700 underline focus-visible:ring-2 focus-visible:ring-red-500 rounded px-1.5 py-0.5"
              >
                Remove
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5">
            <p className="text-base font-medium text-heading">Drag and drop your PDF here</p>
            <p className="text-sm text-muted">
              or{' '}
              <label
                htmlFor="pdf-upload-input"
                className={`font-semibold text-primary hover:text-primary-hover underline cursor-pointer focus-visible:ring-2 focus-visible:ring-primary rounded px-1 py-0.5 ${
                  disabled ? 'pointer-events-none' : ''
                }`}
              >
                choose a file
              </label>
            </p>
            <p className="text-xs text-muted mt-1">Supports standard text PDFs up to 20 MB</p>
          </div>
        )}
      </section>

      {error && (
        <div
          role="alert"
          className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3 flex items-start gap-2.5"
        >
          <svg
            aria-hidden="true"
            className="w-5 h-5 shrink-0 text-red-500 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
              clipRule="evenodd"
            />
          </svg>
          <span className="leading-snug">{error}</span>
        </div>
      )}
    </div>
  )
}
