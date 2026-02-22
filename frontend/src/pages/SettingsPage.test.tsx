import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SettingsPage from './SettingsPage'
import { useConfig, useUpdateConfig } from '../hooks/useConfig'
import { useWebhookConfig } from '../hooks/useWebhookConfig'
import { useTelegramConfig, useUpdateTelegramConfig } from '../hooks/useTelegramConfig'
import { useDashboard } from '../hooks/useDashboard'
import { useSettingsErrorLog } from '../hooks/useSettingsErrorLog'
import { useDisconnectWallet, useRevokeAllSessions } from '../hooks/useWalletActions'
import { useAuth } from '../hooks/useAuth'

vi.mock('../hooks/useConfig', () => ({
  useConfig: vi.fn(),
  useUpdateConfig: vi.fn(),
}))

vi.mock('../hooks/useWebhookConfig', () => ({
  useWebhookConfig: vi.fn(),
}))

vi.mock('../hooks/useTelegramConfig', () => ({
  useTelegramConfig: vi.fn(),
  useUpdateTelegramConfig: vi.fn(),
}))

vi.mock('../hooks/useDashboard', () => ({
  useDashboard: vi.fn(),
}))

vi.mock('../hooks/useSettingsErrorLog', () => ({
  useSettingsErrorLog: vi.fn(),
}))

vi.mock('../hooks/useWalletActions', () => ({
  useDisconnectWallet: vi.fn(),
  useRevokeAllSessions: vi.fn(),
}))

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

const mockUseConfig = vi.mocked(useConfig)
const mockUseUpdateConfig = vi.mocked(useUpdateConfig)
const mockUseWebhookConfig = vi.mocked(useWebhookConfig)
const mockUseTelegramConfig = vi.mocked(useTelegramConfig)
const mockUseUpdateTelegramConfig = vi.mocked(useUpdateTelegramConfig)
const mockUseDashboard = vi.mocked(useDashboard)
const mockUseSettingsErrorLog = vi.mocked(useSettingsErrorLog)
const mockUseDisconnectWallet = vi.mocked(useDisconnectWallet)
const mockUseRevokeAllSessions = vi.mocked(useRevokeAllSessions)
const mockUseAuth = vi.mocked(useAuth)

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderSettingsPage(props: { onNavigate?: (view: 'dashboard' | 'settings') => void } = {}) {
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage {...props} />
    </QueryClientProvider>
  )
}

const defaultConfigData = {
  position_size: '0.5',
  max_position_size: '10.0',
  position_size_unit: 'ETH',
}

const defaultTelegramData = {
  configured: true,
  chat_id: '123456789',
  bot_status: 'connected' as const,
  test_available: true,
  setup_instructions: null,
}

const defaultDashboardData = {
  status: 'all_ok' as const,
  test_mode: false,
  test_mode_warning: null,
  dex_status: {},
  volume_today: { total_usd: '0', by_dex: {} },
  executions_today: { total: 0, success_rate: '0%' },
  recent_errors: 0,
  onboarding_complete: true,
  updated_at: '2026-01-01T00:00:00Z',
}

const defaultWebhookData = {
  webhook_url: 'https://kitkat.example.com/api/webhook?token=abc12345xyz',
  payload_format: {
    required_fields: ['symbol', 'side', 'size'],
    optional_fields: ['price', 'order_type'],
    example: {
      symbol: 'ETH-PERP',
      side: 'buy',
      size: '{{strategy.position_size}}',
    },
  },
  tradingview_setup: {
    alert_name: 'kitkat-001 Signal',
    webhook_url: 'https://kitkat.example.com/api/webhook?token=abc12345xyz',
    message_template: '{"symbol": "{{ticker}}", "side": "{{strategy.order.action}}", "size": "{{strategy.position_size}}"}',
  },
  token_display: 'abc12345...',
}

