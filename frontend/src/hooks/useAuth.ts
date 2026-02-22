import { useSyncExternalStore, useCallback } from 'react'
import { TOKEN_KEY, WALLET_ADDRESS_KEY } from '../lib/constants'

type AuthState = {
  token: string | null
  walletAddress: string | null
}

let listeners: Array<() => void> = []
let cachedState: AuthState = readStorage()

function readStorage(): AuthState {
  return {
    token: localStorage.getItem(TOKEN_KEY),
    walletAddress: localStorage.getItem(WALLET_ADDRESS_KEY),
  }
}

function subscribe(listener: () => void) {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

function emitChange() {
  cachedState = readStorage()
  for (const listener of listeners) {
    listener()
  }
}

function getSnapshot(): AuthState {
  return cachedState
}

/** Reset cached state from localStorage. Exported for test cleanup only. */
export function _resetAuthStoreForTesting() {
  cachedState = readStorage()
}

export function useAuth() {
  const state = useSyncExternalStore(subscribe, getSnapshot)

  const login = useCallback((newToken: string, address?: string) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    if (address) {
      localStorage.setItem(WALLET_ADDRESS_KEY, address)
    }
    emitChange()
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(WALLET_ADDRESS_KEY)
    emitChange()
  }, [])

  return {
    isAuthenticated: !!state.token,
    token: state.token,
    walletAddress: state.walletAddress,
    login,
    logout,
  } as const
}
