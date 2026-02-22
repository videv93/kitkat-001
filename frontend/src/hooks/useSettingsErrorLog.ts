import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { ErrorLogResponse } from '../api/types'

export function useSettingsErrorLog(hours?: number) {
  const params = new URLSearchParams({ limit: '50' })
  if (hours !== undefined) {
    params.set('hours', String(hours))
  }

  return useQuery({
    queryKey: ['errors', 'settings', { hours }],
    queryFn: () => apiClient<ErrorLogResponse>(`/api/errors?${params.toString()}`),
    refetchOnWindowFocus: false,
  })
}
