import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useWebhookConfig } from './useWebhookConfig'

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

const mockWebhookData = {
  webhook_url: 'https://kitkat.example.com/api/webhook?token=abc12345xyz',
  payload_format: {
    required_fields: ['symbol', 'side', 'size'],
    optional_fields: ['price', 'order_type'],
    example: {
      symbol: 'ETH-PERP',
      side: 'buy',
      size: '{{strategy.position_size}}',
    },
  },
  tradingview_setup: {
    alert_name: 'kitkat-001 Signal',
    webhook_url: 'https://kitkat.example.com/api/webhook?token=abc12345xyz',
    message_template: '{"symbol": "{{ticker}}", "side": "{{strategy.order.action}}", "size": "{{strategy.position_size}}"}',
  },
  token_display: 'abc12345...',
}

describe('useWebhookConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches webhook config from /api/config/webhook', async () => {
    mockApiClient.mockResolvedValue(mockWebhookData)

    const { result } = renderHook(() => useWebhookConfig(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockWebhookData)
    expect(mockApiClient).toHaveBeenCalledWith('/api/config/webhook')
  })

  it('returns loading state initially', () => {
    mockApiClient.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useWebhookConfig(), { wrapper: createWrapper() })
    expect(result.current.isLoading).toBe(true)
  })

  it('handles error state', async () => {
    mockApiClient.mockRejectedValue(new Error('Failed to load webhook config'))
    const { result } = renderHook(() => useWebhookConfig(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(Error)
  })
})
