import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { useAuth } from './useAuth'

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns isAuthenticated false when no token in localStorage', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.token).toBeNull()
  })

  it('returns isAuthenticated true when token exists in localStorage', () => {
    localStorage.setItem('kitkat_token', 'test-token-123')
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

  it('logout removes token from state and localStorage', () => {
    localStorage.setItem('kitkat_token', 'existing-token')
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(true)

    act(() => {
      result.current.logout()
    })
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.token).toBeNull()
    expect(localStorage.getItem('kitkat_token')).toBeNull()
  })
})
