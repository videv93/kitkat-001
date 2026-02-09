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

describe('ConnectPage', () => {
  beforeEach(() => {
    currentRenderProps = { ...defaultRenderProps }
    mockShow.mockClear()
    mockHide.mockClear()
  })

  // Task 4.1: renders branding, description, and trust copy
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

  // Task 4.2: renders Connect Wallet button when not connected
  it('renders Connect Wallet button when not connected', () => {
    render(<ConnectPage />)
    expect(screen.getByRole('button', { name: /Connect Wallet/i })).toBeInTheDocument()
  })

  // Task 4.3: shows wallet address when connected
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

  // Task 4.4: ConnectKit button show() is called on click
  it('calls show() when Connect Wallet button is clicked', () => {
    render(<ConnectPage />)
    const button = screen.getByRole('button', { name: /Connect Wallet/i })
    fireEvent.click(button)
    expect(mockShow).toHaveBeenCalledOnce()
  })

  // Connecting state
  it('shows loading indicator when connecting', () => {
    currentRenderProps = {
      ...defaultRenderProps,
      isConnecting: true,
    }
    render(<ConnectPage />)
    expect(screen.getByRole('button', { name: /Connecting/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Connecting/i })).toBeDisabled()
  })
})
