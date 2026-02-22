import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { PositionSizeConfig, PositionSizeUpdate } from '../api/types'

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => apiClient<PositionSizeConfig>('/api/config'),
  })
}

export function useUpdateConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: PositionSizeUpdate) =>
      apiClient<PositionSizeConfig>('/api/config', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  })
}
