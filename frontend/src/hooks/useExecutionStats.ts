import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { ExecutionStatsResponse } from '../api/types'

export function useExecutionStats() {
  return useQuery({
    queryKey: ['stats', 'executions'],
    queryFn: () => apiClient<ExecutionStatsResponse>('/api/stats/executions'),
    refetchInterval: 30_000,
  })
}