let mutateFn: ReturnType<typeof vi.fn>
let telegramMutateFn: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  mutateFn = vi.fn()
  telegramMutateFn = vi.fn()
  mockUseUpdateConfig.mockReturnValue({
    mutate: mutateFn,
    isPending: false,
    isError: false,
    error: null,
  } as any)
  mockUseUpdateTelegramConfig.mockReturnValue({
    mutate: telegramMutateFn,
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  } as any)
  // Default: all sections loaded successfully
  mockUseWebhookConfig.mockReturnValue({
    data: defaultWebhookData,
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockUseConfig.mockReturnValue({
    data: defaultConfigData,
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockUseTelegramConfig.mockReturnValue({
    data: defaultTelegramData,
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockUseDashboard.mockReturnValue({
    data: defaultDashboardData,
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockUseSettingsErrorLog.mockReturnValue({
    data: { errors: [], count: 0 },
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockUseDisconnectWallet.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  } as any)
  mockUseRevokeAllSessions.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  } as any)
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    token: 'test-token',
    walletAddress: '0x1234567890abcdef1234567890abcdef12345678',
    login: vi.fn(),
    logout: vi.fn(),
  } as any)
})

describe('SettingsPage', () => {
  it('renders Settings header and back navigation', () => {
    renderSettingsPage()
    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.getByText('Back to Dashboard')).toBeInTheDocument()
  })

  it('calls onNavigate when back button is clicked', () => {
    const onNavigate = vi.fn()
    renderSettingsPage({ onNavigate })
    fireEvent.click(screen.getByText('Back to Dashboard'))
    expect(onNavigate).toHaveBeenCalledWith('dashboard')
  })

  it('displays position size values from API', () => {
    renderSettingsPage()
    const posInput = screen.getByLabelText('Position Size') as HTMLInputElement
    const maxInput = screen.getByLabelText('Max Position Size') as HTMLInputElement
    expect(posInput.value).toBe('0.5')
    expect(maxInput.value).toBe('10.0')
  })

  it('displays ETH unit label', () => {
    renderSettingsPage()
    expect(screen.getAllByText('ETH')).toHaveLength(2)
  })

  it('shows loading state', () => {
    mockUseConfig.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Loading settings...')).toBeInTheDocument()
  })

  it('shows error state when config fails to load', () => {
    mockUseConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load settings/)).toBeInTheDocument()
  })

  it('input fields are editable', () => {
    renderSettingsPage()
    const posInput = screen.getByLabelText('Position Size') as HTMLInputElement
    fireEvent.change(posInput, { target: { value: '1.5' } })
    expect(posInput.value).toBe('1.5')
  })

  it('Save button triggers mutation with current values', () => {
    renderSettingsPage()
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(mutateFn).toHaveBeenCalledWith(
      { position_size: '0.5', max_position_size: '10.0' },
      expect.any(Object)
    )
  })

  it('shows validation error for position size <= 0', () => {
    renderSettingsPage()
    const posInput = screen.getByLabelText('Position Size')
    fireEvent.change(posInput, { target: { value: '0' } })
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(screen.getByText('Position size must be greater than 0')).toBeInTheDocument()
    expect(mutateFn).not.toHaveBeenCalled()
  })

  it('shows validation error for max > 100', () => {
    renderSettingsPage()
    const maxInput = screen.getByLabelText('Max Position Size')
    fireEvent.change(maxInput, { target: { value: '101' } })
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(screen.getByText('Max position size cannot exceed 100')).toBeInTheDocument()
    expect(mutateFn).not.toHaveBeenCalled()
  })

  it('shows validation error when position size exceeds max', () => {
    renderSettingsPage()
    const posInput = screen.getByLabelText('Position Size')
    const maxInput = screen.getByLabelText('Max Position Size')
    fireEvent.change(posInput, { target: { value: '20' } })
    fireEvent.change(maxInput, { target: { value: '5' } })
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(screen.getByText('Position size cannot exceed max position size')).toBeInTheDocument()
    expect(mutateFn).not.toHaveBeenCalled()
  })

  it('displays API error message on mutation failure', () => {
    mockUseUpdateConfig.mockReturnValue({
      mutate: mutateFn,
      isPending: false,
      isError: true,
      error: new Error('position_size cannot exceed max_position_size'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('position_size cannot exceed max_position_size')).toBeInTheDocument()
  })

  it('disables Save button and shows Saving... during pending state', () => {
    mockUseUpdateConfig.mockReturnValue({
      mutate: mutateFn,
      isPending: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    const saveButtons = screen.getAllByText('Saving...')
    expect(saveButtons[0]).toBeDisabled()
  })

  it('clears validation error when input changes', () => {
    renderSettingsPage()
    const posInput = screen.getByLabelText('Position Size')
    fireEvent.change(posInput, { target: { value: '0' } })
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(screen.getByText('Position size must be greater than 0')).toBeInTheDocument()

    fireEvent.change(posInput, { target: { value: '1' } })
    expect(screen.queryByText('Position size must be greater than 0')).not.toBeInTheDocument()
  })

  it('shows success message after save', async () => {
    mutateFn.mockImplementation((_data: any, options: any) => {
      options?.onSuccess?.()
    })

    renderSettingsPage()
    fireEvent.click(screen.getAllByText('Save')[0])
    expect(screen.getByText('Settings saved successfully')).toBeInTheDocument()
  })
})

describe('SettingsPage - Webhook Setup', () => {
  it('renders Webhook Setup card with URL and masked token', () => {
    renderSettingsPage()
    expect(screen.getByText('Webhook Setup')).toBeInTheDocument()
    expect(screen.getByText(/abc12345\.\.\./)).toBeInTheDocument()
  })

  it('renders Copy button that copies full URL to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    renderSettingsPage()
    fireEvent.click(screen.getByText('Copy'))

    expect(writeText).toHaveBeenCalledWith('https://kitkat.example.com/api/webhook?token=abc12345xyz')
  })

  it('shows Copied! confirmation after copy', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    renderSettingsPage()
    fireEvent.click(screen.getByText('Copy'))

    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument()
    })
  })

  it('renders payload format code block with example JSON', () => {
    renderSettingsPage()
    expect(screen.getByText(/ETH-PERP/)).toBeInTheDocument()
  })

  it('displays required and optional fields', () => {
    renderSettingsPage()
    expect(screen.getByText('symbol, side, size')).toBeInTheDocument()
    expect(screen.getByText('price, order_type')).toBeInTheDocument()
  })

  it('displays TradingView setup instructions', () => {
    renderSettingsPage()
    expect(screen.getByText('kitkat-001 Signal')).toBeInTheDocument()
    expect(screen.getByText(/ticker/)).toBeInTheDocument()
  })

  it('shows loading state while fetching webhook config', () => {
    mockUseWebhookConfig.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Loading webhook config...')).toBeInTheDocument()
  })

  it('shows error state on API failure', () => {
    mockUseWebhookConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Token not configured'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load webhook config/)).toBeInTheDocument()
  })

  it('renders independently from Position Size section', () => {
    mockUseConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Config failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load settings/)).toBeInTheDocument()
    expect(screen.getByText('Webhook Setup')).toBeInTheDocument()
    expect(screen.getByText(/abc12345\.\.\./)).toBeInTheDocument()
  })
})

