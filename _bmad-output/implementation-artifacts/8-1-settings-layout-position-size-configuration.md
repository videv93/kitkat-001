# Story 8.1: Settings Layout & Position Size Configuration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to access a Settings view and configure my position size per trade**,
so that **I can control how much is traded on each signal execution**.

## Acceptance Criteria

1. **Given** I am authenticated and click the Settings navigation element from the Dashboard, **When** the Settings view loads, **Then** I see a "Settings" header with a back navigation to Dashboard
2. **Given** I am authenticated and on the Settings view, **When** the view loads, **Then** I see a Position Size section with the current position size displayed (fetched from `GET /api/config`)
3. **Given** I am on the Settings view, **When** I edit the position size, **Then** I can enter a decimal value in an input field
4. **Given** I am on the Settings view, **When** I edit the maximum position size, **Then** I can enter a decimal value in an input field
5. **Given** I am on the Settings view, **When** I view the position size inputs, **Then** the unit (e.g., "ETH") is displayed alongside the inputs
6. **Given** I have modified position size values, **When** I click a Save button, **Then** changes are saved via `PUT /api/config` and a success confirmation is shown
7. **Given** I enter an invalid value (<=0 or max >100), **When** I try to save, **Then** validation prevents submission with an error message
8. **Given** the API returns a validation error, **When** the save fails, **Then** the error message from the API is displayed to the user

*FRs addressed: FR44, FR45*

## Tasks / Subtasks

