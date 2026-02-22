import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useDisconnectWallet, useRevokeAllSessions } from './useWalletActions'

vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('./useAuth', () => ({
  useAuth: vi.fn(() => ({
    logout: mockLogout,
  })),
}))

import { apiClient } from '../api/client'
const mockApiClient = vi.mocked(apiClient)
const mockLogout = vi.fn()

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useDisconnectWallet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /api/wallet/disconnect and logout on success', async () => {
    mockApiClient.mockResolvedValue({
      wallet_address: '0x1234...5678',
      message: 'Disconnected',
      timestamp: '2026-01-19T10:00:00Z',
    })
    const { result } = renderHook(() => useDisconnectWallet(), {
      wrapper: createWrapper(),
    })
    act(() => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/wallet/disconnect', { method: 'POST' })
    expect(mockLogout).toHaveBeenCalled()
  })

  it('handles disconnect errors', async () => {
    mockApiClient.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useDisconnectWallet(), {
      wrapper: createWrapper(),
    })
    act(() => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(mockLogout).not.toHaveBeenCalled()
  })
})

describe('useRevokeAllSessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /api/wallet/revoke and logout on success', async () => {
    mockApiClient.mockResolvedValue({
      wallet_address: '0x1234...5678',
      sessions_deleted: 2,
      delegation_revoked: true,
      message: 'Revoked',
      timestamp: '2026-01-19T10:00:00Z',
    })
    const { result } = renderHook(() => useRevokeAllSessions(), {
      wrapper: createWrapper(),
    })
    act(() => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith('/api/wallet/revoke', { method: 'POST' })
    expect(mockLogout).toHaveBeenCalled()
  })

  it('handles revoke errors', async () => {
    mockApiClient.mockRejectedValue(new Error('Server error'))
    const { result } = renderHook(() => useRevokeAllSessions(), {
      wrapper: createWrapper(),
    })
    act(() => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(mockLogout).not.toHaveBeenCalled()
  })
})
