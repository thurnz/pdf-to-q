import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, createJob, downloadUrl, getBaseUrl, getJob } from '../api/client'

describe('API Client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('ApiError', () => {
    it('instantiates with status, message and error name', () => {
      const error = new ApiError(400, 'Invalid request')
      expect(error).toBeInstanceOf(Error)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(400)
      expect(error.message).toBe('Invalid request')
      expect(error.name).toBe('ApiError')
    })
  })

  describe('getBaseUrl', () => {
    it('defaults to http://127.0.0.1:8000 when environment variable is unset', () => {
      expect(getBaseUrl()).toBe('http://127.0.0.1:8000')
    })
  })

  describe('downloadUrl', () => {
    it('constructs the download URL correctly', () => {
      const url = downloadUrl('test-uuid-123')
      expect(url).toBe('http://127.0.0.1:8000/jobs/test-uuid-123/download')
    })

    it('escapes special characters in the job id', () => {
      const url = downloadUrl('job/with/slashes')
      expect(url).toBe('http://127.0.0.1:8000/jobs/job%2Fwith%2Fslashes/download')
    })
  })

  describe('createJob', () => {
    it('submits multipart form data and returns JobCreateResponse', async () => {
      const mockResponse = { id: 'job-123', status: 'queued' }
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(mockResponse), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const file = new File(['%PDF content'], 'sample.pdf', {
        type: 'application/pdf',
      })
      const result = await createJob(file, {
        num_questions: 15,
        difficulty: 'hard',
        detail: 'detailed',
      })

      expect(result).toEqual(mockResponse)
      expect(fetch).toHaveBeenCalledTimes(1)

      const [url, init] = vi.mocked(fetch).mock.calls[0]
      expect(url).toBe('http://127.0.0.1:8000/jobs')
      expect(init?.method).toBe('POST')

      const body = init?.body as FormData
      expect(body).toBeInstanceOf(FormData)
      expect(body.get('num_questions')).toBe('15')
      expect(body.get('difficulty')).toBe('hard')
      expect(body.get('detail')).toBe('detailed')
    })

    it('uses default generation options when not provided', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'job-def', status: 'queued' }), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const file = new File(['%PDF content'], 'sample.pdf', {
        type: 'application/pdf',
      })
      await createJob(file)

      const [, init] = vi.mocked(fetch).mock.calls[0]
      const body = init?.body as FormData
      expect(body.get('num_questions')).toBe('10')
      expect(body.get('difficulty')).toBe('medium')
      expect(body.get('detail')).toBe('short')
    })

    it('parses backend { detail } error message when present', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'The uploaded file is not a valid PDF document.' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const file = new File(['bad'], 'test.pdf')
      await expect(createJob(file)).rejects.toMatchObject({
        name: 'ApiError',
        status: 400,
        message: 'The uploaded file is not a valid PDF document.',
      })
    })

    it('returns friendly 429 message when rate limited', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(null, {
          status: 429,
          statusText: 'Too Many Requests',
        }),
      )

      const file = new File(['%PDF'], 'test.pdf')
      await expect(createJob(file)).rejects.toMatchObject({
        name: 'ApiError',
        status: 429,
        message: 'Too many uploads, wait a minute and try again',
      })
    })

    it('returns friendly message on network failure', async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

      const file = new File(['%PDF'], 'test.pdf')
      await expect(createJob(file)).rejects.toMatchObject({
        name: 'ApiError',
        status: 0,
        message: 'Network error. Please check your connection and try again.',
      })
    })
  })

  describe('getJob', () => {
    it('fetches job status successfully', async () => {
      const mockJob = {
        id: 'job-123',
        status: 'processing',
        progress: 0.5,
        error: null,
      }
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(mockJob), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const result = await getJob('job-123')
      expect(result).toEqual(mockJob)

      const [url, init] = vi.mocked(fetch).mock.calls[0]
      expect(url).toBe('http://127.0.0.1:8000/jobs/job-123')
      expect(init?.method).toBe('GET')
    })

    it('throws ApiError with status 404 when job is not found', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Job not found' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      await expect(getJob('missing-id')).rejects.toMatchObject({
        name: 'ApiError',
        status: 404,
        message: 'Job not found',
      })
    })
  })
})
