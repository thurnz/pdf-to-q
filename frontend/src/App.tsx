import { useEffect, useState } from 'react'
import { createJob } from './api/client'
import { ErrorView } from './components/ErrorView'
import { OptionsForm } from './components/OptionsForm'
import { ProgressView } from './components/ProgressView'
import { ResultView } from './components/ResultView'
import { UploadDropzone } from './components/UploadDropzone'
import { useJobPolling } from './hooks/useJobPolling'
import type { GenerationOptions } from './types'
import { validateFile } from './utils/validateFile'

type AppState = 'idle' | 'uploading' | 'processing' | 'done' | 'failed'

const DEFAULT_OPTIONS: GenerationOptions = {
  num_questions: 10,
  difficulty: 'medium',
  detail: 'short',
}

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [options, setOptions] = useState<GenerationOptions>(DEFAULT_OPTIONS)
  const [jobId, setJobId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Poll only while processing
  const { job, error: pollError } = useJobPolling(appState === 'processing' ? jobId : null)

  useEffect(() => {
    if (appState !== 'processing') return

    if (job?.status === 'done') {
      setAppState('done')
    } else if (job?.status === 'failed') {
      setAppState('failed')
      setErrorMessage(job.error || 'Study guide generation failed.')
    } else if (pollError) {
      setAppState('failed')
      setErrorMessage(pollError)
    }
  }, [appState, job, pollError])

  const handleFileSelect = (file: File | null) => {
    if (!file) {
      setSelectedFile(null)
      setFileError(null)
      return
    }

    const validation = validateFile(file)
    setSelectedFile(file)
    setFileError(validation)
  }

  const handleSubmit = async () => {
    if (!selectedFile || fileError) return

    setAppState('uploading')
    setErrorMessage(null)

    try {
      const response = await createJob(selectedFile, options)
      setJobId(response.id)
      setAppState('processing')
    } catch (err: unknown) {
      setAppState('failed')
      const message = err instanceof Error ? err.message : 'Failed to submit document.'
      setErrorMessage(message)
    }
  }

  const handleRetry = () => {
    setAppState('idle')
    setJobId(null)
    setErrorMessage(null)
  }

  const handleReset = () => {
    setAppState('idle')
    setJobId(null)
    setSelectedFile(null)
    setFileError(null)
    setErrorMessage(null)
    setOptions(DEFAULT_OPTIONS)
  }

  return (
    <main className="min-h-screen bg-page text-body flex flex-col items-center px-4 py-12 sm:py-20">
      {/* ── Header ───────────────────────────────────────── */}
      <header className="w-full max-w-2xl mb-10 text-center sm:text-left">
        <h1 className="text-4xl sm:text-5xl font-bold font-display text-heading leading-tight mb-4">
          Study Guide Generator
        </h1>
        <p className="text-lg text-muted leading-relaxed max-w-prose">
          Upload a PDF — lecture notes, a chapter, a paper — and get a focused question-and-answer
          study guide back as a PDF you can print or annotate.
        </p>
      </header>

      {/* ── Content Area ─────────────────────────────────── */}
      <div className="w-full max-w-2xl flex flex-col items-center gap-6">
        {appState === 'idle' && (
          <div className="w-full flex flex-col gap-6">
            <UploadDropzone file={selectedFile} onFileSelect={handleFileSelect} error={fileError} />

            <OptionsForm options={options} onChange={setOptions} />

            <button
              type="button"
              onClick={handleSubmit}
              disabled={!selectedFile || Boolean(fileError)}
              className="w-full py-3 px-6 rounded-lg font-semibold bg-primary hover:bg-primary-hover text-primary-fg transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-40 disabled:cursor-not-allowed shadow-xs"
            >
              Generate Study Guide
            </button>
          </div>
        )}

        {appState === 'uploading' && (
          <ProgressView status="uploading" progress={0.08} fileName={selectedFile?.name} />
        )}

        {appState === 'processing' && (
          <ProgressView
            status={job?.status === 'queued' ? 'queued' : 'processing'}
            progress={job?.progress ?? 0.15}
            fileName={selectedFile?.name}
          />
        )}

        {appState === 'done' && jobId && <ResultView jobId={jobId} onReset={handleReset} />}

        {appState === 'failed' && (
          <ErrorView
            error={errorMessage || 'An unexpected error occurred.'}
            onRetry={handleRetry}
          />
        )}
      </div>
    </main>
  )
}
