import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { useVolumeStats } from './useVolumeStats'
import { apiClient } from '../api/client'
import type { VolumeStatsResponse } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

const mockApiClient = vi.mocked(apiClient)

const mockVolumeData: VolumeStatsResponse = {
  today: {
    extended: { volume_usd: '47250.00', executions: 14 },
    total: { volume_usd: '47250.00', executions: 14 },
  },
  this_week: {
    extended: { volume_usd: '284000.00', executions: 89 },
    total: { volume_usd: '284000.00', executions: 89 },
  },
  updated_at: '2026-02-17T00:00:00Z',
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

describe('useVolumeStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches volume stats on mount', async () => {
    mockApiClient.mockResolvedValueOnce(mockVolumeData)

    renderHook(() => useVolumeStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/stats/volume')
    })
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useVolumeStats(), { wrapper: createWrapper() })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns data on successful fetch', async () => {
    mockApiClient.mockResolvedValueOnce(mockVolumeData)

    const { result } = renderHook(() => useVolumeStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockVolumeData)
    expect(result.current.isError).toBe(false)
  })

  it('returns error on failed fetch', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('API error: 500'))

    const { result } = renderHook(() => useVolumeStats(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.data).toBeUndefined()
  })
})
