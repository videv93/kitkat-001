import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { TelegramConfigResponse, TelegramConfigUpdate } from '../api/types'

export function useTelegramConfig() {
  return useQuery({
    queryKey: ['telegram-config'],
    queryFn: () => apiClient<TelegramConfigResponse>('/api/config/telegram'),
  })
}

export function useUpdateTelegramConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TelegramConfigUpdate) =>
      apiClient<TelegramConfigResponse>('/api/config/telegram', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['telegram-config'] }),
  })
}