describe('SettingsPage - Telegram Alerts', () => {
  it('renders Telegram section with configured status', () => {
    renderSettingsPage()
    expect(screen.getByText('Telegram Alerts')).toBeInTheDocument()
    expect(screen.getByText('Configured')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('shows masked chat ID when configured', () => {
    renderSettingsPage()
    expect(screen.getByText('1234...')).toBeInTheDocument()
  })

  it('shows unconfigured status and setup instructions', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'connected',
        test_available: true,
        setup_instructions: 'To configure Telegram alerts:\n1. Start a chat with the bot',
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Not Configured')).toBeInTheDocument()
    expect(screen.getByText(/To configure Telegram alerts/)).toBeInTheDocument()
  })

  it('shows bot not configured warning', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'not_configured',
        test_available: false,
        setup_instructions: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Telegram bot is not configured on the server/)).toBeInTheDocument()
  })

  it('allows entering chat ID and saving', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'connected',
        test_available: true,
        setup_instructions: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    const chatInput = screen.getByLabelText('Chat ID') as HTMLInputElement
    fireEvent.change(chatInput, { target: { value: '999888777' } })

    // Click the Telegram Save button (second Save button on page)
    const saveButtons = screen.getAllByText('Save')
    fireEvent.click(saveButtons[saveButtons.length - 1])

    expect(telegramMutateFn).toHaveBeenCalledWith(
      { chat_id: '999888777' },
      expect.any(Object)
    )
  })

  it('shows error on failed telegram save', () => {
    mockUseUpdateTelegramConfig.mockReturnValue({
      mutate: telegramMutateFn,
      isPending: false,
      isError: true,
      error: new Error('Failed to send test message - check chat ID'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Failed to send test message - check chat ID')).toBeInTheDocument()
  })

  it('shows success message on successful telegram save', () => {
    telegramMutateFn.mockImplementation((_data: any, options: any) => {
      options?.onSuccess?.()
    })

    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'connected',
        test_available: true,
        setup_instructions: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    const chatInput = screen.getByLabelText('Chat ID')
    fireEvent.change(chatInput, { target: { value: '123' } })
    const saveButtons = screen.getAllByText('Save')
    fireEvent.click(saveButtons[saveButtons.length - 1])
    expect(screen.getByText('Telegram configuration saved successfully')).toBeInTheDocument()
  })

  it('shows loading state for telegram section', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Loading Telegram configuration...')).toBeInTheDocument()
  })

  it('shows error state for telegram section', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Auth failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load Telegram config/)).toBeInTheDocument()
  })

  it('shows bot error status', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'error',
        test_available: false,
        setup_instructions: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('clears mutation error when chat ID input changes', () => {
    const resetFn = vi.fn()
    mockUseUpdateTelegramConfig.mockReturnValue({
      mutate: telegramMutateFn,
      isPending: false,
      isError: true,
      error: new Error('Failed to send test message - check chat ID'),
      reset: resetFn,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Failed to send test message - check chat ID')).toBeInTheDocument()

    const chatInput = screen.getByLabelText('Chat ID')
    fireEvent.change(chatInput, { target: { value: 'new-id' } })
    expect(resetFn).toHaveBeenCalled()
  })

  it('disables save button when chat ID is empty', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: {
        configured: false,
        chat_id: null,
        bot_status: 'connected',
        test_available: true,
        setup_instructions: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    const saveButtons = screen.getAllByText('Save')
    const telegramSaveBtn = saveButtons[saveButtons.length - 1] as HTMLButtonElement
    expect(telegramSaveBtn).toBeDisabled()
  })
})

describe('SettingsPage - Test Mode', () => {
  it('renders Test Mode section with inactive status', () => {
    renderSettingsPage()
    expect(screen.getByText('Test Mode')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('renders Test Mode active status with badge', () => {
    mockUseDashboard.mockReturnValue({
      data: {
        ...defaultDashboardData,
        test_mode: true,
        test_mode_warning: 'Test mode ENABLED - no real trades',
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Test mode ENABLED - no real trades')).toBeInTheDocument()
  })

  it('shows explanation that test mode is server-controlled', () => {
    renderSettingsPage()
    expect(screen.getByText(/Test mode is controlled via the server environment/)).toBeInTheDocument()
  })

  it('shows loading state for test mode section', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Loading test mode status...')).toBeInTheDocument()
  })

  it('shows error state for test mode section', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Server error'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load test mode status/)).toBeInTheDocument()
  })
})

describe('SettingsPage - Section Independence', () => {
  it('renders telegram section even when config section fails', () => {
    mockUseConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Config failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load settings/)).toBeInTheDocument()
    expect(screen.getByText('Telegram Alerts')).toBeInTheDocument()
    expect(screen.getByText('Configured')).toBeInTheDocument()
  })

  it('renders test mode section even when telegram section fails', () => {
    mockUseTelegramConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Telegram failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load Telegram config/)).toBeInTheDocument()
    expect(screen.getByText('Test Mode')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('renders config section even when test mode fails', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Dashboard failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load test mode status/)).toBeInTheDocument()
    const posInput = screen.getByLabelText('Position Size') as HTMLInputElement
    expect(posInput.value).toBe('0.5')
  })

  it('renders error log and account sections even when other sections fail', () => {
    mockUseConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Config failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Error Log')).toBeInTheDocument()
    expect(screen.getByText('Account')).toBeInTheDocument()
  })

  it('renders all sections when error log fails', () => {
    mockUseSettingsErrorLog.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Error log failed'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load error log/)).toBeInTheDocument()
    expect(screen.getByText('Account')).toBeInTheDocument()
    expect(screen.getByText('Telegram Alerts')).toBeInTheDocument()
  })
})

describe('SettingsPage - Error Log', () => {
  it('renders Error Log section header', () => {
    renderSettingsPage()
    expect(screen.getByText('Error Log')).toBeInTheDocument()
  })

  it('shows "No errors recorded" when empty', () => {
    renderSettingsPage()
    expect(screen.getByText('No errors recorded')).toBeInTheDocument()
  })

  it('displays error entries with level badges and details', () => {
    mockUseSettingsErrorLog.mockReturnValue({
      data: {
        errors: [
          {
            id: 'err-1',
            timestamp: '2026-01-19T10:00:00Z',
            level: 'error',
            error_type: 'DEX_TIMEOUT',
            message: 'Extended DEX timeout after 10s',
            context: {},
          },
          {
            id: 'err-2',
            timestamp: '2026-01-19T09:00:00Z',
            level: 'warning',
            error_type: 'RATE_LIMIT',
            message: 'Rate limit approaching',
            context: {},
          },
        ],
        count: 2,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('error')).toBeInTheDocument()
    expect(screen.getByText('warning')).toBeInTheDocument()
    expect(screen.getByText('DEX_TIMEOUT')).toBeInTheDocument()
    expect(screen.getByText('RATE_LIMIT')).toBeInTheDocument()
    expect(screen.getByText('Extended DEX timeout after 10s')).toBeInTheDocument()
    expect(screen.getByText('Rate limit approaching')).toBeInTheDocument()
  })

  it('shows time range filter buttons', () => {
    renderSettingsPage()
    expect(screen.getByText('Last 24h')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('All')).toBeInTheDocument()
  })

  it('calls useSettingsErrorLog with hours when filter clicked', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Last 24h'))
    // After clicking, the hook is called with hours=24 on re-render
    expect(mockUseSettingsErrorLog).toHaveBeenCalledWith(24)
  })

  it('calls useSettingsErrorLog with 168 for 7 days filter', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Last 7 days'))
    expect(mockUseSettingsErrorLog).toHaveBeenCalledWith(168)
  })

  it('resets hours to undefined when All filter clicked', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Last 24h'))
    expect(mockUseSettingsErrorLog).toHaveBeenCalledWith(24)
    fireEvent.click(screen.getByText('All'))
    expect(mockUseSettingsErrorLog).toHaveBeenCalledWith(undefined)
  })

  it('shows loading state for error log', () => {
    mockUseSettingsErrorLog.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Loading error log...')).toBeInTheDocument()
  })

  it('shows error state for error log', () => {
    mockUseSettingsErrorLog.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Server error'),
    } as any)

    renderSettingsPage()
    expect(screen.getByText(/Failed to load error log/)).toBeInTheDocument()
  })
})

