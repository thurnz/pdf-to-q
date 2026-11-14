import type { GenerationOptions, JobCreateResponse, JobStatus } from '../types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

export function getBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/+$/, '')
  }
  return 'http://127.0.0.1:8000'
}

async function parseErrorResponse(response: Response): Promise<string> {
  let detailMsg: string | undefined

  try {
    const data = await response.json()
    if (data && typeof data.detail === 'string' && data.detail.trim() !== '') {
      detailMsg = data.detail.trim()
    } else if (
      data &&
      Array.isArray(data.detail) &&
      data.detail.length > 0 &&
      typeof data.detail[0]?.msg === 'string'
    ) {
      detailMsg = data.detail[0].msg
    }
  } catch {
    // Response body is not JSON or empty; fall through to defaults
  }

  if (response.status === 429) {
    return detailMsg || 'Too many uploads, wait a minute and try again'
  }

  if (detailMsg) {
    return detailMsg
  }

  return response.statusText || `Request failed with status ${response.status}`
}

function isAbortError(err: unknown): boolean {
  return Boolean(
    err &&
    typeof err === 'object' &&
    'name' in err &&
    (err as { name?: unknown }).name === 'AbortError',
  )
}

export async function createJob(
  file: File,
  options?: Partial<GenerationOptions>,
): Promise<JobCreateResponse> {
  const baseUrl = getBaseUrl()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('num_questions', String(options?.num_questions ?? 10))
  formData.append('difficulty', options?.difficulty ?? 'medium')
  formData.append('detail', options?.detail ?? 'short')

  let response: Response
  try {
    response = await fetch(`${baseUrl}/jobs`, {
      method: 'POST',
      body: formData,
    })
  } catch (err: unknown) {
    if (isAbortError(err)) {
      throw err
    }
    throw new ApiError(0, 'Network error. Please check your connection and try again.')
  }

  if (!response.ok) {
    const message = await parseErrorResponse(response)
    throw new ApiError(response.status, message)
  }

  try {
    const data = (await response.json()) as JobCreateResponse
    return data
  } catch {
    throw new ApiError(response.status, 'Invalid server response.')
  }
}

export async function getJob(id: string, signal?: AbortSignal): Promise<JobStatus> {
  const baseUrl = getBaseUrl()
  let response: Response
  try {
    response = await fetch(`${baseUrl}/jobs/${encodeURIComponent(id)}`, {
      method: 'GET',
      signal,
    })
  } catch (err: unknown) {
    if (isAbortError(err)) {
      throw err
    }
    throw new ApiError(0, 'Network error. Please check your connection and try again.')
  }

  if (!response.ok) {
    const message = await parseErrorResponse(response)
    throw new ApiError(response.status, message)
  }

  try {
    const data = (await response.json()) as JobStatus
    return data
  } catch {
    throw new ApiError(response.status, 'Invalid server response.')
  }
}

export function downloadUrl(id: string): string {
  const baseUrl = getBaseUrl()
  return `${baseUrl}/jobs/${encodeURIComponent(id)}/download`
}
