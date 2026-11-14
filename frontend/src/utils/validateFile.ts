export const MAX_FILE_SIZE_MB = 20
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
export const ALLOWED_MIME_TYPE = 'application/pdf'
export const ALLOWED_EXTENSION = '.pdf'

/**
 * Validates an uploaded file against client and backend PDF limits.
 *
 * @param file - The browser File instance to validate.
 * @returns A user-friendly error message if validation fails, or null if valid.
 */
export function validateFile(file: File): string | null {
  const hasPdfExtension = file.name.toLowerCase().endsWith(ALLOWED_EXTENSION)
  const hasPdfMime = file.type === ALLOWED_MIME_TYPE

  if (!hasPdfExtension && !hasPdfMime) {
    return 'Please upload a PDF file.'
  }

  if (file.size === 0) {
    return 'The selected file is empty.'
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File size exceeds the ${MAX_FILE_SIZE_MB} MB limit.`
  }

  return null
}
