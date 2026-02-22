import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { OnboardingResponse } from '../api/types'

export function useOnboarding() {
  return useQuery({
    queryKey: ['onboarding'],
    queryFn: () => apiClient<OnboardingResponse>('/api/onboarding'),
    refetchInterval: 30_000,
  })
}
