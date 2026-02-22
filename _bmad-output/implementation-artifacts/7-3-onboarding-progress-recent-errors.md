# Story 7.3: Onboarding Progress & Recent Errors

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to see my onboarding progress and any recent errors on the dashboard**,
so that **I know what setup steps remain and whether any issues need attention**.

## Acceptance Criteria

1. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see an onboarding progress indicator showing completion status (e.g., "4/5" with a progress bar)
2. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** each onboarding step is listed with its completion state (wallet connected, DEX authorized, webhook configured, test signal sent, first live trade)
3. **Given** incomplete onboarding steps exist, **When** I view the onboarding section, **Then** incomplete steps are visually distinct and hint at what action is needed
4. **Given** all 5 onboarding steps are complete, **When** I view the dashboard, **Then** the onboarding section collapses or shows a completion message
5. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see a recent errors summary section
6. **Given** no recent errors exist, **When** I view the errors section, **Then** it shows "No recent errors" with a checkmark
7. **Given** errors exist, **When** I view the errors section, **Then** the most recent 3 are displayed with timestamp, error type, and DEX

*FRs addressed: FR33*

## Tasks / Subtasks

- [x] Task 1: Add TypeScript types for onboarding and error API responses (AC: #1, #2, #5, #7)
  - [x] 1.1: Add `OnboardingStep` interface to `api/types.ts` with `id: string`, `name: string`, `complete: boolean`
  - [x] 1.2: Add `OnboardingResponse` interface to `api/types.ts` with `complete: boolean`, `progress: string`, `steps: OnboardingStep[]`
  - [x] 1.3: Add `ErrorLogEntry` interface to `api/types.ts` with `id: string`, `timestamp: string`, `level: 'error' | 'warning'`, `error_type: string`, `message: string`, `context: Record<string, unknown>`
  - [x] 1.4: Add `ErrorLogResponse` interface to `api/types.ts` with `errors: ErrorLogEntry[]`, `count: number`
- [x] Task 2: Create `useOnboarding` hook (AC: #1, #2, #3, #4)
  - [x] 2.1: Create `hooks/useOnboarding.ts` using TanStack Query `useQuery` with queryKey `['onboarding']`
  - [x] 2.2: Fetch from `GET /api/onboarding` using existing `apiClient`
  - [x] 2.3: Set `refetchInterval: 30_000` to match dashboard polling pattern
  - [x] 2.4: Create `hooks/useOnboarding.test.ts` with tests for loading, success, error states, and all-complete state
- [x] Task 3: Create `useErrorLog` hook (AC: #5, #6, #7)
  - [x] 3.1: Create `hooks/useErrorLog.ts` using TanStack Query `useQuery` with queryKey `['errors']`
  - [x] 3.2: Fetch from `GET /api/errors?limit=3` using existing `apiClient` (only need most recent 3 for dashboard)
  - [x] 3.3: Set `refetchInterval: 30_000`
  - [x] 3.4: Create `hooks/useErrorLog.test.ts` with tests for loading, success, empty, and error states
- [x] Task 4: Add onboarding progress section to DashboardPage (AC: #1, #2, #3, #4)
  - [x] 4.1: Add Onboarding card below Execution Metrics section
  - [x] 4.2: Display progress indicator as "X/5" with a visual progress bar
  - [x] 4.3: List all 5 steps with checkmark (complete) or circle (incomplete) indicators
  - [x] 4.4: Incomplete steps should use muted styling and hint text
  - [x] 4.5: When all 5 steps complete, show a collapsed "Onboarding Complete" message with checkmark instead of the step list
- [x] Task 5: Add recent errors section to DashboardPage (AC: #5, #6, #7)
  - [x] 5.1: Add Recent Errors card below Onboarding section
  - [x] 5.2: When no errors exist, show "No recent errors" with a green checkmark
  - [x] 5.3: When errors exist, show up to 3 entries with: timestamp (relative or formatted), error_type, and DEX from context
  - [x] 5.4: Use appropriate error styling (red/yellow depending on level)
- [x] Task 6: Write DashboardPage tests for new sections (AC: #1-#7)
  - [x] 6.1: Test onboarding progress renders with "X/5" and progress bar
  - [x] 6.2: Test all 5 onboarding steps listed with correct names
  - [x] 6.3: Test incomplete steps have distinct styling
  - [x] 6.4: Test all-complete state shows completion message
  - [x] 6.5: Test "No recent errors" with checkmark when errors array is empty
  - [x] 6.6: Test error entries display with timestamp, error_type, and DEX context
  - [x] 6.7: Test at most 3 errors are shown even if more exist
- [x] Task 7: Verify all existing tests still pass (no regressions)

## Dev Notes

### Architecture & API Contracts

**Two endpoints to integrate:**

`GET /api/onboarding` (authenticated) returns:
```json
{
  "complete": false,
  "progress": "3/5",
  "steps": [
    { "id": "wallet_connected", "name": "Connect Wallet", "complete": true },
    { "id": "dex_authorized", "name": "Authorize DEX Trading", "complete": true },
    { "id": "webhook_configured", "name": "Configure TradingView Webhook", "complete": true },
    { "id": "test_signal_sent", "name": "Send Test Signal", "complete": false },
    { "id": "first_live_trade", "name": "First Live Trade", "complete": false }
  ]
}
```
- Always returns exactly 5 steps in the order listed
- `progress` format is always "X/5"
- `complete` is true only when all 5 steps are complete

`GET /api/errors` (authenticated) returns:
```json
{
  "errors": [
    {
      "id": "err-42",
      "timestamp": "2026-02-17T08:30:00Z",
      "level": "error",
      "error_type": "DEX_TIMEOUT",
      "message": "Extended DEX did not respond within 30s",
      "context": { "dex": "extended", "signal_id": "abc123" }
    }
  ],
  "count": 1
}
```
- Supports query params: `limit` (default 50, max 100), `hours` (filter by time range)
- For dashboard, use `?limit=3` to get only the most recent 3
- Empty result: `{ "errors": [], "count": 0 }`
- `context.dex` contains the DEX identifier (if applicable)
- `level` is either "error" or "warning"

### Existing Code Patterns (MUST FOLLOW)

**Hook pattern** (established by `useDashboard.ts`, `useVolumeStats.ts`, `useExecutionStats.ts`):
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { SomeType } from '../api/types'

export function useSomething() {
  return useQuery({
    queryKey: ['something'],
    queryFn: () => apiClient<SomeType>('/api/something'),
    refetchInterval: 30_000,
  })
}
```

**Color scheme / styling** (from Stories 7.1, 7.2):
- Dark theme: `bg-gray-950` base, `text-white` primary, `text-gray-400` muted, `border-gray-800`
- Cards: `bg-gray-900` with `border-gray-800`, `p-4`
- Section headers: `text-sm font-medium text-gray-400` with `mb-3`
- Inner rows: `bg-gray-800 px-4 py-2 rounded-md`
- Green success: `text-green-400`
- Error/red: `text-red-400`
- Warning/yellow: `text-yellow-400`
- HTML entity icons (established pattern): checkmark `&#10003;`, warning `&#9888;`, cross `&#10007;`

**Test mock pattern** (from Stories 7.1, 7.2):
```typescript
vi.mock('../hooks/useOnboarding', () => ({
  useOnboarding: vi.fn(),
}))

const mockUseOnboarding = vi.mocked(useOnboarding)
mockUseOnboarding.mockReturnValue({
  data: { complete: false, progress: '3/5', steps: [...] },
  isLoading: false,
  isError: false,
  error: null,
} as any)
```

### Critical Constraints

- **DO NOT** install any new npm packages — everything needed is already installed
- **DO NOT** modify `apiClient` in `api/client.ts`
- **DO NOT** add react-router-dom — keep conditional rendering via AuthGate
- **DO NOT** modify existing System Status, DEX Health, Volume, or Execution sections from Stories 7.1/7.2
- **DO NOT** create separate component files — keep sections in DashboardPage until complexity warrants extraction
- Tailwind CSS v4: uses `@import "tailwindcss"` in CSS, NO tailwind.config.js
- Vitest with jsdom environment (already configured in `vite.config.ts`)
- `apiClient` auto-adds Bearer token and handles 401 by clearing token + reload

### Dashboard Layout Order

The DashboardPage currently has this section order (top to bottom):
1. Header (branding, test mode badge, Settings, Disconnect)
2. System Status indicator (Everything OK / Degraded / Offline)
3. DEX Health cards
4. Volume Stats
5. Execution Metrics

**Add new sections after Execution Metrics:**
6. **Onboarding Progress** (new — this story)
7. **Recent Errors** (new — this story)

Both new sections should render independently of the `data` (dashboard) gate — they have their own hooks. Follow the same pattern as Volume/Execution sections which render with `{(hookData || data) && ...}`.

### DashboardResponse Already Has Summary Data

Note: `DashboardResponse` already contains `onboarding_complete: boolean` and `recent_errors: number`. These can be used as quick fallback indicators while the dedicated hooks load:
- `data.onboarding_complete` — show "Complete" or "In Progress" while `useOnboarding` loads
- `data.recent_errors` — show error count while `useErrorLog` loads

### Progress Bar Implementation

Use a simple Tailwind-based progress bar:
```html
<div className="h-2 w-full rounded-full bg-gray-800">
  <div className="h-2 rounded-full bg-green-500" style={{ width: `${(completed/5)*100}%` }} />
</div>
```

### Timestamp Formatting

For error timestamps, use a simple relative time approach or formatted date. Keep it minimal — no external date libraries. Options:
- `new Date(timestamp).toLocaleString()` for full timestamp
- Simple relative time helper: "2m ago", "1h ago", "3h ago" (preferred for dashboard glance UX)

### Project Structure Notes

- All new files go in existing directories — no new folders needed
- Types: `frontend/src/api/types.ts` (append new interfaces)
- Hooks: `frontend/src/hooks/useOnboarding.ts`, `frontend/src/hooks/useErrorLog.ts`
- Tests: colocated with source files (`.test.ts` / `.test.tsx`)
- Page: modify existing `frontend/src/pages/DashboardPage.tsx`

### Previous Story Intelligence (Stories 7.1, 7.2)

**From Story 7.1:**
- Established DashboardPage layout: header, system status, DEX health cards
- STATUS_CONFIG and DEX_STATUS_DOT constants for color mapping
- 14 new tests (4 hook + 10 page); all passed
- HTML entities for icons (&#10003;, &#9888;, &#10007;) — accepted as pattern
- No `staleTime` in hooks — accepted, follow same pattern
- AuthGate.test.tsx was updated for new loading text

**From Story 7.2:**
- Added Volume Stats and Execution Metrics sections
- Created `useVolumeStats` and `useExecutionStats` hooks
- Established `formatUSD` helper (exported)
- Moved sections outside `{data && ...}` block — render independently when hook data available
- 13 new tests; all 63 tests pass after code review fixes
- Code review found: decoupled stats sections from dashboard data gate (MEDIUM fix)
- Zero-state test needed `getAllByText` for duplicate "$0" values

**From Story 7.2 code review:**
- Export helper functions so they can be unit tested
- Ensure sections render independently even if dashboard API fails
- Test edge cases including zero/empty states

### Git Intelligence

Recent commits show Stories 6.1, 6.2 committed. Stories 6.3, 7.1, 7.2 are implemented but uncommitted (visible in working tree). The frontend has 63 tests passing. Current DashboardPage.tsx imports `useDashboard`, `useVolumeStats`, `useExecutionStats`.

### References

- [Source: _bmad-output/planning-artifacts/epics-frontend.md — Epic 2, Story 2.3]
- [Source: _bmad-output/planning-artifacts/prd.md — FR33, Journey 1]
- [Source: src/kitkat/models.py — OnboardingResponse, OnboardingStep, ErrorLogEntry, ErrorLogResponse]
- [Source: src/kitkat/api/stats.py — get_onboarding_status endpoint, ONBOARDING_STEPS]
- [Source: src/kitkat/api/errors.py — get_errors endpoint with limit/hours params]
- [Source: _bmad-output/implementation-artifacts/7-1-dashboard-layout-system-health-status.md — Dashboard patterns]
- [Source: _bmad-output/implementation-artifacts/7-2-volume-stats-execution-metrics.md — Stats hook patterns, code review learnings]
- [Source: _bmad-output/project-context.md — Tech stack, naming conventions]
- [Source: frontend/src/pages/DashboardPage.tsx — Current dashboard implementation]
- [Source: frontend/src/api/types.ts — Existing TypeScript interfaces]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Existing "falls back to dashboard data" test failed due to duplicate em dash (`—`) — one from volume "This Week" fallback, one from onboarding progress fallback. Fixed by using `getAllByText` instead of `getByText`.

### Completion Notes List

- Added 4 TypeScript interfaces (`OnboardingStep`, `OnboardingResponse`, `ErrorLogEntry`, `ErrorLogResponse`) to `api/types.ts`
- Created `useOnboarding` hook fetching `GET /api/onboarding` with 30s polling via TanStack Query
- Created `useErrorLog` hook fetching `GET /api/errors?limit=3` with 30s polling
- Added Onboarding Progress card to DashboardPage: progress indicator ("X/5"), Tailwind progress bar, 5-step list with checkmark/circle icons, muted styling for incomplete steps
- When all 5 steps complete (`onboardingData.complete === true`), shows collapsed "Onboarding Complete" message instead of step list
- Fallback: when `useOnboarding` still loading, shows dashboard `onboarding_complete` data
- Added Recent Errors card to DashboardPage: "No recent errors" with green checkmark when empty, error entries with error_type, timestamp (toLocaleString), DEX context, level-based styling (red for error, yellow for warning)
- Both sections render independently of dashboard data gate using `{(hookData || data) && ...}` pattern
- 8 new hook tests (4 per hook) + 7 new page tests = 15 new tests; all 78 tests pass with zero regressions

### Change Log

- 2026-02-18: Story 7.3 implementation complete — Onboarding progress, recent errors, dedicated hooks, progress bar, step list, error display with level-based styling
- 2026-02-18: Addressed code review findings — 3 MEDIUM issues fixed, 3 LOW documented as acceptable. 78/78 tests pass.

### File List

- frontend/src/api/types.ts (modified — added onboarding/error log types)
- frontend/src/hooks/useOnboarding.ts (new — TanStack Query hook for onboarding)
- frontend/src/hooks/useOnboarding.test.ts (new — 4 tests)
- frontend/src/hooks/useErrorLog.ts (new — TanStack Query hook for error log)
- frontend/src/hooks/useErrorLog.test.ts (new — 4 tests)
- frontend/src/pages/DashboardPage.tsx (modified — added onboarding progress + recent errors sections)
- frontend/src/pages/DashboardPage.test.tsx (modified — 27 tests total: 20 from 7.1/7.2 + 7 new)

## Senior Developer Review (AI)

### Review Model
Claude Opus 4.6

### Review Date
2026-02-18

### Findings

| # | Severity | Description | Status |
|---|----------|-------------|--------|
| M1 | MEDIUM | Progress bar shows 0% width when dashboard fallback shows "5/5" — visual inconsistency between text and bar | FIXED |
| M2 | MEDIUM | Progress bar denominator hard-coded to 5 instead of using `steps.length` | FIXED |
| M3 | MEDIUM | No test for onboarding/error sections rendering independently when dashboard fails | FIXED |
| L1 | LOW | Mixed icon encoding: HTML entities for some, Unicode escapes for others | ACCEPTED |
| L2 | LOW | DashboardPage.tsx growing large at 273 lines with 6 hooks | ACCEPTED |
| L3 | LOW | Duplicate "No recent errors" text in two branches, fallback path untested | ACCEPTED |

### Fixes Applied
- **M1**: Progress bar now shows `100%` width when `data.onboarding_complete` is true and `onboardingData` hasn't loaded yet
- **M2**: Changed hard-coded `/5` to `/onboardingData.steps.length` for dynamic step count
- **M3**: Extended "renders stats sections even when dashboard endpoint fails" test to also verify Onboarding and Recent Errors sections render independently

### Verdict
PASS — All MEDIUM issues fixed, LOW issues documented as acceptable. 78/78 tests pass.
