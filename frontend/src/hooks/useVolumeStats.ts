import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { VolumeStatsResponse } from '../api/types'

export function useVolumeStats() {
  return useQuery({
    queryKey: ['stats', 'volume'],
    queryFn: () => apiClient<VolumeStatsResponse>('/api/stats/volume'),
    refetchInterval: 30_000,
  })
}
