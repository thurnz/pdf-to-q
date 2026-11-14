import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import App from '../App'
import type { JobStatus } from '../types'

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders page title and initial idle form', () => {
    render(<App />)
    expect(
      screen.getByRole('heading', { level: 1, name: /study guide generator/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /upload area/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeDisabled()
  })

  it('shows an error message when an invalid file is selected', async () => {
    const { container } = render(<App />)

    const invalidFile = new File(['dummy content'], 'document.txt', {
      type: 'text/plain',
    })
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement

    fireEvent.change(fileInput, { target: { files: [invalidFile] } })

    const errorAlert = await screen.findByRole('alert')
    expect(errorAlert).toHaveTextContent(/please upload a pdf file/i)
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeDisabled()
  })

  it('completes a successful flow and displays the correct download link', async () => {
    const user = userEvent.setup()

    vi.spyOn(client, 'createJob').mockResolvedValueOnce({
      id: 'job-success-123',
      status: 'queued',
    })

    const doneJob: JobStatus = {
      id: 'job-success-123',
      status: 'done',
      progress: 1.0,
      error: null,
    }
    vi.spyOn(client, 'getJob').mockResolvedValue(doneJob)

    const { container } = render(<App />)

    const validPdf = new File(['%PDF-1.4 dummy'], 'lecture.pdf', {
      type: 'application/pdf',
    })
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement

    await user.upload(fileInput, validPdf)

    const submitBtn = screen.getByRole('button', {
      name: /generate study guide/i,
    })
    expect(submitBtn).toBeEnabled()

    await user.click(submitBtn)

    // Verify download link appears with correct href
    const downloadLink = await screen.findByRole('link', {
      name: /download pdf guide/i,
    })
    expect(downloadLink).toBeInTheDocument()
    expect(downloadLink).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/jobs/job-success-123/download',
    )

    // Click "Make another" and verify reset
    const makeAnotherBtn = screen.getByRole('button', { name: /make another/i })
    await user.click(makeAnotherBtn)

    expect(await screen.findByRole('region', { name: /upload area/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeDisabled()
  })

  it('shows an error message on job failure and Try again resets the form', async () => {
    const user = userEvent.setup()

    vi.spyOn(client, 'createJob').mockResolvedValueOnce({
      id: 'job-fail-456',
      status: 'queued',
    })

    const failedJob: JobStatus = {
      id: 'job-fail-456',
      status: 'failed',
      progress: 0.2,
      error: 'Scanned PDF not supported yet: document contains little or no extractable text',
    }
    vi.spyOn(client, 'getJob').mockResolvedValue(failedJob)

    const { container } = render(<App />)

    const validPdf = new File(['%PDF-1.4 dummy'], 'scanned.pdf', {
      type: 'application/pdf',
    })
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement

    await user.upload(fileInput, validPdf)
    await user.click(screen.getByRole('button', { name: /generate study guide/i }))

    // Verify error message in ErrorView
    const errorAlert = await screen.findByRole('alert')
    expect(errorAlert).toHaveTextContent(/scanned pdf not supported yet/i)

    // Click "Try again"
    const tryAgainBtn = screen.getByRole('button', { name: /try again/i })
    await user.click(tryAgainBtn)

    // Should return to idle state
    expect(await screen.findByRole('region', { name: /upload area/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate study guide/i })).toBeInTheDocument()
  })
})
