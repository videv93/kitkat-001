import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { ErrorLogResponse } from '../api/types'

export function useErrorLog() {
  return useQuery({
    queryKey: ['errors'],
    queryFn: () => apiClient<ErrorLogResponse>('/api/errors?limit=3'),
    refetchInterval: 30_000,
  })
}
