import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useToast } from './useToast'

describe('useToast', () => {
  beforeEach(() => {
    // Clear any toasts left from a previous test.
    const { toasts, dismiss } = useToast()
    toasts.value.slice().forEach(t => dismiss(t.id))
  })

  it('pushes a toast and auto-dismisses after the ttl', () => {
    vi.useFakeTimers()
    const { toasts, success } = useToast()
    success('done')
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0]).toMatchObject({ kind: 'success', message: 'done' })
    vi.advanceTimersByTime(4000)
    expect(toasts.value).toHaveLength(0)
    vi.useRealTimers()
  })

  it('dismiss removes a specific toast', () => {
    const { toasts, info, dismiss } = useToast()
    info('a'); info('b')
    const firstId = toasts.value[0].id
    dismiss(firstId)
    expect(toasts.value.find(t => t.id === firstId)).toBeUndefined()
  })
})
