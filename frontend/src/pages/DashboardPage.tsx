import { useAuth } from '../hooks/useAuth'
import { useDashboard } from '../hooks/useDashboard'
import { useVolumeStats } from '../hooks/useVolumeStats'
import { useExecutionStats } from '../hooks/useExecutionStats'
import { useOnboarding } from '../hooks/useOnboarding'
import { useErrorLog } from '../hooks/useErrorLog'

export function formatUSD(value: string): string {
  const num = parseFloat(value)
  if (isNaN(num)) return '$0'
  if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `$${Math.round(num / 1_000)}k`
  return `$${Math.round(num)}`
}

const STATUS_CONFIG = {
  all_ok: { label: 'Everything OK', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
  degraded: { label: 'Degraded', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  offline: { label: 'Offline', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
} as const

const DEX_STATUS_DOT = {
  healthy: 'bg-green-500',
  degraded: 'bg-yellow-500',
  offline: 'bg-red-500',
} as const

interface DashboardPageProps {
  onNavigate?: (view: 'dashboard' | 'settings') => void
}

export default function DashboardPage({ onNavigate }: DashboardPageProps) {
  const { logout } = useAuth()
  const { data, isLoading, isError, error } = useDashboard()
  const { data: volumeData } = useVolumeStats()
  const { data: execData } = useExecutionStats()
  const { data: onboardingData } = useOnboarding()
  const { data: errorData } = useErrorLog()

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="flex items-center justify-between border-b border-gray-800 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">kitkat-001</h1>
          {data?.test_mode && (
            <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400">
              TEST MODE
            </span>
          )}
        </div>
        <nav className="flex gap-4">
          <button
            onClick={() => onNavigate?.('settings')}
            className="text-gray-400 hover:text-white"
          >
            Settings
          </button>
          <button
            onClick={logout}
            className="text-gray-400 hover:text-white"
          >
            Disconnect
          </button>
        </nav>
      </header>

      <main className="mx-auto max-w-4xl p-4 sm:p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-gray-400">Loading dashboard...</div>
          </div>
        )}

        {isError && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
            <p className="text-red-400">
              Failed to load dashboard: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        )}

        {data && (
          <div className="space-y-6">
            {/* System Status Indicator */}
            <div
              className={`rounded-lg border p-6 text-center ${STATUS_CONFIG[data.status].bg} ${STATUS_CONFIG[data.status].border}`}
            >
              <div className={`text-2xl font-bold ${STATUS_CONFIG[data.status].color}`}>
                {data.status === 'all_ok' && (
                  <span className="mr-2">&#10003;</span>
                )}
                {data.status === 'degraded' && (
                  <span className="mr-2">&#9888;</span>
                )}
                {data.status === 'offline' && (
                  <span className="mr-2">&#10007;</span>
                )}
                {STATUS_CONFIG[data.status].label}
              </div>
              {data.recent_errors > 0 && data.status === 'all_ok' && (
                <p className="mt-1 text-sm text-yellow-400">
                  {data.recent_errors} recent error{data.recent_errors !== 1 ? 's' : ''}
                </p>
              )}
              {data.test_mode_warning && (
                <p className="mt-1 text-sm text-yellow-400">{data.test_mode_warning}</p>
              )}
            </div>

            {/* DEX Health Status */}
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-sm font-medium text-gray-400">DEX Health</h2>
              <div className="space-y-2">
                {Object.entries(data.dex_status).map(([dexId, dex]) => (
                  <div
                    key={dexId}
                    className="flex items-center justify-between rounded-md bg-gray-800 px-4 py-2"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full ${DEX_STATUS_DOT[dex.status]}`}
                      />
                      <span className="font-medium capitalize">{dexId}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-gray-400">
                      <span className="capitalize">{dex.status}</span>
                      {dex.latency_ms !== null && (
                        <span>{dex.latency_ms}ms</span>
                      )}
                    </div>
                  </div>
                ))}
                {Object.keys(data.dex_status).length === 0 && (
                  <p className="text-sm text-gray-500">No DEXs configured</p>
                )}
              </div>
            </div>

          </div>
        )}

        {/* Volume Stats — renders independently of dashboard data */}
        {(volumeData || data) && (
          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-3 text-sm font-medium text-gray-400">Volume</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-400">Today</p>
                <p className="text-2xl font-bold">
                  {volumeData ? formatUSD(volumeData.today.total?.volume_usd ?? '0') : formatUSD(data!.volume_today.total_usd)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">This Week</p>
                <p className="text-2xl font-bold">
                  {volumeData ? formatUSD(volumeData.this_week.total?.volume_usd ?? '0') : '—'}
                </p>
              </div>
            </div>
            {volumeData && Object.keys(volumeData.today).filter(k => k !== 'total').length > 1 && (
              <div className="mt-3 space-y-1">
                {Object.entries(volumeData.today)
                  .filter(([k]) => k !== 'total')
                  .map(([dexId, entry]) => (
                    <div key={dexId} className="flex items-center justify-between rounded-md bg-gray-800 px-4 py-2 text-sm">
                      <span className="capitalize">{dexId}</span>
                      <span className="text-gray-400">{formatUSD(entry.volume_usd)}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Execution Metrics — renders independently of dashboard data */}
        {(execData || data) && (
          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-3 text-sm font-medium text-gray-400">Executions</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-400">Today</p>
                <p className="text-2xl font-bold">
                  {execData ? execData.today.total : data!.executions_today.total}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Success Rate</p>
                <p className="text-2xl font-bold">
                  {execData ? execData.today.success_rate : data!.executions_today.success_rate}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Onboarding Progress — renders independently of dashboard data */}
        {(onboardingData || data) && (
          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-3 text-sm font-medium text-gray-400">Onboarding</h2>
            {onboardingData?.complete ? (
              <div className="flex items-center gap-2 text-green-400">
                <span>&#10003;</span>
                <span>Onboarding Complete</span>
              </div>
            ) : (
              <>
                <div className="mb-3 flex items-center gap-3">
                  <span className="text-lg font-bold">{onboardingData?.progress ?? (data?.onboarding_complete ? '5/5' : '—')}</span>
                  <div className="h-2 flex-1 rounded-full bg-gray-800">
                    <div
                      className="h-2 rounded-full bg-green-500"
                      style={{ width: onboardingData
                        ? `${(onboardingData.steps.filter(s => s.complete).length / onboardingData.steps.length) * 100}%`
                        : data?.onboarding_complete ? '100%' : '0%' }}
                    />
                  </div>
                </div>
                {onboardingData && (
                  <div className="space-y-1">
                    {onboardingData.steps.map((step) => (
                      <div
                        key={step.id}
                        className={`flex items-center gap-3 rounded-md px-4 py-2 ${step.complete ? 'bg-gray-800' : 'bg-gray-800/50'}`}
                      >
                        <span className={step.complete ? 'text-green-400' : 'text-gray-600'}>
                          {step.complete ? '\u2713' : '\u25CB'}
                        </span>
                        <span className={step.complete ? 'text-white' : 'text-gray-500'}>
                          {step.name}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Recent Errors — renders independently of dashboard data */}
        {(errorData || data) && (
          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-3 text-sm font-medium text-gray-400">Recent Errors</h2>
            {errorData && errorData.errors.length === 0 ? (
              <div className="flex items-center gap-2 text-green-400">
                <span>&#10003;</span>
                <span>No recent errors</span>
              </div>
            ) : errorData ? (
              <div className="space-y-2">
                {errorData.errors.map((err) => (
                  <div
                    key={err.id}
                    className={`rounded-md px-4 py-2 ${err.level === 'error' ? 'bg-red-500/10' : 'bg-yellow-500/10'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={err.level === 'error' ? 'text-red-400' : 'text-yellow-400'}>
                        {err.error_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(err.timestamp).toLocaleString()}
                      </span>
                    </div>
                    {err.context.dex && (
                      <span className="text-xs text-gray-400">DEX: {String(err.context.dex)}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                {data && data.recent_errors > 0
                  ? `${data.recent_errors} recent error${data.recent_errors !== 1 ? 's' : ''}`
                  : 'No recent errors'}
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
