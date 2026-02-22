import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { useDashboard } from './useDashboard'
import { apiClient } from '../api/client'
import type { DashboardResponse } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

const mockApiClient = vi.mocked(apiClient)

const mockDashboardData: DashboardResponse = {
  status: 'all_ok',
  test_mode: false,
  test_mode_warning: null,
  dex_status: {
    extended: { status: 'healthy', latency_ms: 45 },
  },
  volume_today: { total_usd: '1000.00', by_dex: { extended: '1000.00' } },
  executions_today: { total: 5, success_rate: '100.00%' },
  recent_errors: 0,
  onboarding_complete: false,
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

describe('useDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches dashboard data on mount', async () => {
    mockApiClient.mockResolvedValueOnce(mockDashboardData)

    renderHook(() => useDashboard(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/dashboard')
    })
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {})) // never resolves

    const { result } = renderHook(() => useDashboard(), { wrapper: createWrapper() })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns data on successful fetch', async () => {
    mockApiClient.mockResolvedValueOnce(mockDashboardData)

    const { result } = renderHook(() => useDashboard(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockDashboardData)
    expect(result.current.isError).toBe(false)
  })

  it('returns error on failed fetch', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('API error: 500'))

    const { result } = renderHook(() => useDashboard(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.data).toBeUndefined()
  })
})
