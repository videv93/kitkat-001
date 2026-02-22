import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useSettingsErrorLog } from './useSettingsErrorLog'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

import { apiClient } from '../api/client'
const mockApiClient = vi.mocked(apiClient)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useSettingsErrorLog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches errors with limit=50 and no hours filter', async () => {
    mockApiClient.mockResolvedValue({ errors: [], count: 0 })
    const { result } = renderHook(() => useSettingsErrorLog(), {
      wrapper: createWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/errors?limit=50')
  })

  it('fetches errors with hours filter', async () => {
    mockApiClient.mockResolvedValue({ errors: [], count: 0 })
    const { result } = renderHook(() => useSettingsErrorLog(24), {
      wrapper: createWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/errors?limit=50&hours=24')
  })

  it('returns error log data on success', async () => {
    const mockData = {
      errors: [
        { id: 'err-1', timestamp: '2026-01-19T10:00:00Z', level: 'error', error_type: 'DEX_TIMEOUT', message: 'Timeout', context: {} },
      ],
      count: 1,
    }
    mockApiClient.mockResolvedValue(mockData)
    const { result } = renderHook(() => useSettingsErrorLog(), {
      wrapper: createWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockData)
  })

  it('handles API errors', async () => {
    mockApiClient.mockRejectedValue(new Error('Unauthorized'))
    const { result } = renderHook(() => useSettingsErrorLog(), {
      wrapper: createWrapper(),
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(Error)
  })

  it('uses distinct query key with hours', async () => {
    mockApiClient.mockResolvedValue({ errors: [], count: 0 })
    const { result } = renderHook(() => useSettingsErrorLog(168), {
      wrapper: createWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/errors?limit=50&hours=168')
  })
})
