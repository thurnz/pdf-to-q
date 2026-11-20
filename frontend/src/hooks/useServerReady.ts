import { useEffect, useRef, useState } from 'react'
import { getBaseUrl } from '../api/client'

/** How long to wait before showing the "waking up" banner (ms). */
export const WAKEUP_NOTICE_DELAY_MS = 3000

export type ServerReadyState = 'checking' | 'waking' | 'ready' | 'error'

export interface UseServerReadyResult {
  serverState: ServerReadyState
  /** User-facing notice message when state is 'waking' or 'error'. */
  notice: string | null
}

/**
 * On mount, pings GET /health once.
 * - If it responds within WAKEUP_NOTICE_DELAY_MS  → state becomes 'ready' silently.
 * - If it takes longer                           → state becomes 'waking' (show banner).
 * - Once the response arrives after waking       → state becomes 'ready'.
 * - If the fetch fails (network error)           → state becomes 'error'.
 */
export function useServerReady(): UseServerReadyResult {
  const [serverState, setServerState] = useState<ServerReadyState>('checking')
  const [notice, setNotice] = useState<string | null>(null)
  // Ref so the timer callback can read the latest state without stale closure
  const isResolvedRef = useRef(false)

  useEffect(() => {
    let wakeTimer: ReturnType<typeof setTimeout> | null = null

    wakeTimer = setTimeout(() => {
      if (!isResolvedRef.current) {
        setServerState('waking')
        setNotice('Waking up the server, this can take up to a minute…')
      }
    }, WAKEUP_NOTICE_DELAY_MS)

    const controller = new AbortController()

    fetch(`${getBaseUrl()}/health`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
        return res.json()
      })
      .then(() => {
        isResolvedRef.current = true
        if (wakeTimer !== null) clearTimeout(wakeTimer)
        setServerState('ready')
        setNotice(null)
      })
      .catch((err: unknown) => {
        if (
          err &&
          typeof err === 'object' &&
          'name' in err &&
          (err as { name?: unknown }).name === 'AbortError'
        ) {
          return // component unmounted
        }
        isResolvedRef.current = true
        if (wakeTimer !== null) clearTimeout(wakeTimer)
        setServerState('error')
        setNotice(
          'Could not reach the server. Please check your connection and refresh the page.',
        )
      })

    return () => {
      if (wakeTimer !== null) clearTimeout(wakeTimer)
      controller.abort()
    }
  }, [])

  return { serverState, notice }
}
