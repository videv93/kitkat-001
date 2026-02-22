import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { useExecutionStats } from './useExecutionStats'
import { apiClient } from '../api/client'
import type { ExecutionStatsResponse } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

const mockApiClient = vi.mocked(apiClient)

const mockExecutionData: ExecutionStatsResponse = {
  today: {
    total: 14,
    successful: 14,
    failed: 0,
    partial: 0,
    success_rate: '100.00%',
  },
  this_week: {
    total: 89,
    successful: 87,
    failed: 1,
    partial: 1,
    success_rate: '97.75%',
  },
  all_time: {
    total: 523,
    successful: 515,
    failed: 5,
    partial: 3,
    success_rate: '98.47%',
  },
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useExecutionStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches execution stats on mount', async () => {
    mockApiClient.mockResolvedValueOnce(mockExecutionData)

    renderHook(() => useExecutionStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/stats/executions')
    })
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useExecutionStats(), { wrapper: createWrapper() })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns data on successful fetch', async () => {
    mockApiClient.mockResolvedValueOnce(mockExecutionData)

    const { result } = renderHook(() => useExecutionStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockExecutionData)
    expect(result.current.isError).toBe(false)
  })

  it('returns error on failed fetch', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('API error: 500'))

    const { result } = renderHook(() => useExecutionStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.data).toBeUndefined()
  })
})
