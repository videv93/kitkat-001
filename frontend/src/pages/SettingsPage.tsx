import { useState, useEffect } from 'react'
import { useConfig, useUpdateConfig } from '../hooks/useConfig'
import { useWebhookConfig } from '../hooks/useWebhookConfig'
import { useTelegramConfig, useUpdateTelegramConfig } from '../hooks/useTelegramConfig'
import { useDashboard } from '../hooks/useDashboard'
import { useSettingsErrorLog } from '../hooks/useSettingsErrorLog'
import { useDisconnectWallet, useRevokeAllSessions } from '../hooks/useWalletActions'
import { useAuth } from '../hooks/useAuth'

interface SettingsPageProps {
  onNavigate?: (view: 'dashboard' | 'settings') => void
}

export default function SettingsPage({ onNavigate }: SettingsPageProps) {
  const { data, isLoading, isError, error } = useConfig()
  const mutation = useUpdateConfig()

  const [positionSize, setPositionSize] = useState('')
  const [maxPositionSize, setMaxPositionSize] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [showSuccess, setShowSuccess] = useState(false)

  useEffect(() => {
    if (data) {
      setPositionSize(data.position_size)
      setMaxPositionSize(data.max_position_size)
    }
  }, [data])

  useEffect(() => {
    if (showSuccess) {
      const timer = setTimeout(() => setShowSuccess(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [showSuccess])

  const handleSave = () => {
    setValidationError(null)
    setShowSuccess(false)

    const size = parseFloat(positionSize)
    const maxSize = parseFloat(maxPositionSize)

    if (isNaN(size) || size <= 0) {
      setValidationError('Position size must be greater than 0')
      return
    }
    if (isNaN(maxSize) || maxSize <= 0) {
      setValidationError('Max position size must be greater than 0')
      return
    }
    if (maxSize > 100) {
      setValidationError('Max position size cannot exceed 100')
      return
    }
    if (size > maxSize) {
      setValidationError('Position size cannot exceed max position size')
      return
    }

    mutation.mutate(
      { position_size: positionSize, max_position_size: maxPositionSize },
      {
        onSuccess: () => setShowSuccess(true),
      }
    )
  }

  // Telegram config - independent hook
  const telegramQuery = useTelegramConfig()
  const telegramMutation = useUpdateTelegramConfig()

  const [chatId, setChatId] = useState('')
  const [showTelegramSuccess, setShowTelegramSuccess] = useState(false)

  useEffect(() => {
    if (telegramQuery.data?.chat_id) {
      setChatId(telegramQuery.data.chat_id)
    }
  }, [telegramQuery.data])

  useEffect(() => {
    if (showTelegramSuccess) {
      const timer = setTimeout(() => setShowTelegramSuccess(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [showTelegramSuccess])

  const handleTelegramSave = () => {
    setShowTelegramSuccess(false)
    telegramMutation.reset()
    telegramMutation.mutate(
      { chat_id: chatId },
      {
        onSuccess: () => setShowTelegramSuccess(true),
      }
    )
  }

  // Test mode - reuse dashboard data (includes test_mode boolean)
  const dashboardQuery = useDashboard()

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="flex items-center justify-between border-b border-gray-800 px-4 py-4 sm:px-6">
        <h1 className="text-xl font-bold">kitkat-001</h1>
        <button
          onClick={() => onNavigate?.('dashboard')}
          className="text-gray-400 hover:text-white"
        >
          Back to Dashboard
        </button>
      </header>

      <main className="mx-auto max-w-4xl p-4 sm:p-6">
        <h2 className="mb-6 text-2xl font-semibold">Settings</h2>

        {/* Position Size Section */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-gray-400">Loading settings...</div>
          </div>
        )}

        {isError && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
            <p className="text-red-400">
              Failed to load settings: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        )}

        {data && (
          <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
            <h3 className="mb-3 text-sm font-medium text-gray-400">Position Size</h3>

            <div className="space-y-4">
              <div>
                <label htmlFor="position-size" className="mb-1 block text-sm text-gray-400">
                  Position Size
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="position-size"
                    type="number"
                    step="0.01"
                    min="0"
                    value={positionSize}
                    onChange={(e) => { setPositionSize(e.target.value); setValidationError(null) }}
                    className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-white"
                  />
                  <span className="text-sm text-gray-400">{data.position_size_unit}</span>
                </div>
              </div>

              <div>
                <label htmlFor="max-position-size" className="mb-1 block text-sm text-gray-400">
                  Max Position Size
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="max-position-size"
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={maxPositionSize}
                    onChange={(e) => { setMaxPositionSize(e.target.value); setValidationError(null) }}
                    className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-white"
                  />
                  <span className="text-sm text-gray-400">{data.position_size_unit}</span>
                </div>
              </div>

              {validationError && (
                <p className="text-sm text-red-400">{validationError}</p>
              )}

              {mutation.isError && (
                <p className="text-sm text-red-400">
                  {mutation.error instanceof Error ? mutation.error.message : 'Failed to save'}
                </p>
              )}

              {showSuccess && (
                <p className="text-sm text-green-400">Settings saved successfully</p>
              )}

              <button
                onClick={handleSave}
                disabled={mutation.isPending}
                className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {mutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        )}

        {/* Webhook Setup Section - Independent */}
        <WebhookSetupSection />

        {/* Telegram Alerts Section - Independent */}
        <div className="mt-6">
          {telegramQuery.isLoading && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Telegram Alerts</h3>
              <div className="text-gray-400">Loading Telegram configuration...</div>
            </div>
          )}

          {telegramQuery.isError && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Telegram Alerts</h3>
              <p className="text-red-400">
                Failed to load Telegram config: {telegramQuery.error instanceof Error ? telegramQuery.error.message : 'Unknown error'}
              </p>
            </div>
          )}

          {telegramQuery.data && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Telegram Alerts</h3>

              <div className="space-y-4">
                {/* Status display */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Status:</span>
                  {telegramQuery.data.configured ? (
                    <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs text-green-400">Configured</span>
                  ) : (
                    <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">Not Configured</span>
                  )}
                </div>

                {/* Bot status */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Bot Status:</span>
                  {telegramQuery.data.bot_status === 'connected' && (
                    <span className="text-sm text-green-400">Connected</span>
                  )}
                  {telegramQuery.data.bot_status === 'not_configured' && (
                    <span className="text-sm text-yellow-400">Not Configured</span>
                  )}
                  {telegramQuery.data.bot_status === 'error' && (
                    <span className="text-sm text-red-400">Error</span>
                  )}
                </div>

                {/* Bot not configured warning */}
                {telegramQuery.data.bot_status === 'not_configured' && (
                  <div className="rounded-md bg-yellow-500/10 p-3">
                    <p className="text-sm text-yellow-400">
                      Telegram bot is not configured on the server. Contact your administrator to set up the bot token.
                    </p>
                  </div>
                )}

                {/* Setup instructions when not configured */}
                {telegramQuery.data.setup_instructions && (
                  <div className="rounded-md bg-gray-800 p-3 font-mono text-sm text-gray-300 whitespace-pre-line">
                    {telegramQuery.data.setup_instructions}
                  </div>
                )}

                {/* Chat ID display when configured */}
                {telegramQuery.data.configured && telegramQuery.data.chat_id && (
                  <div>
                    <span className="text-sm text-gray-400">Chat ID: </span>
                    <span className="text-sm text-white">
                      {telegramQuery.data.chat_id.length > 4
                        ? telegramQuery.data.chat_id.slice(0, 4) + '...'
                        : telegramQuery.data.chat_id}
                    </span>
                  </div>
                )}

                {/* Chat ID input */}
                <div>
                  <label htmlFor="telegram-chat-id" className="mb-1 block text-sm text-gray-400">
                    Chat ID
                  </label>
                  <input
                    id="telegram-chat-id"
                    type="text"
                    value={chatId}
                    onChange={(e) => { setChatId(e.target.value); telegramMutation.reset() }}
                    placeholder="Enter your Telegram chat ID"
                    className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-white"
                  />
                </div>

                {/* Error message */}
                {telegramMutation.isError && (
                  <p className="text-sm text-red-400">
                    {telegramMutation.error instanceof Error ? telegramMutation.error.message : 'Failed to save'}
                  </p>
                )}

                {/* Success message */}
                {showTelegramSuccess && (
                  <p className="text-sm text-green-400">Telegram configuration saved successfully</p>
                )}

                <button
                  onClick={handleTelegramSave}
                  disabled={telegramMutation.isPending || !chatId.trim()}
                  className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {telegramMutation.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Test Mode Section - Independent */}
        <div className="mt-6">
          {dashboardQuery.isLoading && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Test Mode</h3>
              <div className="text-gray-400">Loading test mode status...</div>
            </div>
          )}

          {dashboardQuery.isError && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Test Mode</h3>
              <p className="text-red-400">
                Failed to load test mode status: {dashboardQuery.error instanceof Error ? dashboardQuery.error.message : 'Unknown error'}
              </p>
            </div>
          )}

          {dashboardQuery.data && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h3 className="mb-3 text-sm font-medium text-gray-400">Test Mode</h3>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Status:</span>
                  {dashboardQuery.data.test_mode ? (
                    <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">Active</span>
                  ) : (
                    <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs text-green-400">Inactive</span>
                  )}
                </div>

                {dashboardQuery.data.test_mode_warning && (
                  <div className="rounded-md bg-yellow-500/10 p-3">
                    <p className="text-sm text-yellow-400">{dashboardQuery.data.test_mode_warning}</p>
                  </div>
                )}

                <p className="text-sm text-gray-500">
                  Test mode is controlled via the server environment variable. Contact your administrator to change this setting.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Error Log Section - Independent */}
        <ErrorLogSection />

        {/* Account Section - Independent */}
        <AccountSection />
      </main>
    </div>
  )
}

function WebhookSetupSection() {
  const { data, isLoading, isError, error } = useWebhookConfig()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (copied) {
      const timer = setTimeout(() => setCopied(false), 2500)
      return () => clearTimeout(timer)
    }
  }, [copied])

  const handleCopy = async () => {
    if (data) {
      try {
        await navigator.clipboard.writeText(data.webhook_url)
        setCopied(true)
      } catch {
        // Clipboard access denied or not available
      }
    }
  }

  return (
    <div className="mt-6">
      {isLoading && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Webhook Setup</h3>
          <div className="text-gray-400">Loading webhook config...</div>
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Webhook Setup</h3>
          <p className="text-red-400">
            Failed to load webhook config: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}

      {data && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Webhook Setup</h3>

          <div className="space-y-4">
            {/* Webhook URL */}
            <div>
              <span className="mb-1 block text-sm text-gray-400">Webhook URL</span>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-md bg-gray-800 px-3 py-2 font-mono text-sm text-gray-300 break-all">
                  {data.webhook_url.replace(/token=[^&]*/, `token=${data.token_display}`)}
                </code>
                <button
                  onClick={handleCopy}
                  className="shrink-0 rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Payload Format */}
            <div>
              <span className="mb-1 block text-sm text-gray-400">Payload Format</span>
              <div className="mb-2 text-sm text-gray-400">
                <span>Required: </span>
                <span className="text-white">{data.payload_format.required_fields.join(', ')}</span>
              </div>
              <div className="mb-2 text-sm text-gray-400">
                <span>Optional: </span>
                <span className="text-white">{data.payload_format.optional_fields.join(', ')}</span>
              </div>
              <pre className="rounded-md bg-gray-800 p-3 font-mono text-sm text-gray-300 overflow-x-auto">{JSON.stringify(data.payload_format.example, null, 2)}</pre>
            </div>

            {/* TradingView Setup */}
            <div>
              <span className="mb-1 block text-sm text-gray-400">TradingView Setup</span>
              <div className="mb-2 text-sm text-gray-400">
                <span>Alert Name: </span>
                <span className="text-white">{data.tradingview_setup.alert_name}</span>
              </div>
              <span className="mb-1 block text-sm text-gray-400">Message Template</span>
              <pre className="rounded-md bg-gray-800 p-3 font-mono text-sm text-gray-300 overflow-x-auto">{data.tradingview_setup.message_template}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ErrorLogSection() {
  const [hours, setHours] = useState<number | undefined>(undefined)
  const { data, isLoading, isError, error } = useSettingsErrorLog(hours)

  const filterOptions: { label: string; value: number | undefined }[] = [
    { label: 'Last 24h', value: 24 },
    { label: 'Last 7 days', value: 168 },
    { label: 'All', value: undefined },
  ]

  return (
    <div className="mt-6">
      {isLoading && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Error Log</h3>
          <div className="text-gray-400">Loading error log...</div>
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Error Log</h3>
          <p className="text-red-400">
            Failed to load error log: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}

      {data && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h3 className="mb-3 text-sm font-medium text-gray-400">Error Log</h3>

          <div className="mb-4 flex gap-2">
            {filterOptions.map((opt) => (
              <button
                key={opt.label}
                onClick={() => setHours(opt.value)}
                className={
                  hours === opt.value
                    ? 'rounded-md bg-blue-600 px-3 py-1 text-sm text-white'
                    : 'rounded-md bg-gray-800 px-3 py-1 text-sm text-gray-400 hover:text-white'
                }
              >
                {opt.label}
              </button>
            ))}
          </div>

          {data.errors.length === 0 ? (
            <p className="text-sm text-gray-500">No errors recorded</p>
          ) : (
            <div className="space-y-2">
              {data.errors.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-md border border-gray-800 bg-gray-800/50 p-3"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={
                        entry.level === 'error'
                          ? 'rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-400'
                          : 'rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400'
                      }
                    >
                      {entry.level}
                    </span>
                    <span className="font-mono text-xs text-gray-400">{entry.error_type}</span>
                    <span className="ml-auto text-xs text-gray-500">
                      {new Date(entry.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300">{entry.message}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AccountSection() {
  const { walletAddress } = useAuth()
  const disconnectMutation = useDisconnectWallet()
  const revokeMutation = useRevokeAllSessions()

  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false)
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false)

  const abbreviatedAddress = walletAddress
    ? `${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`
    : null

  const handleDisconnect = () => {
    setShowDisconnectConfirm(false)
    disconnectMutation.mutate()
  }

  const handleRevoke = () => {
    setShowRevokeConfirm(false)
    revokeMutation.mutate()
  }

  return (
    <div className="mt-6">
      <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
        <h3 className="mb-3 text-sm font-medium text-gray-400">Account</h3>

        <div className="space-y-4">
          {abbreviatedAddress && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Connected Wallet:</span>
              <span className="font-mono text-sm text-white">{abbreviatedAddress}</span>
            </div>
          )}

          {/* Disconnect */}
          <div>
            <button
              onClick={() => { setShowRevokeConfirm(false); disconnectMutation.reset(); setShowDisconnectConfirm(true) }}
              disabled={disconnectMutation.isPending || revokeMutation.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-white hover:bg-red-700 disabled:opacity-50"
            >
              {disconnectMutation.isPending ? 'Disconnecting...' : 'Disconnect Wallet'}
            </button>

            {showDisconnectConfirm && (
              <div className="mt-2 rounded-md bg-red-500/10 border border-red-500/20 p-3">
                <p className="text-sm text-red-400 mb-2">This will end your current session</p>
                <div className="flex gap-2">
                  <button
                    onClick={handleDisconnect}
                    className="rounded-md bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => setShowDisconnectConfirm(false)}
                    className="rounded-md bg-gray-800 px-3 py-1 text-sm text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {disconnectMutation.isError && (
              <p className="mt-2 text-sm text-red-400">
                {disconnectMutation.error instanceof Error ? disconnectMutation.error.message : 'Failed to disconnect'}
              </p>
            )}
          </div>

          {/* Revoke All Sessions */}
          <div>
            <button
              onClick={() => { setShowDisconnectConfirm(false); revokeMutation.reset(); setShowRevokeConfirm(true) }}
              disabled={disconnectMutation.isPending || revokeMutation.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-white hover:bg-red-700 disabled:opacity-50"
            >
              {revokeMutation.isPending ? 'Revoking...' : 'Revoke All Sessions'}
            </button>

            {showRevokeConfirm && (
              <div className="mt-2 rounded-md bg-red-500/10 border border-red-500/20 p-3">
                <p className="text-sm text-red-400 mb-2">This will end ALL active sessions across all devices</p>
                <div className="flex gap-2">
                  <button
                    onClick={handleRevoke}
                    className="rounded-md bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => setShowRevokeConfirm(false)}
                    className="rounded-md bg-gray-800 px-3 py-1 text-sm text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {revokeMutation.isError && (
              <p className="mt-2 text-sm text-red-400">
                {revokeMutation.error instanceof Error ? revokeMutation.error.message : 'Failed to revoke sessions'}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
