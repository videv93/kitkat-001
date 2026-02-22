import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { DashboardResponse } from '../api/types'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiClient<DashboardResponse>('/api/dashboard'),
    refetchInterval: 30_000,
  })
}
