import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WAKEUP_NOTICE_DELAY_MS, useServerReady } from '../hooks/useServerReady'

/** Flush all pending promises/microtasks. */
async function flushMicrotasks(rounds = 4) {
  for (let i = 0; i < rounds; i++) {
    await act(async () => {
      await Promise.resolve()
    })
  }
}

describe('useServerReady', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('transitions to ready immediately when health responds within 3 s', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    )

    const { result } = renderHook(() => useServerReady())
    expect(result.current.serverState).toBe('checking')

    // Drain fetch microtasks (resolved promise → .then → setState)
    await flushMicrotasks()

    expect(result.current.serverState).toBe('ready')
    expect(result.current.notice).toBeNull()
  })

  it('shows waking notice after 3 s when health is slow, then clears on success', async () => {
    let resolveHealth!: () => void
    const healthPromise = new Promise<Response>((res) => {
      resolveHealth = () => res(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    })
    vi.mocked(fetch).mockReturnValueOnce(healthPromise)

    const { result } = renderHook(() => useServerReady())
    expect(result.current.serverState).toBe('checking')

    // Advance past the 3 s threshold → setTimeout fires → setState('waking')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WAKEUP_NOTICE_DELAY_MS + 100)
    })

    expect(result.current.serverState).toBe('waking')
    expect(result.current.notice).toMatch(/waking up/i)

    // Resolve the slow health call
    await act(async () => {
      resolveHealth()
    })
    await flushMicrotasks()

    expect(result.current.serverState).toBe('ready')
    expect(result.current.notice).toBeNull()
  })

  it('transitions to error when health fetch fails', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const { result } = renderHook(() => useServerReady())

    await flushMicrotasks()

    expect(result.current.serverState).toBe('error')
    expect(result.current.notice).toMatch(/could not reach the server/i)
  })
})
