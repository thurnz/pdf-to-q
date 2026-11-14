import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { POLL_INTERVAL_MS, useJobPolling } from '../hooks/useJobPolling'
import type { JobStatus } from '../types'

describe('useJobPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('remains idle and does not poll when jobId is null', () => {
    const getJobSpy = vi.spyOn(client, 'getJob')
    const { result } = renderHook(() => useJobPolling(null))

    expect(result.current.isPolling).toBe(false)
    expect(result.current.job).toBeNull()
    expect(result.current.error).toBeNull()
    expect(getJobSpy).not.toHaveBeenCalled()
  })

  it('polls every 2 seconds until status is done', async () => {
    const queuedJob: JobStatus = {
      id: 'job-1',
      status: 'queued',
      progress: 0.1,
      error: null,
    }
    const processingJob: JobStatus = {
      id: 'job-1',
      status: 'processing',
      progress: 0.6,
      error: null,
    }
    const doneJob: JobStatus = {
      id: 'job-1',
      status: 'done',
      progress: 1.0,
      error: null,
    }

    const getJobSpy = vi
      .spyOn(client, 'getJob')
      .mockResolvedValueOnce(queuedJob)
      .mockResolvedValueOnce(processingJob)
      .mockResolvedValueOnce(doneJob)

    const { result } = renderHook(() => useJobPolling('job-1'))

    expect(result.current.isPolling).toBe(true)

    // Await first poll microtasks
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.job).toEqual(queuedJob)
    expect(result.current.isPolling).toBe(true)

    // Advance 2 seconds -> second poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(result.current.job).toEqual(processingJob)
    expect(result.current.isPolling).toBe(true)

    // Advance 2 seconds -> third poll (done)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(result.current.job).toEqual(doneJob)
    expect(result.current.isPolling).toBe(false)

    // Advance more time to confirm polling has stopped
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(3)
  })

  it('stops polling and sets error if job status is failed', async () => {
    const failedJob: JobStatus = {
      id: 'job-fail',
      status: 'failed',
      progress: 0.3,
      error: 'Scanned PDF not supported yet: document contains little or no extractable text',
    }

    const getJobSpy = vi.spyOn(client, 'getJob').mockResolvedValueOnce(failedJob)

    const { result } = renderHook(() => useJobPolling('job-fail'))

    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.job).toEqual(failedJob)
    expect(result.current.isPolling).toBe(false)
    expect(result.current.error).toBe(failedJob.error)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(1)
  })

  it('stops polling when unmounted', async () => {
    let capturedSignal: AbortSignal | undefined

    vi.spyOn(client, 'getJob').mockImplementation((_id, signal) => {
      capturedSignal = signal
      return new Promise(() => {
        // Pending promise that does not resolve
      })
    })

    const { unmount } = renderHook(() => useJobPolling('job-unmount'))

    expect(capturedSignal).toBeDefined()
    expect(capturedSignal?.aborted).toBe(false)

    unmount()

    expect(capturedSignal?.aborted).toBe(true)
  })

  it('stops with an error after 5 consecutive network failures', async () => {
    const networkError = new client.ApiError(
      0,
      'Network error. Please check your connection and try again.',
    )
    const getJobSpy = vi.spyOn(client, 'getJob').mockRejectedValue(networkError)

    const { result } = renderHook(() => useJobPolling('job-net-fail'))

    // 1st attempt
    await act(async () => {
      await Promise.resolve()
    })
    expect(getJobSpy).toHaveBeenCalledTimes(1)
    expect(result.current.isPolling).toBe(true)

    // 2nd attempt
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(2)
    expect(result.current.isPolling).toBe(true)

    // 3rd attempt
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(3)
    expect(result.current.isPolling).toBe(true)

    // 4th attempt
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(4)
    expect(result.current.isPolling).toBe(true)

    // 5th attempt (hits threshold)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(5)
    expect(result.current.isPolling).toBe(false)
    expect(result.current.error).toBe(
      'Failed to reach server after multiple attempts. Please check your connection.',
    )

    // Advance further to verify no 6th poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(5)
  })

  it('resets consecutive error counter on a successful poll', async () => {
    const networkError = new client.ApiError(
      0,
      'Network error. Please check your connection and try again.',
    )
    const successJob: JobStatus = {
      id: 'job-recover',
      status: 'processing',
      progress: 0.4,
      error: null,
    }

    const getJobSpy = vi
      .spyOn(client, 'getJob')
      .mockRejectedValueOnce(networkError)
      .mockRejectedValueOnce(networkError)
      .mockResolvedValueOnce(successJob)
      .mockResolvedValueOnce({ ...successJob, status: 'done', progress: 1.0 })

    const { result } = renderHook(() => useJobPolling('job-recover'))

    // 1st attempt (fail)
    await act(async () => {
      await Promise.resolve()
    })
    expect(getJobSpy).toHaveBeenCalledTimes(1)

    // 2nd attempt (fail)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(2)

    // 3rd attempt (success)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(3)
    expect(result.current.job).toEqual(successJob)

    // 4th attempt (done)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(getJobSpy).toHaveBeenCalledTimes(4)
    expect(result.current.isPolling).toBe(false)
  })
})
