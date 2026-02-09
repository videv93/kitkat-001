import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiClient } from './client'

describe('apiClient', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('makes GET request to correct URL without Content-Type', async () => {
    const mockResponse = { data: 'test' }
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    })

    const result = await apiClient('/api/health')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/health',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    )
    expect(result).toEqual(mockResponse)
  })

  it('sets Content-Type on requests with body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiClient('/api/config', {
      method: 'PUT',
      body: JSON.stringify({ position_size: '0.1' }),
    })
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/config',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    )
  })

  it('includes Authorization header when token exists', async () => {
    localStorage.setItem('kitkat_token', 'bearer-token-123')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiClient('/api/dashboard')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/dashboard',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer bearer-token-123',
        }),
      })
    )
  })

  it('does not include Authorization header when no token', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiClient('/api/health')
    const callArgs = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[1].headers['Authorization']).toBeUndefined()
  })

  it('clears token and reloads on 401 response', async () => {
    localStorage.setItem('kitkat_token', 'expired-token')
    const reloadMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { reload: reloadMock },
      writable: true,
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    })

    await expect(apiClient('/api/dashboard')).rejects.toThrow('Session expired')
    expect(localStorage.getItem('kitkat_token')).toBeNull()
    expect(reloadMock).toHaveBeenCalled()
  })

  it('throws error with message on non-OK response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: 'Internal server error' }),
    })

    await expect(apiClient('/api/health')).rejects.toThrow('Internal server error')
  })
})
