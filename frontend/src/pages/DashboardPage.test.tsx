import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardPage, { formatUSD } from './DashboardPage'
import { useDashboard } from '../hooks/useDashboard'
import { useVolumeStats } from '../hooks/useVolumeStats'
import { useExecutionStats } from '../hooks/useExecutionStats'
import { useOnboarding } from '../hooks/useOnboarding'
import { useErrorLog } from '../hooks/useErrorLog'
import type { DashboardResponse, VolumeStatsResponse, ExecutionStatsResponse, OnboardingResponse, ErrorLogResponse } from '../api/types'

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    isAuthenticated: true,
    token: 'test-token',
    login: vi.fn(),
    logout: vi.fn(),
  })),
}))

vi.mock('../hooks/useDashboard', () => ({
  useDashboard: vi.fn(),
}))

vi.mock('../hooks/useVolumeStats', () => ({
  useVolumeStats: vi.fn(),
}))

vi.mock('../hooks/useExecutionStats', () => ({
  useExecutionStats: vi.fn(),
}))

vi.mock('../hooks/useOnboarding', () => ({
  useOnboarding: vi.fn(),
}))

vi.mock('../hooks/useErrorLog', () => ({
  useErrorLog: vi.fn(),
}))

const mockUseDashboard = vi.mocked(useDashboard)
const mockUseVolumeStats = vi.mocked(useVolumeStats)
const mockUseExecutionStats = vi.mocked(useExecutionStats)
const mockUseOnboarding = vi.mocked(useOnboarding)
const mockUseErrorLog = vi.mocked(useErrorLog)

function makeDashboardData(overrides: Partial<DashboardResponse> = {}): DashboardResponse {
  return {
    status: 'all_ok',
    test_mode: false,
    test_mode_warning: null,
    dex_status: {
      extended: { status: 'healthy', latency_ms: 45 },
    },
    volume_today: { total_usd: '0.00', by_dex: {} },
    executions_today: { total: 0, success_rate: 'N/A' },
    recent_errors: 0,
    onboarding_complete: false,
    updated_at: '2026-02-17T00:00:00Z',
    ...overrides,
  }
}

const defaultVolumeData: VolumeStatsResponse = {
  today: {
    extended: { volume_usd: '47250.00', executions: 14 },
    total: { volume_usd: '47250.00', executions: 14 },
  },
  this_week: {
    extended: { volume_usd: '284000.00', executions: 89 },
    total: { volume_usd: '284000.00', executions: 89 },
  },
  updated_at: '2026-02-17T00:00:00Z',
}

const defaultExecData: ExecutionStatsResponse = {
  today: { total: 14, successful: 14, failed: 0, partial: 0, success_rate: '100.00%' },
  this_week: { total: 89, successful: 87, failed: 1, partial: 1, success_rate: '97.75%' },
  all_time: { total: 523, successful: 515, failed: 5, partial: 3, success_rate: '98.47%' },
}

const defaultOnboardingData: OnboardingResponse = {
  complete: false,
  progress: '3/5',
  steps: [
    { id: 'wallet_connected', name: 'Connect Wallet', complete: true },
    { id: 'dex_authorized', name: 'Authorize DEX Trading', complete: true },
    { id: 'webhook_configured', name: 'Configure TradingView Webhook', complete: true },
    { id: 'test_signal_sent', name: 'Send Test Signal', complete: false },
    { id: 'first_live_trade', name: 'First Live Trade', complete: false },
  ],
}

const defaultErrorData: ErrorLogResponse = {
  errors: [],
  count: 0,
}

function mockStatsLoaded(volumeData: VolumeStatsResponse | undefined = defaultVolumeData, execData: ExecutionStatsResponse | undefined = defaultExecData) {
  mockUseVolumeStats.mockReturnValue({ data: volumeData, isLoading: false, isError: false, error: null } as any)
  mockUseExecutionStats.mockReturnValue({ data: execData, isLoading: false, isError: false, error: null } as any)
}

function mockAllHooksLoaded(onboarding: OnboardingResponse | undefined = defaultOnboardingData, errors: ErrorLogResponse | undefined = defaultErrorData) {
  mockUseOnboarding.mockReturnValue({ data: onboarding, isLoading: false, isError: false, error: null } as any)
  mockUseErrorLog.mockReturnValue({ data: errors, isLoading: false, isError: false, error: null } as any)
}

