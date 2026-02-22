import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { WebhookConfigResponse } from '../api/types'

export function useWebhookConfig() {
  return useQuery({
    queryKey: ['config', 'webhook'],
    queryFn: () => apiClient<WebhookConfigResponse>('/api/config/webhook'),
  })
}
