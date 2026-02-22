import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useWalletAuth } from './useWalletAuth'

// Mock dependencies
const mockLogin = vi.fn()
const mockSignMessageAsync = vi.fn()

let mockAccountState = {
  address: undefined as string | undefined,
  isConnected: false,
}

vi.mock('wagmi', () => ({
  useAccount: () => mockAccountState,
  useSignMessage: () => ({ signMessageAsync: mockSignMessageAsync }),
}))

vi.mock('./useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    token: null,
    login: mockLogin,
    logout: vi.fn(),
  }),
}))

const mockApiClient = vi.fn()
vi.mock('../api/client', () => ({
  apiClient: (...args: unknown[]) => mockApiClient(...args),
}))

describe('useWalletAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAccountState = { address: undefined, isConnected: false }
  })

  it('stays idle when wallet is not connected', () => {
    const { result } = renderHook(() => useWalletAuth())
    expect(result.current.isAuthenticating).toBe(false)
    expect(result.current.step).toBe('idle')
    expect(result.current.error).toBeNull()
  })

  it('fetches challenge when wallet connects', async () => {
    const challengeResponse = {
      message: 'Sign this message',
      nonce: 'abc123',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'Delegation authority',
    }
    mockApiClient.mockResolvedValueOnce(challengeResponse)
    mockSignMessageAsync.mockResolvedValueOnce('0xsignature')
    mockApiClient.mockResolvedValueOnce({
      token: 'bearer-token',
      expires_at: '2026-02-17T00:00:00Z',
      wallet_address: '0x1234567890abcdef1234567890abcdef12345678',
    })

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        '/api/wallet/challenge?wallet_address=0x1234567890abcdef1234567890abcdef12345678'
      )
    })
  })

  it('calls signMessageAsync with challenge message', async () => {
    const challengeResponse = {
      message: 'Sign this to authorize kitkat-001',
      nonce: 'nonce123',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'Delegation',
    }
    mockApiClient.mockResolvedValueOnce(challengeResponse)
    mockSignMessageAsync.mockResolvedValueOnce('0xsig')
    mockApiClient.mockResolvedValueOnce({
      token: 'token123',
      expires_at: '2026-02-17T00:00:00Z',
      wallet_address: '0x1234567890abcdef1234567890abcdef12345678',
    })

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(mockSignMessageAsync).toHaveBeenCalledWith({
        message: 'Sign this to authorize kitkat-001',
      })
    })
  })

  it('sends verify request with correct payload on successful signature', async () => {
    mockApiClient.mockResolvedValueOnce({
      message: 'Sign this',
      nonce: 'nonce456',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'Delegation',
    })
    mockSignMessageAsync.mockResolvedValueOnce('0xmysignature')
    mockApiClient.mockResolvedValueOnce({
      token: 'final-token',
      expires_at: '2026-02-17T00:00:00Z',
      wallet_address: '0x1234567890abcdef1234567890abcdef12345678',
    })

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/wallet/verify', {
        method: 'POST',
        body: JSON.stringify({
          wallet_address: '0x1234567890abcdef1234567890abcdef12345678',
          signature: '0xmysignature',
          nonce: 'nonce456',
        }),
      })
    })
  })

  it('calls login() with token on successful verify', async () => {
    mockApiClient.mockResolvedValueOnce({
      message: 'msg',
      nonce: 'n',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'e',
    })
    mockSignMessageAsync.mockResolvedValueOnce('0xsig')
    mockApiClient.mockResolvedValueOnce({
      token: 'my-bearer-token',
      expires_at: '2026-02-17T00:00:00Z',
      wallet_address: '0xaddr',
    })

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('my-bearer-token', '0xaddr')
    })
  })

  it('sets error state when user rejects MetaMask signature', async () => {
    mockApiClient.mockResolvedValueOnce({
      message: 'msg',
      nonce: 'n',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'e',
    })

    // Import UserRejectedRequestError from viem
    const { UserRejectedRequestError } = await import('viem')
    mockSignMessageAsync.mockRejectedValueOnce(
      new UserRejectedRequestError(new Error('User rejected'))
    )

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    const { result } = renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(result.current.error).toBe(
        'Signature rejected - you can try again anytime'
      )
    })
    expect(result.current.isAuthenticating).toBe(false)
  })

  it('sets error state when API returns error', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('Network error'))

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    const { result } = renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(result.current.error).toBe('Network error')
    })
    expect(result.current.isAuthenticating).toBe(false)
  })

  it('retry resets error and re-triggers flow', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('First attempt failed'))

    mockAccountState = {
      address: '0x1234567890abcdef1234567890abcdef12345678',
      isConnected: true,
    }

    const { result } = renderHook(() => useWalletAuth())

    await waitFor(() => {
      expect(result.current.error).toBe('First attempt failed')
    })

    // Setup success for retry
    mockApiClient.mockResolvedValueOnce({
      message: 'msg',
      nonce: 'n',
      expires_at: '2026-02-17T00:00:00Z',
      explanation: 'e',
    })
    mockSignMessageAsync.mockResolvedValueOnce('0xsig')
    mockApiClient.mockResolvedValueOnce({
      token: 'retry-token',
      expires_at: '2026-02-17T00:00:00Z',
      wallet_address: '0xaddr',
    })

    act(() => {
      result.current.retry()
    })

    await waitFor(() => {
      expect(result.current.error).toBeNull()
    })

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('retry-token', '0xaddr')
    })
  })
})
