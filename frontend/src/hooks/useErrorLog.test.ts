import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { useErrorLog } from './useErrorLog'
import { apiClient } from '../api/client'
import type { ErrorLogResponse } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

const mockApiClient = vi.mocked(apiClient)

const mockErrorData: ErrorLogResponse = {
  errors: [
    {
      id: 'err-42',
      timestamp: '2026-02-17T08:30:00Z',
      level: 'error',
      error_type: 'DEX_TIMEOUT',
      message: 'Extended DEX did not respond within 30s',
      context: { dex: 'extended', signal_id: 'abc123' },
    },
  ],
  count: 1,
}

const mockEmptyErrors: ErrorLogResponse = {
  errors: [],
  count: 0,
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useErrorLog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches errors with limit=3 on mount', async () => {
    mockApiClient.mockResolvedValueOnce(mockEmptyErrors)

    renderHook(() => useErrorLog(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/errors?limit=3')
    })
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useErrorLog(), { wrapper: createWrapper() })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns data on successful fetch', async () => {
    mockApiClient.mockResolvedValueOnce(mockErrorData)

    const { result } = renderHook(() => useErrorLog(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockErrorData)
    expect(result.current.isError).toBe(false)
  })

  it('returns error on failed fetch', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('API error: 500'))

    const { result } = renderHook(() => useErrorLog(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.data).toBeUndefined()
  })
})