function mockLoaded(data: DashboardResponse) {
  mockUseDashboard.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    error: null,
  } as any)
  mockStatsLoaded()
  mockAllHooksLoaded()
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: stats/onboarding/error hooks return no data (loading)
    mockUseVolumeStats.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
    mockUseExecutionStats.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
    mockUseOnboarding.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
    mockUseErrorLog.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
  })

  it('renders header with kitkat-001 branding', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('kitkat-001')).toBeInTheDocument()
  })

  it('shows test mode badge when test_mode is true', () => {
    mockLoaded(makeDashboardData({ test_mode: true }))
    render(<DashboardPage />)
    expect(screen.getByText('TEST MODE')).toBeInTheDocument()
  })

  it('does not show test mode badge when test_mode is false', () => {
    mockLoaded(makeDashboardData({ test_mode: false }))
    render(<DashboardPage />)
    expect(screen.queryByText('TEST MODE')).not.toBeInTheDocument()
  })

  it('shows Everything OK when status is all_ok and no errors', () => {
    mockLoaded(makeDashboardData({ status: 'all_ok', recent_errors: 0 }))
    render(<DashboardPage />)
    expect(screen.getByText('Everything OK')).toBeInTheDocument()
  })

  it('shows Degraded status when status is degraded', () => {
    mockLoaded(makeDashboardData({ status: 'degraded' }))
    render(<DashboardPage />)
    expect(screen.getByText('Degraded')).toBeInTheDocument()
  })

  it('shows Offline status when status is offline', () => {
    mockLoaded(makeDashboardData({ status: 'offline' }))
    render(<DashboardPage />)
    expect(screen.getByText('Offline')).toBeInTheDocument()
  })

  it('renders per-DEX health indicators with correct colors', () => {
    mockLoaded(makeDashboardData({
      dex_status: {
        extended: { status: 'healthy', latency_ms: 45 },
        mock: { status: 'degraded', latency_ms: 200 },
      },
    }))
    render(<DashboardPage />)
    expect(screen.getByText('extended')).toBeInTheDocument()
    expect(screen.getByText('mock')).toBeInTheDocument()
    expect(screen.getByText('45ms')).toBeInTheDocument()
    expect(screen.getByText('200ms')).toBeInTheDocument()

    // Verify dot colors via class names
    const extendedRow = screen.getByText('extended').closest('div')!.parentElement!
    const mockRow = screen.getByText('mock').closest('div')!.parentElement!
    expect(extendedRow.querySelector('.bg-green-500')).not.toBeNull()
    expect(mockRow.querySelector('.bg-yellow-500')).not.toBeNull()
  })

  it('shows loading state while fetching', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)
    render(<DashboardPage />)
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
  })

  it('shows Settings navigation link', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('shows error state when fetch fails', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network failure'),
    } as any)
    render(<DashboardPage />)
    expect(screen.getByText(/Failed to load dashboard/)).toBeInTheDocument()
    expect(screen.getByText(/Network failure/)).toBeInTheDocument()
  })

  // Story 7.2: Volume Stats tests
  it('renders volume stats with formatted USD values', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Volume')).toBeInTheDocument()
    expect(screen.getByText('$47k')).toBeInTheDocument()  // today
    expect(screen.getByText('$284k')).toBeInTheDocument()  // this week
  })

  it('renders per-DEX volume breakdown when multiple DEXs present', () => {
    const multiDexVolume: VolumeStatsResponse = {
      today: {
        extended: { volume_usd: '30000.00', executions: 10 },
        paradex: { volume_usd: '17250.00', executions: 4 },
        total: { volume_usd: '47250.00', executions: 14 },
      },
      this_week: {
        extended: { volume_usd: '200000.00', executions: 60 },
        paradex: { volume_usd: '84000.00', executions: 29 },
        total: { volume_usd: '284000.00', executions: 89 },
      },
      updated_at: '2026-02-17T00:00:00Z',
    }
    mockUseDashboard.mockReturnValue({
      data: makeDashboardData(),
      isLoading: false,
      isError: false,
      error: null,
    } as any)
    mockStatsLoaded(multiDexVolume)
    render(<DashboardPage />)
    // Per-DEX rows should appear for extended and paradex
    expect(screen.getByText('$30k')).toBeInTheDocument()
    expect(screen.getByText('$17k')).toBeInTheDocument()
  })

  it('renders execution count and success rate', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Executions')).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()  // today's total
    expect(screen.getByText('100.00%')).toBeInTheDocument()  // success rate
  })

  it('shows zeros without error when no executions exist', () => {
    const zeroVolume: VolumeStatsResponse = {
      today: { total: { volume_usd: '0.00', executions: 0 } },
      this_week: { total: { volume_usd: '0.00', executions: 0 } },
      updated_at: '2026-02-17T00:00:00Z',
    }
    const zeroExec: ExecutionStatsResponse = {
      today: { total: 0, successful: 0, failed: 0, partial: 0, success_rate: 'N/A' },
      this_week: { total: 0, successful: 0, failed: 0, partial: 0, success_rate: 'N/A' },
      all_time: { total: 0, successful: 0, failed: 0, partial: 0, success_rate: 'N/A' },
    }
    mockUseDashboard.mockReturnValue({
      data: makeDashboardData(),
      isLoading: false,
      isError: false,
      error: null,
    } as any)
    mockStatsLoaded(zeroVolume, zeroExec)
    render(<DashboardPage />)
    const zeroValues = screen.getAllByText('$0')
    expect(zeroValues).toHaveLength(2)  // today + this week
    expect(screen.getByText('N/A')).toBeInTheDocument()  // success rate
    // Should not show error state
    expect(screen.queryByText(/Failed to load/)).not.toBeInTheDocument()
  })

  it('falls back to dashboard data when stats hooks have no data', () => {
    mockUseDashboard.mockReturnValue({
      data: makeDashboardData({
        volume_today: { total_usd: '5000.00', by_dex: { extended: '5000.00' } },
        executions_today: { total: 3, success_rate: '100.00%' },
      }),
      isLoading: false,
      isError: false,
      error: null,
    } as any)
    // Stats hooks loading (no data)
    mockUseVolumeStats.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
    mockUseExecutionStats.mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as any)
    render(<DashboardPage />)
    expect(screen.getByText('$5k')).toBeInTheDocument()  // fallback from dashboard
    expect(screen.getByText('3')).toBeInTheDocument()  // fallback execution count
    const emDashes = screen.getAllByText('—')
    expect(emDashes.length).toBeGreaterThanOrEqual(1)  // M3: this week shows em dash when no volume stats (+ onboarding fallback)
  })

  it('renders stats sections even when dashboard endpoint fails but stats succeed', () => {
    mockUseDashboard.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Dashboard failed'),
    } as any)
    mockStatsLoaded()
    mockAllHooksLoaded()
    render(<DashboardPage />)
    // Dashboard error shown
    expect(screen.getByText(/Failed to load dashboard/)).toBeInTheDocument()
    // But stats sections still render from dedicated endpoints
    expect(screen.getByText('Volume')).toBeInTheDocument()
    expect(screen.getByText('$47k')).toBeInTheDocument()
    expect(screen.getByText('Executions')).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('100.00%')).toBeInTheDocument()
    // Onboarding and error sections also render independently
    expect(screen.getByText('Onboarding')).toBeInTheDocument()
    expect(screen.getByText('3/5')).toBeInTheDocument()
    expect(screen.getByText('Recent Errors')).toBeInTheDocument()
    expect(screen.getByText('No recent errors')).toBeInTheDocument()
  })
  // Story 7.3: Onboarding Progress tests
  it('renders onboarding progress with step count and progress bar', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Onboarding')).toBeInTheDocument()
    expect(screen.getByText('3/5')).toBeInTheDocument()
  })

  it('renders all 5 onboarding steps with correct names', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Connect Wallet')).toBeInTheDocument()
    expect(screen.getByText('Authorize DEX Trading')).toBeInTheDocument()
    expect(screen.getByText('Configure TradingView Webhook')).toBeInTheDocument()
    expect(screen.getByText('Send Test Signal')).toBeInTheDocument()
    expect(screen.getByText('First Live Trade')).toBeInTheDocument()
  })

  it('shows incomplete steps with distinct muted styling', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    // Complete steps should have white text, incomplete should have gray-500
    const sendTestSignal = screen.getByText('Send Test Signal')
    expect(sendTestSignal.className).toContain('text-gray-500')
    const connectWallet = screen.getByText('Connect Wallet')
    expect(connectWallet.className).toContain('text-white')
  })

  it('shows completion message when all onboarding steps complete', () => {
    const completeOnboarding: OnboardingResponse = {
      complete: true,
      progress: '5/5',
      steps: [
        { id: 'wallet_connected', name: 'Connect Wallet', complete: true },
        { id: 'dex_authorized', name: 'Authorize DEX Trading', complete: true },
        { id: 'webhook_configured', name: 'Configure TradingView Webhook', complete: true },
        { id: 'test_signal_sent', name: 'Send Test Signal', complete: true },
        { id: 'first_live_trade', name: 'First Live Trade', complete: true },
      ],
    }
    mockUseDashboard.mockReturnValue({ data: makeDashboardData({ onboarding_complete: true }), isLoading: false, isError: false, error: null } as any)
    mockStatsLoaded()
    mockAllHooksLoaded(completeOnboarding)
    render(<DashboardPage />)
    expect(screen.getByText('Onboarding Complete')).toBeInTheDocument()
    // Should NOT show individual steps
    expect(screen.queryByText('Send Test Signal')).not.toBeInTheDocument()
  })

  // Story 7.3: Recent Errors tests
  it('shows "No recent errors" with checkmark when no errors', () => {
    mockLoaded(makeDashboardData())
    render(<DashboardPage />)
    expect(screen.getByText('Recent Errors')).toBeInTheDocument()
    expect(screen.getByText('No recent errors')).toBeInTheDocument()
  })

  it('renders error entries with error_type, timestamp, and DEX', () => {
    const errorData: ErrorLogResponse = {
      errors: [
        {
          id: 'err-42',
          timestamp: '2026-02-17T08:30:00Z',
          level: 'error',
          error_type: 'DEX_TIMEOUT',
          message: 'Extended DEX did not respond within 30s',
          context: { dex: 'extended', signal_id: 'abc123' },
        },
        {
          id: 'err-41',
          timestamp: '2026-02-17T07:15:00Z',
          level: 'warning',
          error_type: 'DEX_ERROR',
          message: 'Temporary failure',
          context: { dex: 'paradex' },
        },
      ],
      count: 2,
    }
    mockUseDashboard.mockReturnValue({ data: makeDashboardData({ recent_errors: 2 }), isLoading: false, isError: false, error: null } as any)
    mockStatsLoaded()
    mockAllHooksLoaded(defaultOnboardingData, errorData)
    render(<DashboardPage />)
    expect(screen.getByText('DEX_TIMEOUT')).toBeInTheDocument()
    expect(screen.getByText('DEX_ERROR')).toBeInTheDocument()
    expect(screen.getByText('DEX: extended')).toBeInTheDocument()
    expect(screen.getByText('DEX: paradex')).toBeInTheDocument()
  })

  it('shows at most 3 errors (limit enforced by API query param)', () => {
    const errorData: ErrorLogResponse = {
      errors: [
        { id: 'err-3', timestamp: '2026-02-17T08:00:00Z', level: 'error', error_type: 'ERR_A', message: 'a', context: {} },
        { id: 'err-2', timestamp: '2026-02-17T07:00:00Z', level: 'error', error_type: 'ERR_B', message: 'b', context: {} },
        { id: 'err-1', timestamp: '2026-02-17T06:00:00Z', level: 'warning', error_type: 'ERR_C', message: 'c', context: {} },
      ],
      count: 3,
    }
    mockUseDashboard.mockReturnValue({ data: makeDashboardData({ recent_errors: 5 }), isLoading: false, isError: false, error: null } as any)
    mockStatsLoaded()
    mockAllHooksLoaded(defaultOnboardingData, errorData)
    render(<DashboardPage />)
    expect(screen.getByText('ERR_A')).toBeInTheDocument()
    expect(screen.getByText('ERR_B')).toBeInTheDocument()
    expect(screen.getByText('ERR_C')).toBeInTheDocument()
  })
})

// M1: formatUSD unit tests
describe('formatUSD', () => {
  it('formats values under 1000 as whole dollars', () => {
    expect(formatUSD('450.00')).toBe('$450')
    expect(formatUSD('0.00')).toBe('$0')
    expect(formatUSD('999.49')).toBe('$999')
  })

  it('formats values >= 1000 with k suffix', () => {
    expect(formatUSD('1000.00')).toBe('$1k')
    expect(formatUSD('31000.00')).toBe('$31k')
    expect(formatUSD('47250.00')).toBe('$47k')
    expect(formatUSD('284000.00')).toBe('$284k')
    expect(formatUSD('999500.00')).toBe('$1000k')
  })

  it('formats values >= 1M with M suffix', () => {
    expect(formatUSD('1000000.00')).toBe('$1.0M')
    expect(formatUSD('1200000.00')).toBe('$1.2M')
    expect(formatUSD('50000000.00')).toBe('$50.0M')
  })

  it('returns $0 for NaN or empty string', () => {
    expect(formatUSD('')).toBe('$0')
    expect(formatUSD('abc')).toBe('$0')
  })
})
