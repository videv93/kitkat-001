import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { useOnboarding } from './useOnboarding'
import { apiClient } from '../api/client'
import type { OnboardingResponse } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

const mockApiClient = vi.mocked(apiClient)

const mockOnboardingData: OnboardingResponse = {
  complete: false,
  progress: '3/5',
  steps: [
    { id: 'wallet_connected', name: 'Connect Wallet', complete: true },
    { id: 'dex_authorized', name: 'Authorize DEX Trading', complete: true },
    { id: 'webhook_configured', name: 'Configure TradingView Webhook', complete: true },
    { id: 'test_signal_sent', name: 'Send Test Signal', complete: false },
    { id: 'first_live_trade', name: 'First Live Trade', complete: false },
  ],
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useOnboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches onboarding data on mount', async () => {
    mockApiClient.mockResolvedValueOnce(mockOnboardingData)

    renderHook(() => useOnboarding(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/onboarding')
    })
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useOnboarding(), { wrapper: createWrapper() })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns data on successful fetch', async () => {
    mockApiClient.mockResolvedValueOnce(mockOnboardingData)

    const { result } = renderHook(() => useOnboarding(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockOnboardingData)
    expect(result.current.isError).toBe(false)
  })

  it('returns error on failed fetch', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('API error: 500'))

    const { result } = renderHook(() => useOnboarding(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.data).toBeUndefined()
  })
})
