import { render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConnectKitProvider } from 'connectkit'
import { config } from '../lib/wagmi'
import AuthGate from './AuthGate'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function TestProviders({ children }: { children: ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <ConnectKitProvider>
          {children}
        </ConnectKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  )
}

describe('AuthGate', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders ConnectPage when not authenticated', () => {
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('kitkat-001')).toBeInTheDocument()
    expect(screen.getByText('TradingView to DEX signal execution')).toBeInTheDocument()
  })

  it('renders DashboardPage when authenticated', () => {
    localStorage.setItem('kitkat_token', 'valid-token')
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('Dashboard — coming in Story 7.1')).toBeInTheDocument()
  })
})
