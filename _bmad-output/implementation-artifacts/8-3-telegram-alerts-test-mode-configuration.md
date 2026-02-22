# Story 8.3: Telegram Alerts & Test Mode Configuration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to configure my Telegram alert destination and view test mode status from the Settings page**,
so that **I can receive alerts in my preferred Telegram chat and understand whether the system is running in test mode**.

## Acceptance Criteria

1. **Telegram Config Display:** Given an authenticated user on the Settings page, when the Telegram configuration section renders, then it shows the current configuration status (configured/not configured), chat ID if set, bot status, and setup instructions if not configured.

2. **Telegram Chat ID Update:** Given an authenticated user, when they enter a chat ID and click "Save", then `PUT /api/config/telegram` is called with `{ "chat_id": "<value>" }`, a test message is sent server-side, and on success the config is saved and a success message is shown.

3. **Telegram Test Message Failure:** Given an invalid chat ID, when the user saves, then the API returns 400 with `"Failed to send test message - check chat ID"`, the error is displayed, and the configuration is NOT saved.

4. **Telegram Bot Not Configured:** Given the server has no bot token configured, when the user views or attempts to update Telegram config, then a clear message indicates the bot is not available (bot_status: "not_configured").

5. **Telegram Unconfigured State:** Given Telegram is not configured for the user, when the Settings page loads, then setup instructions are displayed to guide the user.

6. **Test Mode Status Display:** Given the dashboard data includes `test_mode` boolean, when the Settings page renders, then a "Test Mode" section shows whether test mode is active or inactive, with a visual indicator (badge/label). This is a read-only display — test mode is controlled via server environment variable.

7. **Section Independence:** Given any section fails to load, when the Settings page renders, then other sections (Position Size, Webhook, Telegram, Test Mode) continue to render independently.

## Tasks / Subtasks

