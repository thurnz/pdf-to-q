import { useEffect, useState } from 'react'
import { ApiError, getJob } from '../api/client'
import type { JobStatus } from '../types'

export const POLL_INTERVAL_MS = 2000
export const MAX_CONSECUTIVE_ERRORS = 5

export interface UseJobPollingResult {
  job: JobStatus | null
  error: string | null
  isPolling: boolean
}

/**
 * React hook that polls job status every 2 seconds until completion or terminal failure.
 *
 * @param jobId - ID of the job to poll, or null/undefined to stay idle.
 */
export function useJobPolling(jobId: string | null | undefined): UseJobPollingResult {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState<boolean>(false)

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      setError(null)
      setIsPolling(false)
      return
    }

    const abortController = new AbortController()
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    let consecutiveErrors = 0
    let isCancelled = false

    setJob(null)
    setError(null)
    setIsPolling(true)

    const poll = async () => {
      if (isCancelled || abortController.signal.aborted) {
        return
      }

      try {
        const result = await getJob(jobId, abortController.signal)
        if (isCancelled || abortController.signal.aborted) {
          return
        }

        consecutiveErrors = 0
        setJob(result)

        if (result.status === 'done' || result.status === 'failed') {
          setIsPolling(false)
          if (result.status === 'failed' && result.error) {
            setError(result.error)
          }
          return
        }

        timeoutId = setTimeout(poll, POLL_INTERVAL_MS)
      } catch (err: unknown) {
        if (
          isCancelled ||
          abortController.signal.aborted ||
          (err && typeof err === 'object' && 'name' in err && err.name === 'AbortError')
        ) {
          return
        }

        // Fatal client error like 404 (Job not found) terminates immediately
        if (err instanceof ApiError && err.status === 404) {
          setIsPolling(false)
          setError(err.message)
          return
        }

        consecutiveErrors += 1
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          setIsPolling(false)
          setError(
            err instanceof ApiError && err.status !== 0
              ? err.message
              : 'Failed to reach server after multiple attempts. Please check your connection.',
          )
          return
        }

        timeoutId = setTimeout(poll, POLL_INTERVAL_MS)
      }
    }

    void poll()

    return () => {
      isCancelled = true
      abortController.abort()
      if (timeoutId !== null) {
        clearTimeout(timeoutId)
      }
      setIsPolling(false)
    }
  }, [jobId])

  return { job, error, isPolling }
}
