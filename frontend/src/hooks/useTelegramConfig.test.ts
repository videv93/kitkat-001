import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useTelegramConfig, useUpdateTelegramConfig } from './useTelegramConfig'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

import { apiClient } from '../api/client'

const mockApiClient = vi.mocked(apiClient)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useTelegramConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches telegram config from /api/config/telegram', async () => {
    mockApiClient.mockResolvedValue({
      configured: true,
      chat_id: '123456789',
      bot_status: 'connected',
      test_available: true,
      setup_instructions: null,
    })

    const { result } = renderHook(() => useTelegramConfig(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({
      configured: true,
      chat_id: '123456789',
      bot_status: 'connected',
      test_available: true,
      setup_instructions: null,
    })
    expect(mockApiClient).toHaveBeenCalledWith('/api/config/telegram')
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useTelegramConfig(), { wrapper: createWrapper() })
    expect(result.current.isLoading).toBe(true)
  })

  it('handles error state', async () => {
    mockApiClient.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useTelegramConfig(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(Error)
  })
})

describe('useUpdateTelegramConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends PUT request to /api/config/telegram', async () => {
    mockApiClient.mockResolvedValue({
      configured: true,
      chat_id: '123456789',
      bot_status: 'connected',
      test_available: true,
      setup_instructions: null,
    })

    const { result } = renderHook(() => useUpdateTelegramConfig(), { wrapper: createWrapper() })

    result.current.mutate({ chat_id: '123456789' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/config/telegram', {
      method: 'PUT',
      body: JSON.stringify({ chat_id: '123456789' }),
    })
  })

  it('handles mutation error', async () => {
    mockApiClient.mockRejectedValue(new Error('Failed to send test message - check chat ID'))
    const { result } = renderHook(() => useUpdateTelegramConfig(), { wrapper: createWrapper() })

    result.current.mutate({ chat_id: 'invalid' })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