describe('SettingsPage - Account', () => {
  it('renders Account section with abbreviated wallet address', () => {
    renderSettingsPage()
    expect(screen.getByText('Account')).toBeInTheDocument()
    expect(screen.getByText('0x1234...5678')).toBeInTheDocument()
  })

  it('renders Disconnect Wallet button', () => {
    renderSettingsPage()
    expect(screen.getByText('Disconnect Wallet')).toBeInTheDocument()
  })

  it('renders Revoke All Sessions button', () => {
    renderSettingsPage()
    expect(screen.getByText('Revoke All Sessions')).toBeInTheDocument()
  })

  it('shows disconnect confirmation dialog on click', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Disconnect Wallet'))
    expect(screen.getByText('This will end your current session')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('hides disconnect confirmation on cancel', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Disconnect Wallet'))
    expect(screen.getByText('This will end your current session')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('This will end your current session')).not.toBeInTheDocument()
  })

  it('calls disconnect mutation on confirm', () => {
    const disconnectMutate = vi.fn()
    mockUseDisconnectWallet.mockReturnValue({
      mutate: disconnectMutate,
      isPending: false,
      isError: false,
      error: null,
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    fireEvent.click(screen.getByText('Disconnect Wallet'))
    fireEvent.click(screen.getByText('Confirm'))
    expect(disconnectMutate).toHaveBeenCalled()
  })

  it('shows revoke confirmation dialog on click', () => {
    renderSettingsPage()
    fireEvent.click(screen.getByText('Revoke All Sessions'))
    expect(screen.getByText('This will end ALL active sessions across all devices')).toBeInTheDocument()
  })

  it('calls revoke mutation on confirm', () => {
    const revokeMutate = vi.fn()
    mockUseRevokeAllSessions.mockReturnValue({
      mutate: revokeMutate,
      isPending: false,
      isError: false,
      error: null,
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    fireEvent.click(screen.getByText('Revoke All Sessions'))
    // Two "Confirm" buttons may exist, get the last one
    const confirmButtons = screen.getAllByText('Confirm')
    fireEvent.click(confirmButtons[confirmButtons.length - 1])
    expect(revokeMutate).toHaveBeenCalled()
  })

  it('shows Disconnecting... during pending state', () => {
    mockUseDisconnectWallet.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      error: null,
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Disconnecting...')).toBeInTheDocument()
  })

  it('shows Revoking... during pending state', () => {
    mockUseRevokeAllSessions.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      error: null,
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Revoking...')).toBeInTheDocument()
  })

  it('shows disconnect error message', () => {
    mockUseDisconnectWallet.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error('Network error'),
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('shows revoke error message', () => {
    mockUseRevokeAllSessions.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error('Server error'),
      reset: vi.fn(),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Server error')).toBeInTheDocument()
  })

  it('does not show wallet address when not available', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      token: 'test-token',
      walletAddress: null,
      login: vi.fn(),
      logout: vi.fn(),
    } as any)

    renderSettingsPage()
    expect(screen.getByText('Account')).toBeInTheDocument()
    expect(screen.queryByText('Connected Wallet:')).not.toBeInTheDocument()
  })
})
