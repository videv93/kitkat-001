import { useEffect, useRef, useState, useCallback } from 'react'
import { useAccount, useSignMessage } from 'wagmi'
import { UserRejectedRequestError } from 'viem'
import { apiClient } from '../api/client'
import { useAuth } from './useAuth'
import type { ChallengeResponse, VerifyResponse } from '../api/types'

type AuthStep = 'idle' | 'challenging' | 'signing' | 'verifying' | 'done'

export function useWalletAuth() {
  const { address, isConnected } = useAccount()
  const { signMessageAsync } = useSignMessage()
  const { isAuthenticated, login } = useAuth()

  const [step, setStep] = useState<AuthStep>('idle')
  const [error, setError] = useState<string | null>(null)
  const authInProgress = useRef(false)

  const performAuth = useCallback(
    async (walletAddress: string) => {
      try {
        // Step 1: Fetch challenge
        setStep('challenging')
        setError(null)
        const challenge = await apiClient<ChallengeResponse>(
          `/api/wallet/challenge?wallet_address=${walletAddress}`
        )

        // Step 2: Sign message
        setStep('signing')
        const signature = await signMessageAsync({
          message: challenge.message,
        })

        // Step 3: Verify signature
        setStep('verifying')
        const result = await apiClient<VerifyResponse>('/api/wallet/verify', {
          method: 'POST',
          body: JSON.stringify({
            wallet_address: walletAddress,
            signature,
            nonce: challenge.nonce,
          }),
        })

        // Step 4: Store token and wallet address
        login(result.token, result.wallet_address)
        setStep('done')
      } catch (err) {
        if (err instanceof UserRejectedRequestError) {
          setError('Signature rejected - you can try again anytime')
        } else if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('Authentication failed. Please try again.')
        }
        setStep('idle')
      } finally {
        authInProgress.current = false
      }
    },
    [signMessageAsync, login]
  )

  useEffect(() => {
    if (
      isConnected &&
      address &&
      !isAuthenticated &&
      !authInProgress.current &&
      step === 'idle' &&
      !error
    ) {
      authInProgress.current = true
      performAuth(address)
    }
  }, [isConnected, address, isAuthenticated, step, error, performAuth])

  const retry = useCallback(() => {
    setError(null)
    setStep('idle')
    // The useEffect will re-trigger since error is cleared and step is idle
  }, [])

  const isAuthenticating = step !== 'idle' && step !== 'done'

  return { isAuthenticating, step, error, retry } as const
}
