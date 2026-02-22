export interface ChallengeResponse {
  message: string
  nonce: string
  expires_at: string
  explanation: string
}

export interface VerifyRequest {
  wallet_address: string
  signature: string
  nonce: string
}

export interface VerifyResponse {
  token: string
  expires_at: string
  wallet_address: string
}

// Dashboard API types (GET /api/dashboard)
export interface DashboardDexStatus {
  status: 'healthy' | 'degraded' | 'offline'
  latency_ms: number | null
}

export interface DashboardVolumeToday {
  total_usd: string
  by_dex: Record<string, string>
}

export interface DashboardExecutionsToday {
  total: number
  success_rate: string
}

export interface DashboardResponse {
  status: 'all_ok' | 'degraded' | 'offline'
  test_mode: boolean
  test_mode_warning: string | null
  dex_status: Record<string, DashboardDexStatus>
  volume_today: DashboardVolumeToday
  executions_today: DashboardExecutionsToday
  recent_errors: number
  onboarding_complete: boolean
  updated_at: string
}

// Volume Stats API types (GET /api/stats/volume)
export interface VolumeDexEntry {
  volume_usd: string
  executions: number
}

export interface VolumeStatsResponse {
  today: Record<string, VolumeDexEntry>
  this_week: Record<string, VolumeDexEntry>
  updated_at: string
}

// Execution Stats API types (GET /api/stats/executions)
export interface ExecutionStatsPeriod {
  total: number
  successful: number
  failed: number
  partial: number
  success_rate: string
}

export interface ExecutionStatsResponse {
  today: ExecutionStatsPeriod
  this_week: ExecutionStatsPeriod
  all_time: ExecutionStatsPeriod
}

// Onboarding API types (GET /api/onboarding)
export interface OnboardingStep {
  id: string
  name: string
  complete: boolean
}

export interface OnboardingResponse {
  complete: boolean
  progress: string
  steps: OnboardingStep[]
}

// Position Size Config API types (GET/PUT /api/config)
export interface PositionSizeConfig {
  position_size: string
  max_position_size: string
  position_size_unit: string
}

export interface PositionSizeUpdate {
  position_size?: string
  max_position_size?: string
}

// Webhook Config API types (GET /api/config/webhook)
export interface PayloadFormat {
  required_fields: string[]
  optional_fields: string[]
  example: Record<string, string>
}

export interface TradingViewSetup {
  alert_name: string
  webhook_url: string
  message_template: string
}

export interface WebhookConfigResponse {
  webhook_url: string
  payload_format: PayloadFormat
  tradingview_setup: TradingViewSetup
  token_display: string
}

// Telegram Config API types (GET/PUT /api/config/telegram)
export interface TelegramConfigResponse {
  configured: boolean
  chat_id: string | null
  bot_status: 'connected' | 'not_configured' | 'error'
  test_available: boolean
  setup_instructions: string | null
}

export interface TelegramConfigUpdate {
  chat_id: string
}

// Error Log API types (GET /api/errors)
export interface ErrorLogEntry {
  id: string
  timestamp: string
  level: 'error' | 'warning'
  error_type: string
  message: string
  context: Record<string, unknown>
}

export interface ErrorLogResponse {
  errors: ErrorLogEntry[]
  count: number
}

// Wallet Disconnect/Revoke API types (POST /api/wallet/disconnect, /api/wallet/revoke)
export interface DisconnectResponse {
  wallet_address: string
  message: string
  timestamp: string
}

export interface RevokeResponse {
  wallet_address: string
  sessions_deleted: number
  delegation_revoked: boolean
  message: string
  timestamp: string
}