- [x] Task 1: Create TypeScript types for Telegram config (AC: #1, #2)
  - [x] 1.1 Add `TelegramConfigResponse` interface to `api/types.ts`
  - [x] 1.2 Add `TelegramConfigUpdate` interface to `api/types.ts`

- [x] Task 2: Create `useTelegramConfig` hook (AC: #1, #2, #3, #4, #5)
  - [x] 2.1 Create `hooks/useTelegramConfig.ts` with `useTelegramConfig()` query hook (`GET /api/config/telegram`)
  - [x] 2.2 Add `useUpdateTelegramConfig()` mutation hook (`PUT /api/config/telegram`) with query invalidation
  - [x] 2.3 Create `hooks/useTelegramConfig.test.ts` — loading, success, error, mutation states

- [x] Task 3: Add Telegram Configuration section to SettingsPage (AC: #1, #2, #3, #4, #5)
  - [x] 3.1 Add Telegram config card below Webhook Setup section in `SettingsPage.tsx`
  - [x] 3.2 Show configured status with chat ID (masked partially) and bot status indicator
  - [x] 3.3 Show setup instructions when not configured (`setup_instructions` from API)
  - [x] 3.4 Add chat ID input field with Save button
  - [x] 3.5 Show success message (auto-dismiss ~3s) on successful save
  - [x] 3.6 Show error message on failed save (invalid chat ID, bot not configured)
  - [x] 3.7 Handle `bot_status: "not_configured"` — show warning that server bot is not set up

- [x] Task 4: Add Test Mode status section to SettingsPage (AC: #6)
  - [x] 4.1 Use existing `useDashboard` hook data (`test_mode` boolean) — no new API call needed
  - [x] 4.2 Add "Test Mode" card showing active/inactive status with colored badge
  - [x] 4.3 Show `test_mode_warning` message if present
  - [x] 4.4 Display explanation that test mode is controlled via server environment

- [x] Task 5: Ensure section independence (AC: #7)
  - [x] 5.1 Each section (Position Size, Webhook, Telegram, Test Mode) has independent loading/error states
  - [x] 5.2 Failure in one section does not block rendering of others

- [x] Task 6: Write tests (AC: all)
  - [x] 6.1 Add SettingsPage tests for Telegram section (configured, unconfigured, save success, save error, bot not configured)
  - [x] 6.2 Add SettingsPage tests for Test Mode section (active, inactive, warning display)
  - [x] 6.3 Add section independence tests

## Dev Notes

### API Contracts

**GET /api/config/telegram** → `TelegramConfigResponse`:
```json
{
  "configured": true,
  "chat_id": "123456789",
  "bot_status": "connected",
  "test_available": true,
  "setup_instructions": null
}
```
When unconfigured:
```json
{
  "configured": false,
  "chat_id": null,
  "bot_status": "connected",
  "test_available": true,
  "setup_instructions": "To configure Telegram alerts:\n1. Start a chat with the kitkat-001 bot on Telegram\n2. Send /start to the bot\n3. Copy your chat ID from the bot's response\n4. Use PUT /api/config/telegram with your chat_id"
}
```

**PUT /api/config/telegram** with `{ "chat_id": "123456789" }`:
- 200: Returns updated `TelegramConfigResponse` with `configured: true`
- 400: `{"detail": "Failed to send test message - check chat ID"}` — config NOT saved
- 503: `{"detail": "Telegram bot not configured on server"}` — no bot token on server

**Test Mode:** Already available from `GET /api/dashboard` response:
- `test_mode: boolean`
- `test_mode_warning: string | null`
- No separate endpoint needed — reuse `useDashboard` hook

### Architecture & Patterns to Follow

**Hook pattern (from 8.1/8.2):**
```typescript
// Query hook
export function useTelegramConfig() {
  return useQuery({
    queryKey: ['telegram-config'],
    queryFn: () => apiClient<TelegramConfigResponse>('/api/config/telegram'),
  })
}

// Mutation hook
export function useUpdateTelegramConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TelegramConfigUpdate) =>
      apiClient<TelegramConfigResponse>('/api/config/telegram', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['telegram-config'] }),
  })
}
```

**Styling constants (established in 8.1/8.2):**
- Card: `rounded-lg border border-gray-800 bg-gray-900 p-4`
- Section header: `text-sm font-medium text-gray-400 mb-3`
- Input: `w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-white`
- Button: `rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50`
- Success: `text-sm text-green-400`
- Error: `text-sm text-red-400`
- Code block: `bg-gray-800 rounded-md p-3 font-mono text-sm text-gray-300`
- Card spacing: `mt-6` between cards
- Badge active: `bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded text-xs`
- Badge inactive: `bg-green-500/20 text-green-400 px-2 py-0.5 rounded text-xs`

**Test mock pattern (from 8.1/8.2):**
```typescript
vi.mock('../hooks/useTelegramConfig', () => ({
  useTelegramConfig: vi.fn(),
  useUpdateTelegramConfig: vi.fn(),
}))
```

### SettingsPage Section Ordering

Current: Position Size → (Webhook Setup from 8.2)
After 8.3: Position Size → Webhook Setup → Telegram Alerts → Test Mode

Each section renders independently with its own hook and loading/error state. The SettingsPage currently loads all data through `useConfig` for position size. For Telegram, add `useTelegramConfig`. For test mode, reuse `useDashboard`.

### Section Independence Pattern

Each section should follow this structure:
```tsx
{/* Telegram Section */}
<TelegramSection />  // or inline with own hook call

// Where each section independently handles:
const { data, isLoading, isError, error } = useTelegramConfig()
// Render loading/error/data states independently
```

Since SettingsPage currently doesn't use separate components for sections (everything is inline), continue the inline pattern but ensure each section's hook failure doesn't prevent other sections from rendering.

### Project Structure Notes

- Alignment with existing structure: hooks in `frontend/src/hooks/`, types in `frontend/src/api/types.ts`
- Page modifications only in `frontend/src/pages/SettingsPage.tsx`
- No new pages, no routing changes needed
- No new npm packages needed

### References

- [Source: src/kitkat/api/config.py#L333-492] — Backend GET/PUT /api/config/telegram endpoints
- [Source: src/kitkat/models.py#L945-990] — TelegramConfigResponse and TelegramConfigUpdate Pydantic models
- [Source: src/kitkat/config.py#L41] — test_mode setting (env var, read-only)
- [Source: src/kitkat/api/health.py#L44] — test_mode exposed in health endpoint
- [Source: frontend/src/pages/SettingsPage.tsx] — Current settings page structure
- [Source: frontend/src/hooks/useConfig.ts] — Existing hook pattern to follow
- [Source: frontend/src/api/types.ts] — Existing type definitions
- [Source: frontend/src/hooks/useDashboard.ts] — Already has test_mode data
- [Source: _bmad-output/implementation-artifacts/8-1-settings-layout-position-size-configuration.md] — Patterns established
- [Source: _bmad-output/implementation-artifacts/8-2-webhook-setup-display.md] — Patterns established

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- All 6 tasks completed with all subtasks
- Added TelegramConfigResponse and TelegramConfigUpdate TypeScript interfaces matching backend Pydantic models
- Created useTelegramConfig query hook and useUpdateTelegramConfig mutation hook following established TanStack Query patterns
- Added Telegram Alerts section to SettingsPage: displays config status (Configured/Not Configured badge), bot status, masked chat ID, setup instructions, chat ID input with save, success/error feedback with auto-dismiss
- Added Test Mode section to SettingsPage: displays Active/Inactive badge using existing useDashboard hook, shows test_mode_warning if present, explains server-controlled nature
- All sections render independently — failure in one does not block others
- 5 hook tests + 35 SettingsPage tests (15 existing position size + 12 telegram + 5 test mode + 3 section independence)
- 125 total tests passing, 0 regressions
- No new npm packages added

### Change Log

- 2026-02-19: Story 8.3 implementation complete — Telegram config UI and Test Mode display added to Settings
- 2026-02-19: Code review fixes — added telegramMutation.reset() on save and input change to prevent stale error/success overlap; added bot_status 'error' display; added 2 new tests (bot error state, mutation reset on input change)

### File List

- frontend/src/api/types.ts (modified — added TelegramConfigResponse, TelegramConfigUpdate)
- frontend/src/hooks/useTelegramConfig.ts (new — query and mutation hooks)
- frontend/src/hooks/useTelegramConfig.test.ts (new — 5 tests)
- frontend/src/pages/SettingsPage.tsx (modified — added Telegram and Test Mode sections)
- frontend/src/pages/SettingsPage.test.tsx (modified — expanded from 15 to 33 tests)
