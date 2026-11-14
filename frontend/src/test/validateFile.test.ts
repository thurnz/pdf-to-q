import { describe, expect, it } from 'vitest'
import {
  ALLOWED_EXTENSION,
  ALLOWED_MIME_TYPE,
  MAX_FILE_SIZE_BYTES,
  MAX_FILE_SIZE_MB,
  validateFile,
} from '../utils/validateFile'

describe('validateFile', () => {
  it('exports expected named constants', () => {
    expect(MAX_FILE_SIZE_MB).toBe(20)
    expect(MAX_FILE_SIZE_BYTES).toBe(20 * 1024 * 1024)
    expect(ALLOWED_MIME_TYPE).toBe('application/pdf')
    expect(ALLOWED_EXTENSION).toBe('.pdf')
  })

  it('accepts a valid PDF file with application/pdf MIME type', () => {
    const file = new File(['%PDF-1.4 dummy content'], 'notes.pdf', {
      type: 'application/pdf',
    })
    expect(validateFile(file)).toBeNull()
  })

  it('accepts a valid PDF file by .pdf extension even if MIME type is empty or generic', () => {
    const file = new File(['%PDF-1.4 dummy content'], 'assignment.pdf', {
      type: '',
    })
    expect(validateFile(file)).toBeNull()
  })

  it('accepts a file with uppercase .PDF extension', () => {
    const file = new File(['%PDF-1.4 dummy content'], 'DOCUMENT.PDF', {
      type: 'application/octet-stream',
    })
    expect(validateFile(file)).toBeNull()
  })

  it('rejects a non-PDF file by extension and MIME type', () => {
    const file = new File(['image data'], 'photo.png', {
      type: 'image/png',
    })
    const error = validateFile(file)
    expect(error).toBe('Please upload a PDF file.')
  })

  it('rejects an empty 0-byte file', () => {
    const file = new File([], 'empty.pdf', {
      type: 'application/pdf',
    })
    const error = validateFile(file)
    expect(error).toBe('The selected file is empty.')
  })

  it('rejects a file exceeding the 20 MB limit', () => {
    // Construct a File object mock with size slightly above MAX_FILE_SIZE_BYTES
    const oversizedFile = new File([''], 'huge.pdf', { type: 'application/pdf' })
    Object.defineProperty(oversizedFile, 'size', {
      value: MAX_FILE_SIZE_BYTES + 1,
      configurable: true,
    })

    const error = validateFile(oversizedFile)
    expect(error).toContain('20 MB limit')
  })

  it('accepts a file at exactly the 20 MB limit', () => {
    const exactFile = new File(['dummy'], 'exact.pdf', { type: 'application/pdf' })
    Object.defineProperty(exactFile, 'size', {
      value: MAX_FILE_SIZE_BYTES,
      configurable: true,
    })

    expect(validateFile(exactFile)).toBeNull()
  })
})

