import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { useAuth, _resetAuthStoreForTesting } from './useAuth'

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear()
    _resetAuthStoreForTesting()
  })

  it('returns isAuthenticated false when no token in localStorage', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.token).toBeNull()
  })

  it('returns isAuthenticated true when token exists in localStorage', () => {
    localStorage.setItem('kitkat_token', 'test-token-123')
    _resetAuthStoreForTesting()
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.token).toBe('test-token-123')
  })

  it('login sets token in state and localStorage', () => {
    const { result } = renderHook(() => useAuth())
    act(() => {
      result.current.login('new-token')
    })
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.token).toBe('new-token')
    expect(localStorage.getItem('kitkat_token')).toBe('new-token')
  })

  it('login stores wallet address when provided', () => {
    const { result } = renderHook(() => useAuth())
    act(() => {
      result.current.login('new-token', '0x1234567890abcdef1234567890abcdef12345678')
    })
    expect(result.current.walletAddress).toBe('0x1234567890abcdef1234567890abcdef12345678')
    expect(localStorage.getItem('kitkat_wallet_address')).toBe('0x1234567890abcdef1234567890abcdef12345678')
  })

  it('reads wallet address from localStorage on init', () => {
    localStorage.setItem('kitkat_token', 'test-token')
    localStorage.setItem('kitkat_wallet_address', '0xabcdef')
    _resetAuthStoreForTesting()
    const { result } = renderHook(() => useAuth())
    expect(result.current.walletAddress).toBe('0xabcdef')
  })

  it('logout removes token and wallet address from state and localStorage', () => {
    localStorage.setItem('kitkat_token', 'existing-token')
    localStorage.setItem('kitkat_wallet_address', '0xabcdef')
    _resetAuthStoreForTesting()
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(true)

    act(() => {
      result.current.logout()
    })
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.token).toBeNull()
    expect(result.current.walletAddress).toBeNull()
    expect(localStorage.getItem('kitkat_token')).toBeNull()
    expect(localStorage.getItem('kitkat_wallet_address')).toBeNull()
  })
})
