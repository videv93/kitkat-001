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
    window.location.hash = ''
  })

  it('renders ConnectPage when not authenticated', () => {
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('kitkat-001')).toBeInTheDocument()
    expect(screen.getByText('TradingView to DEX signal execution')).toBeInTheDocument()
  })

  it('renders DashboardPage when authenticated', () => {
    localStorage.setItem('kitkat_token', 'valid-token')
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
  })

  it('renders SettingsPage when authenticated and hash is #settings', () => {
    localStorage.setItem('kitkat_token', 'valid-token')
    window.location.hash = '#settings'
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.getByText('Back to Dashboard')).toBeInTheDocument()
  })

  it('renders DashboardPage by default when authenticated with no hash', () => {
    localStorage.setItem('kitkat_token', 'valid-token')
    window.location.hash = ''
    render(<AuthGate />, { wrapper: TestProviders })
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
  })
})
