import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useConfig, useUpdateConfig } from './useConfig'

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

describe('useConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches config from /api/config', async () => {
    mockApiClient.mockResolvedValue({
      position_size: '0.5',
      max_position_size: '10.0',
      position_size_unit: 'ETH',
    })

    const { result } = renderHook(() => useConfig(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({
      position_size: '0.5',
      max_position_size: '10.0',
      position_size_unit: 'ETH',
    })
    expect(mockApiClient).toHaveBeenCalledWith('/api/config')
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useConfig(), { wrapper: createWrapper() })
    expect(result.current.isLoading).toBe(true)
  })

  it('handles error state', async () => {
    mockApiClient.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useConfig(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(Error)
  })
})

describe('useUpdateConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends PUT request to /api/config', async () => {
    mockApiClient.mockResolvedValue({
      position_size: '1.0',
      max_position_size: '5.0',
      position_size_unit: 'ETH',
    })

    const { result } = renderHook(() => useUpdateConfig(), { wrapper: createWrapper() })

    result.current.mutate({ position_size: '1.0', max_position_size: '5.0' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/config', {
      method: 'PUT',
      body: JSON.stringify({ position_size: '1.0', max_position_size: '5.0' }),
    })
  })

  it('handles mutation error', async () => {
    mockApiClient.mockRejectedValue(new Error('Validation failed'))
    const { result } = renderHook(() => useUpdateConfig(), { wrapper: createWrapper() })

    result.current.mutate({ position_size: '200' })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
