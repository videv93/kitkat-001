import { useMutation } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { useAuth } from './useAuth'
import type { DisconnectResponse, RevokeResponse } from '../api/types'

export function useDisconnectWallet() {
  const { logout } = useAuth()

  return useMutation({
    mutationFn: () =>
      apiClient<DisconnectResponse>('/api/wallet/disconnect', { method: 'POST' }),
    onSuccess: () => {
      logout()
    },
  })
}

export function useRevokeAllSessions() {
  const { logout } = useAuth()

  return useMutation({
    mutationFn: () =>
      apiClient<RevokeResponse>('/api/wallet/revoke', { method: 'POST' }),
    onSuccess: () => {
      logout()
    },
  })
}
