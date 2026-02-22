import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ConnectPage from './ConnectPage'

// Default mock state: disconnected
const mockShow = vi.fn()
const mockHide = vi.fn()
const defaultRenderProps = {
  isConnected: false,
  isConnecting: false,
  show: mockShow,
  hide: mockHide,
  address: undefined,
  truncatedAddress: undefined,
  ensName: undefined,
  chain: undefined,
}

let currentRenderProps = { ...defaultRenderProps }

vi.mock('connectkit', () => ({
  ConnectKitButton: {
    Custom: ({ children }: { children: (props: typeof defaultRenderProps) => React.ReactNode }) =>
      children(currentRenderProps),
  },
}))

// Mock useWalletAuth
const mockRetry = vi.fn()
let mockWalletAuth = {
  isAuthenticating: false,
  step: 'idle' as string,
  error: null as string | null,
  retry: mockRetry,
}

vi.mock('../hooks/useWalletAuth', () => ({
  useWalletAuth: () => mockWalletAuth,
}))

describe('ConnectPage', () => {
  beforeEach(() => {
    currentRenderProps = { ...defaultRenderProps }
    mockWalletAuth = {
      isAuthenticating: false,
      step: 'idle',
      error: null,
      retry: mockRetry,
    }
    mockShow.mockClear()
    mockHide.mockClear()
    mockRetry.mockClear()
  })

  // Existing Story 6.2 tests
  it('renders branding and app name', () => {
    render(<ConnectPage />)
    expect(screen.getByText('kitkat-001')).toBeInTheDocument()
  })

  it('renders app description', () => {
    render(<ConnectPage />)
    expect(screen.getByText(/TradingView to DEX signal execution/i)).toBeInTheDocument()
  })

  it('renders trust-building copy', () => {
    render(<ConnectPage />)
    const trustCopy = screen.getByText(
      /Signs a message to verify ownership.*no fund access granted/i
    )
    expect(trustCopy).toBeInTheDocument()
  })

  it('renders Connect Wallet button when not connected', () => {
    render(<ConnectPage />)
    expect(screen.getByRole('button', { name: /Connect Wallet/i })).toBeInTheDocument()
  })

  it('shows truncated wallet address when connected', () => {
    currentRenderProps = {
      ...defaultRenderProps,
      isConnected: true,
      address: '0x1234567890abcdef1234567890abcdef12345678' as `0x${string}`,
      truncatedAddress: '0x1234...5678',
    }
    render(<ConnectPage />)
    expect(screen.getByText('0x1234...5678')).toBeInTheDocument()
  })

  it('calls show() when Connect Wallet button is clicked', () => {
    render(<ConnectPage />)
    const button = screen.getByRole('button', { name: /Connect Wallet/i })
    fireEvent.click(button)
    expect(mockShow).toHaveBeenCalledOnce()
  })

  it('shows loading indicator when connecting', () => {
    currentRenderProps = {
      ...defaultRenderProps,
      isConnecting: true,
    }
    render(<ConnectPage />)
    expect(screen.getByRole('button', { name: /Connecting/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Connecting/i })).toBeDisabled()
  })

  // Story 6.3: Auth flow state tests
  it('shows "Requesting challenge..." during challenge fetch', () => {
    mockWalletAuth = {
      isAuthenticating: true,
      step: 'challenging',
      error: null,
      retry: mockRetry,
    }
    render(<ConnectPage />)
    expect(screen.getByText('Requesting challenge...')).toBeInTheDocument()
  })

  it('shows "Please sign the message in MetaMask..." during signing', () => {
    mockWalletAuth = {
      isAuthenticating: true,
      step: 'signing',
      error: null,
      retry: mockRetry,
    }
    render(<ConnectPage />)
    expect(screen.getByText('Please sign the message in MetaMask...')).toBeInTheDocument()
  })

  it('shows error message when signature rejected', () => {
    mockWalletAuth = {
      isAuthenticating: false,
      step: 'idle',
      error: 'Signature rejected - you can try again anytime',
      retry: mockRetry,
    }
    render(<ConnectPage />)
    expect(screen.getByText('Signature rejected - you can try again anytime')).toBeInTheDocument()
  })

  it('shows "Try Again" button on error and calls retry', () => {
    mockWalletAuth = {
      isAuthenticating: false,
      step: 'idle',
      error: 'Some error occurred',
      retry: mockRetry,
    }
    render(<ConnectPage />)
    const tryAgainButton = screen.getByRole('button', { name: /Try Again/i })
    expect(tryAgainButton).toBeInTheDocument()
    fireEvent.click(tryAgainButton)
    expect(mockRetry).toHaveBeenCalledOnce()
  })
})
