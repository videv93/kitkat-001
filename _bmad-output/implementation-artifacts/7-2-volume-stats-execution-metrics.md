# Story 7.2: Volume Stats & Execution Metrics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to see my trading volume and execution statistics on the dashboard**,
so that **I can track my progress toward airdrop volume targets**.

## Acceptance Criteria

1. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see today's total volume displayed prominently (formatted as USD, e.g., "$31k")
2. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see this week's total volume displayed
3. **Given** multiple DEXs are active, **When** the dashboard loads, **Then** volume is broken down per DEX
4. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see the total execution count (signals processed today)
5. **Given** I am authenticated and on the Dashboard view, **When** the dashboard loads, **Then** I see the success rate as a percentage (e.g., "100%")
6. Stats are fetched from `GET /api/stats/volume` and `GET /api/stats/executions`
7. **Given** no executions exist yet, **When** the dashboard loads, **Then** the stats section shows zeros with no error state

*FRs addressed: FR34, FR35, FR36, FR37, FR38*

## Tasks / Subtasks

- [x] Task 1: Add TypeScript types for volume and execution stats API responses (AC: #6)
  - [x] 1.1: Add `VolumeStatsResponse` interface to `api/types.ts` matching `GET /api/stats/volume` response shape
  - [x] 1.2: Add `ExecutionStatsResponse` interface to `api/types.ts` matching `GET /api/stats/executions` response shape
- [x] Task 2: Create `useVolumeStats` hook (AC: #1, #2, #3, #6)
  - [x] 2.1: Create `hooks/useVolumeStats.ts` using TanStack Query `useQuery` with queryKey `['stats', 'volume']`
  - [x] 2.2: Fetch from `GET /api/stats/volume` using existing `apiClient`
  - [x] 2.3: Set `refetchInterval: 30_000` to match dashboard polling pattern
  - [x] 2.4: Create `hooks/useVolumeStats.test.ts` with tests for loading, success, error states
- [x] Task 3: Create `useExecutionStats` hook (AC: #4, #5, #6)
  - [x] 3.1: Create `hooks/useExecutionStats.ts` using TanStack Query `useQuery` with queryKey `['stats', 'executions']`
  - [x] 3.2: Fetch from `GET /api/stats/executions` using existing `apiClient`
  - [x] 3.3: Set `refetchInterval: 30_000`
  - [x] 3.4: Create `hooks/useExecutionStats.test.ts` with tests for loading, success, error states
- [x] Task 4: Add volume stats section to DashboardPage (AC: #1, #2, #3, #7)
  - [x] 4.1: Add Volume Stats card below DEX Health section with today's total volume prominently displayed
  - [x] 4.2: Display this week's total volume
  - [x] 4.3: Show per-DEX volume breakdown when multiple DEXs are active
  - [x] 4.4: Format volume as USD with abbreviation (e.g., "$31k", "$284k") for large values
  - [x] 4.5: Show zeros gracefully when no executions exist (no error state)
- [x] Task 5: Add execution metrics section to DashboardPage (AC: #4, #5, #7)
  - [x] 5.1: Display total execution count for today
  - [x] 5.2: Display success rate percentage
  - [x] 5.3: Show "N/A" for success rate when zero executions exist
- [x] Task 6: Write DashboardPage tests for new sections (AC: #1-#7)
  - [x] 6.1: Test volume stats render with formatted USD values
  - [x] 6.2: Test per-DEX breakdown renders when multiple DEXs present
  - [x] 6.3: Test execution count and success rate display
  - [x] 6.4: Test zero-state displays zeros without error
  - [x] 6.5: Test loading/error states for stats hooks (fallback to dashboard data test)
- [x] Task 7: Verify all existing tests still pass (no regressions)

## Dev Notes

### Architecture & API Contracts

**Two dedicated stats endpoints to call (NOT the dashboard endpoint for detailed stats):**

`GET /api/stats/volume` returns:
```json
{
  "today": {
    "extended": {"volume_usd": "47250.00", "executions": 14},
    "total": {"volume_usd": "47250.00", "executions": 14}
  },
  "this_week": {
    "extended": {"volume_usd": "284000.00", "executions": 89},
    "total": {"volume_usd": "284000.00", "executions": 89}
  },
  "updated_at": "2026-01-19T10:00:00Z"
}
```
- "today" = UTC midnight to current time
- "this_week" = Monday 00:00 UTC to current time
- Zero values are `"0.00"` (not null or missing)
- Per-DEX keys are dynamic (e.g., "extended", "paradex") plus "total"

`GET /api/stats/executions` returns:
```json
{
  "today": {
    "total": 14,
    "successful": 14,
    "failed": 0,
    "partial": 0,
    "success_rate": "100.00%"
  },
  "this_week": {
    "total": 89,
    "successful": 87,
    "failed": 1,
    "partial": 1,
    "success_rate": "97.75%"
  },
  "all_time": {
    "total": 523,
    "successful": 515,
    "failed": 5,
    "partial": 3,
    "success_rate": "98.47%"
  }
}
```
- Zero executions returns `"N/A"` for success_rate
- Test mode executions excluded

### Existing Code Patterns (MUST FOLLOW)

**Hook pattern** (from `useDashboard.ts`):
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

**Color scheme / styling** (from Story 7.1 DashboardPage):
- Dark theme: `bg-gray-950` base, `text-white` primary, `text-gray-400` muted, `border-gray-800`
- Cards: `bg-gray-900` with `border-gray-800`, `p-4`
- Section headers: `text-sm font-medium text-gray-400` with `mb-3`
- Inner rows: `bg-gray-800 px-4 py-2 rounded-md`

**Volume formatting helper:** Create a simple `formatUSD` function inline or as a const in DashboardPage — abbreviate large values:
- < 1000: "$450"
- >= 1000 and < 1M: "$31k", "$284k"
- >= 1M: "$1.2M"
- Parse from string decimal (e.g., "47250.00" -> "$47k")

### Critical Constraints

- **DO NOT** install any new npm packages
- **DO NOT** modify `apiClient` in `api/client.ts`
- **DO NOT** add react-router-dom — keep conditional rendering via AuthGate
- **DO NOT** modify existing System Status or DEX Health sections from Story 7.1
- Tailwind CSS v4: uses `@import "tailwindcss"` in CSS, NO tailwind.config.js
- Vitest with jsdom environment (already configured in `vite.config.ts`)
- `apiClient` auto-adds Bearer token and handles 401 by clearing token + reload

### Dashboard Response Already Has Summary Data

Note: `DashboardResponse` (fetched by `useDashboard`) already contains `volume_today` and `executions_today` fields. However, story AC #2 requires **this week's** volume which is NOT in the dashboard endpoint. Use the dedicated stats endpoints for the full data. The `useDashboard` hook data can be used as a quick fallback or alongside the dedicated hooks.

**Recommended approach:** Use `useVolumeStats` and `useExecutionStats` as the primary data sources for this section. The volume/execution section should gracefully handle its own loading state independently of the dashboard hook.

### Project Structure Notes

- All new files go in existing directories — no new folders needed
- Types: `frontend/src/api/types.ts` (append new interfaces)
- Hooks: `frontend/src/hooks/useVolumeStats.ts`, `frontend/src/hooks/useExecutionStats.ts`
- Tests: colocated with source files (`.test.ts` / `.test.tsx`)
- Page: modify existing `frontend/src/pages/DashboardPage.tsx`

### Previous Story Intelligence (Story 7.1)

- Story 7.1 established the full DashboardPage structure: header, system status indicator, DEX health cards
- 45 tests currently passing (14 from 7.1): 4 hook tests + 10 page tests
- ConnectKit requires ResizeObserver polyfill (already in `test/setup.ts`)
- `events` package polyfill for ConnectKit (already installed)
- TOKEN_KEY = `'kitkat_token'` in `lib/constants.ts`
- Code review found: HTML entities for icons may render inconsistently (accepted as LOW) — continue using same pattern for consistency
- No `staleTime` in useDashboard (accepted as LOW) — follow same pattern for new hooks

### Git Intelligence

Recent commits show Story 6.2 and 6.1 completed. Stories 6.3 and 7.1 are implemented but uncommitted. The frontend codebase is stable with all 45 tests passing.

### References

- [Source: _bmad-output/planning-artifacts/epics-frontend.md — Epic 2, Story 2.2]
- [Source: _bmad-output/planning-artifacts/epics.md — Stories 5.1, 5.2, 5.3 (backend implementations)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR34-FR38, Journey 1, Journey 5]
- [Source: _bmad-output/planning-artifacts/architecture.md — Stats Service, API boundaries]
- [Source: _bmad-output/implementation-artifacts/7-1-dashboard-layout-system-health-status.md — Previous story patterns]
- [Source: _bmad-output/project-context.md — Tech stack, naming conventions, anti-patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Zero-state test initially failed due to duplicate "$0" text (today + this week both render "$0") — fixed by using `getAllByText` assertion

### Completion Notes List

- Added 3 TypeScript interfaces (`VolumeDexEntry`, `VolumeStatsResponse`, `ExecutionStatsResponse`) + 1 sub-interface (`ExecutionStatsPeriod`) to `api/types.ts`
- Created `useVolumeStats` hook fetching `GET /api/stats/volume` with 30s polling via TanStack Query
- Created `useExecutionStats` hook fetching `GET /api/stats/executions` with 30s polling
- Added Volume Stats card to DashboardPage: today's volume, this week's volume, per-DEX breakdown (shown when >1 DEX)
- Added Execution Metrics card to DashboardPage: today's execution count + success rate
- `formatUSD` helper abbreviates values ($47k, $284k, $1.2M)
- Graceful fallback: when stats hooks are still loading, falls back to `useDashboard` data for today's values
- 8 new hook tests (4 per hook) + 5 new page tests = 13 new tests; all 58 tests pass with zero regressions

### Change Log

- 2026-02-17: Story 7.2 implementation complete — Volume stats, execution metrics, dedicated stats hooks, USD formatting, per-DEX breakdown
- 2026-02-17: Addressed code review findings — 3 MEDIUM issues fixed, 3 LOW documented as acceptable. 63/63 tests pass.

### File List

- frontend/src/api/types.ts (modified — added volume/execution stats types)
- frontend/src/hooks/useVolumeStats.ts (new — TanStack Query hook for volume stats)
- frontend/src/hooks/useVolumeStats.test.ts (new — 4 tests)
- frontend/src/hooks/useExecutionStats.ts (new — TanStack Query hook for execution stats)
- frontend/src/hooks/useExecutionStats.test.ts (new — 4 tests)
- frontend/src/pages/DashboardPage.tsx (modified — added volume stats + execution metrics sections, exported formatUSD, decoupled stats from dashboard gate)
- frontend/src/pages/DashboardPage.test.tsx (modified — 20 tests total: 10 from 7.1 + 10 new including formatUSD unit tests)

## Senior Developer Review (AI)

### Review Model
Claude Opus 4.6

### Review Date
2026-02-17

### Findings

| # | Severity | Description | Status |
|---|----------|-------------|--------|
| M1 | MEDIUM | `formatUSD` had no unit tests — edge cases untested (million values, boundary, NaN) | FIXED |
| M2 | MEDIUM | Volume/Execution sections nested inside `{data && ...}` — stats hidden when dashboard fails despite having own data | FIXED |
| M3 | MEDIUM | "This Week" fallback em dash "—" when volumeData null was untested | FIXED |
| L1 | LOW | `formatUSD` not exported — couldn't be reused or unit tested independently | FIXED (as part of M1) |
| L2 | LOW | Per-DEX volume breakdown only shows "today" data, not "this week" per-DEX | ACCEPTED |
| L3 | LOW | Three concurrent API calls on dashboard mount (useDashboard + 2 stats hooks) — minor redundancy | ACCEPTED |

### Fixes Applied
- **M1+L1**: Exported `formatUSD`, added 4 unit tests covering under-1k, k-suffix, M-suffix, NaN/empty edge cases
- **M2**: Moved Volume and Execution sections outside `{data && ...}` block — they now render when `volumeData || data` and `execData || data` respectively
- **M3**: Added assertion for em dash "—" in the fallback test

### Verdict
PASS — All MEDIUM issues fixed, LOW issues documented as acceptable. 63/63 tests pass.