- [x] Task 1: Add view routing to AuthGate for Settings navigation (AC: #1)
  - [x] 1.1: Add `currentView` state to AuthGate (`'dashboard' | 'settings'`) with hash-based navigation
  - [x] 1.2: Pass `onNavigate` callback to DashboardPage and SettingsPage
  - [x] 1.3: DashboardPage "Settings" link calls `onNavigate('settings')` instead of `href="#settings"`
  - [x] 1.4: SettingsPage "Back to Dashboard" link calls `onNavigate('dashboard')`
  - [x] 1.5: Listen to `hashchange` event for browser back/forward support
- [x] Task 2: Add TypeScript types for config API (AC: #2, #6, #8)
  - [x] 2.1: Add `PositionSizeConfig` interface to `api/types.ts` with `position_size: string`, `max_position_size: string`, `position_size_unit: string`
  - [x] 2.2: Add `PositionSizeUpdate` interface to `api/types.ts` with `position_size?: string`, `max_position_size?: string`
- [x] Task 3: Create `useConfig` hook (AC: #2, #6, #8)
  - [x] 3.1: Create `hooks/useConfig.ts` with `useQuery` for `GET /api/config` (queryKey: `['config']`)
  - [x] 3.2: Add `useMutation` for `PUT /api/config` with `onSuccess` invalidating `['config']` query
  - [x] 3.3: Create `hooks/useConfig.test.ts` with tests for loading, success, error states, and mutation
- [x] Task 4: Implement SettingsPage with Position Size section (AC: #1-#8)
  - [x] 4.1: Add header with "Settings" title and back navigation link
  - [x] 4.2: Add Position Size card with current values fetched from `useConfig`
  - [x] 4.3: Add two input fields: "Position Size" and "Max Position Size" with "ETH" unit label
  - [x] 4.4: Add Save button that calls the mutation
  - [x] 4.5: Show success message on save (auto-dismiss after 3s)
  - [x] 4.6: Show API error message on failure
  - [x] 4.7: Client-side validation: values must be > 0, max must be <= 100, position_size <= max_position_size
  - [x] 4.8: Loading state while config is fetching
- [x] Task 5: Write tests (AC: #1-#8)
  - [x] 5.1: Create `pages/SettingsPage.test.tsx` with tests for:
    - Settings header and back navigation renders
    - Position size values displayed from API
    - Input fields are editable
    - ETH unit label displayed
    - Save button triggers PUT request
    - Success message shown on save
    - Validation error displayed (value <= 0)
    - API error message displayed on failure
  - [x] 5.2: Update `AuthGate.test.tsx` for view routing (settings navigation)
- [x] Task 6: Verify all existing tests still pass (no regressions)

## Dev Notes

### Architecture & API Contracts

**Backend endpoint (already implemented):**

`GET /api/config` (authenticated) returns:
```json
{
  "position_size": "0.1",
  "max_position_size": "10.0",
  "position_size_unit": "ETH"
}
```

`PUT /api/config` (authenticated) accepts:
```json
{
  "position_size": "1.0",
  "max_position_size": "5.0"
}
```
- Both fields are optional - only provided fields are updated
- Returns updated `PositionSizeConfig` on success
- Returns 400 with `{"detail": {"error": "position_size cannot exceed max_position_size", "code": "INVALID_CONFIG", ...}}` on cross-validation failure
- Returns 422 on Pydantic validation failure (e.g., value <= 0, max > 100)
- Defaults: position_size = "0.1", max_position_size = "10.0"
- System max limit: 100 ETH

### Existing Code Patterns (MUST FOLLOW)

**View routing:** Currently AuthGate renders ConnectPage or DashboardPage based on `isAuthenticated`. There is NO react-router-dom. Navigation between Dashboard and Settings must use hash-based state (`#settings` / `#dashboard`) managed in AuthGate. SettingsPage already exists as a placeholder.

**Hook pattern** (established by `useDashboard.ts`, `useVolumeStats.ts`, etc.):
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { SomeType } from '../api/types'

export function useSomething() {
  return useQuery({
    queryKey: ['something'],
    queryFn: () => apiClient<SomeType>('/api/something'),
  })
}
```

**Mutation pattern** (new for this story - use TanStack Query `useMutation`):
```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'

const queryClient = useQueryClient()
const mutation = useMutation({
  mutationFn: (data: PositionSizeUpdate) =>
    apiClient<PositionSizeConfig>('/api/config', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
})
```

**Color scheme / styling** (from Stories 7.1, 7.2, 7.3):
- Dark theme: `bg-gray-950` base, `text-white` primary, `text-gray-400` muted, `border-gray-800`
- Cards: `bg-gray-900` with `border-gray-800`, `p-4`
- Section headers: `text-sm font-medium text-gray-400` with `mb-3`
- Input styling: `bg-gray-800 text-white border-gray-700 rounded-md px-3 py-2`
- Button: `bg-blue-600 hover:bg-blue-700 text-white rounded-md px-4 py-2`
- Success text: `text-green-400`
- Error text: `text-red-400`
- HTML entity icons (established pattern): checkmark `&#10003;`

**Test mock pattern** (from Stories 7.1, 7.2, 7.3):
```typescript
vi.mock('../hooks/useConfig', () => ({
  useConfig: vi.fn(),
}))
const mockUseConfig = vi.mocked(useConfig)
mockUseConfig.mockReturnValue({
  data: { position_size: '0.1', max_position_size: '10.0', position_size_unit: 'ETH' },
  isLoading: false,
  isError: false,
  error: null,
} as any)
```

**apiClient already handles:**
- Auto-adds `Content-Type: application/json` when `body` is present
- Auto-adds `Authorization: Bearer {token}` from localStorage
- 401 → clears token + window.location.reload()
- Non-ok → throws Error with `detail` or `error` from response body

### Critical Constraints

- **DO NOT** install any new npm packages — TanStack Query (with `useMutation`, `useQueryClient`) is already installed
- **DO NOT** add react-router-dom — keep hash-based view switching in AuthGate
- **DO NOT** modify `apiClient` in `api/client.ts`
- **DO NOT** modify existing Dashboard sections
- Tailwind CSS v4: uses `@import "tailwindcss"` in CSS, NO tailwind.config.js
- Vitest with jsdom environment (already configured in `vite.config.ts`)
- SettingsPage already exists as a placeholder — modify in place
- DashboardPage "Settings" link currently uses `href="#settings"` — change to callback

### Navigation Pattern

The `#settings` / `#dashboard` hash approach:
1. AuthGate manages `currentView` state initialized from `window.location.hash`
2. On hash change, update `currentView`
3. Render DashboardPage when `currentView === 'dashboard'` (or default)
4. Render SettingsPage when `currentView === 'settings'`
5. Pass `onNavigate` to both pages: updates hash + state
6. SettingsPage accepts `onNavigate` prop for "Back to Dashboard" link

### Previous Story Intelligence (Stories 7.1, 7.2, 7.3)

**From Story 7.3:**
- DashboardPage has 6 hooks, 275 lines — growing but accepted
- 78 tests pass total across frontend
- Sections render independently with `{(hookData || data) && ...}` pattern
- Code review accepted HTML entities for icons
- `getAllByText` needed when duplicate text appears

**From Story 7.2:**
- Export helper functions for testability (e.g., `formatUSD`)
- Ensure sections render independently even if API fails
- Test edge cases including zero/empty states

**From Story 7.1:**
- STATUS_CONFIG and DEX_STATUS_DOT constants for color mapping
- Dark theme styling pattern established

### Git Intelligence

Recent commits: Stories 6.1, 6.2 committed. Stories 6.3, 7.1, 7.2, 7.3 implemented but uncommitted. Frontend has 78 tests passing. SettingsPage.tsx exists as a stub with "Settings — coming in Story 8.1" placeholder text.

### Project Structure Notes

- All new files go in existing directories — no new folders needed
- Types: `frontend/src/api/types.ts` (append new interfaces)
- Hooks: `frontend/src/hooks/useConfig.ts`
- Tests: `frontend/src/hooks/useConfig.test.ts`, `frontend/src/pages/SettingsPage.test.tsx`
- Modify: `frontend/src/components/AuthGate.tsx` (add view routing)
- Modify: `frontend/src/pages/SettingsPage.tsx` (implement settings UI)
- Modify: `frontend/src/pages/DashboardPage.tsx` (change Settings link to callback)

### References

- [Source: _bmad-output/planning-artifacts/epics-frontend.md — Epic 3, Story 3.1]
- [Source: _bmad-output/planning-artifacts/prd.md — FR44, FR45]
- [Source: src/kitkat/api/config.py — GET/PUT /api/config endpoints]
- [Source: src/kitkat/models.py — PositionSizeConfig, PositionSizeUpdate Pydantic models]
- [Source: _bmad-output/implementation-artifacts/7-3-onboarding-progress-recent-errors.md — Established patterns]
- [Source: _bmad-output/project-context.md — Tech stack, naming conventions]
- [Source: frontend/src/components/AuthGate.tsx — Current routing (no Settings view)]
- [Source: frontend/src/pages/SettingsPage.tsx — Placeholder stub]
- [Source: frontend/src/pages/DashboardPage.tsx — Settings link at line 48]
- [Source: frontend/src/api/client.ts — apiClient with auto Content-Type and auth]
- [Source: frontend/src/api/types.ts — Existing TypeScript interfaces]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Added `PositionSizeConfig` and `PositionSizeUpdate` TypeScript interfaces to `api/types.ts`
- Created `useConfig` hook with TanStack Query `useQuery` for `GET /api/config`
- Created `useUpdateConfig` hook with TanStack Query `useMutation` for `PUT /api/config` with cache invalidation
- Implemented hash-based view routing in AuthGate: `currentView` state, `onNavigate` callback, `hashchange` listener
- DashboardPage accepts `onNavigate` prop; Settings link changed from `<a href>` to `<button onClick>`
- SettingsPage fully implemented: Position Size card with two labeled decimal inputs, ETH unit labels, Save button, client-side validation (>0, max<=100, size<=max), success message (auto-dismiss 3s), API error display, loading state
- 5 hook tests (3 useConfig + 2 useUpdateConfig), 13 SettingsPage tests, 4 AuthGate tests (2 new for settings routing)
- All 98 tests pass with zero regressions (was 78)

### Change Log

- 2026-02-18: Story 8.1 implementation complete — Settings view routing, position size configuration with validation, 20 new tests
- 2026-02-18: Code review — fixed 4 issues (L2 success/error overlap, M3 missing pending test, M4 validation not clearing on edit), added 2 tests → 100 total

### File List

- frontend/src/api/types.ts (modified — added PositionSizeConfig, PositionSizeUpdate)
- frontend/src/hooks/useConfig.ts (new — useConfig + useUpdateConfig hooks)
- frontend/src/hooks/useConfig.test.ts (new — 5 tests)
- frontend/src/components/AuthGate.tsx (modified — hash-based view routing with settings support)
- frontend/src/components/AuthGate.test.tsx (modified — 4 tests, 2 new for settings routing)
- frontend/src/pages/DashboardPage.tsx (modified — accepts onNavigate prop, Settings button)
- frontend/src/pages/SettingsPage.tsx (modified — full implementation replacing placeholder)
- frontend/src/pages/SettingsPage.test.tsx (new — 15 tests)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Date:** 2026-02-18 | **Verdict:** PASS with fixes applied

### Issues Found: 1 High, 4 Medium, 2 Low

**H1 [NOTED] ConnectPage.tsx/test modified in git but not in story File List** — These are uncommitted changes from Story 6.3, not 8.1. No action needed for this story but should be committed with 6.3.

**M1 [ACCEPTED] Header hierarchy shows app name as h1, "Settings" as h2** — Consistent with DashboardPage pattern. AC satisfied by presence of "Settings" text + back nav.

**M2 [ACCEPTED] Background refetch can overwrite unsaved edits** — Low risk given single-user app with no polling. Acceptable for MVP.

**M3 [FIXED] No test for disabled Save button during mutation pending state** — Added test verifying `Saving...` text and disabled attribute.

**M4 [FIXED] Validation error persists after user corrects input** — Added `setValidationError(null)` to both input onChange handlers. Added test.

**L1 [ACCEPTED] `input type="number"` allows scientific notation** — Edge case, parseFloat handles it correctly, validation catches NaN.

**L2 [FIXED] Success message and error can display simultaneously** — Added `setShowSuccess(false)` at start of `handleSave()`.

### Fixes Applied
- `SettingsPage.tsx`: Clear `showSuccess` on save, clear `validationError` on input change
- `SettingsPage.test.tsx`: +2 tests (pending button state, validation clears on edit)
- **100 tests passing** (was 98)
