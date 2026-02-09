# Story 6.2: Connect Screen & Wallet Connection UI

Status: done

## Story

As a **user**,
I want **to see a Connect Screen with a wallet connect button and clear explanations of what connecting does**,
So that **I feel confident connecting my MetaMask wallet to kitkat-001**.

## Acceptance Criteria

1. **Given** I am not authenticated
   **When** I visit the kitkat-001 application
   **Then** I see a Connect Screen with the kitkat-001 branding and a brief description

2. **Given** I am on the Connect Screen
   **When** I look at the page
   **Then** I see a "Connect Wallet" button powered by ConnectKit
   **And** I see trust-building copy explaining: "Signs a message to verify ownership - no fund access granted"

3. **Given** I am on the Connect Screen
   **When** I click the "Connect Wallet" button
   **Then** the ConnectKit modal opens with MetaMask as an option

4. **Given** the ConnectKit modal is open
   **When** I select MetaMask
   **Then** the MetaMask popup appears requesting connection approval

5. **Given** I have approved the MetaMask connection
   **When** the wallet connection succeeds
   **Then** my wallet address is displayed (abbreviated: 0x1234...abcd)

6. **Given** the Connect Screen
   **When** viewed on a mobile viewport
   **Then** the layout is responsive and fully functional

*FRs addressed: FR18, FR19, FR23*

## Tasks / Subtasks

- [x] Task 1: Enhance ConnectPage UI with branding and trust copy (AC: #1, #2)
  - [x] 1.1 Redesign ConnectPage.tsx with improved layout, branding, and visual hierarchy
  - [x] 1.2 Add trust-building copy section with icon/shield visual element
  - [x] 1.3 Add brief feature description (what kitkat-001 does)
  - [x] 1.4 Style with Tailwind for dark theme consistency (bg-gray-950 base)

- [x] Task 2: Implement ConnectKitButton.Custom for wallet UI (AC: #2, #3, #4, #5)
  - [x] 2.1 Replace plain `<ConnectKitButton />` with `<ConnectKitButton.Custom>` render prop pattern
  - [x] 2.2 Show "Connect Wallet" button when disconnected (styled with Tailwind)
  - [x] 2.3 Show abbreviated wallet address when connected (use `truncatedAddress` from render props)
  - [x] 2.4 Add connecting/loading state indicator
  - [x] 2.5 Ensure `show()` from render props opens the ConnectKit modal correctly

- [x] Task 3: Mobile responsive layout (AC: #6)
  - [x] 3.1 Ensure flex layout works on mobile viewports (min-width handling)
  - [x] 3.2 Test padding/spacing for small screens (px-4 minimum)
  - [x] 3.3 Ensure ConnectKit modal works on mobile (ConnectKit handles this internally)

- [x] Task 4: Write tests for ConnectPage (AC: #1, #2, #5)
  - [x] 4.1 Test: renders branding, description, and trust copy
  - [x] 4.2 Test: renders Connect Wallet button when not connected
  - [x] 4.3 Test: shows wallet address when connected
  - [x] 4.4 Test: ConnectKit button `show()` is called on click

## Dev Notes

### CRITICAL: Scope Boundary

This story is UI-only. It builds the Connect Screen visuals and wallet connection button. The actual auth flow (challenge/sign/verify/session) is Story 6.3. After wallet connects via ConnectKit in this story, the user sees their address displayed. The automatic auth handshake happens in the NEXT story.

### Current ConnectPage.tsx (What Exists)

```tsx
// frontend/src/pages/ConnectPage.tsx - CURRENT STATE
import { ConnectKitButton } from 'connectkit'

export default function ConnectPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 text-white">
      <div className="mx-auto max-w-md text-center">
        <h1 className="mb-2 text-4xl font-bold">kitkat-001</h1>
        <p className="mb-8 text-gray-400">TradingView to DEX signal execution</p>
        <ConnectKitButton />
        <p className="mt-6 text-sm text-gray-500">
          Signs a message to verify ownership — no fund access granted
        </p>
      </div>
    </div>
  )
}
```

### ConnectKitButton.Custom Pattern (USE THIS)

The `ConnectKitButton.Custom` render prop provides:

```tsx
import { ConnectKitButton } from 'connectkit'

<ConnectKitButton.Custom>
  {({
    isConnected,        // boolean
    isConnecting,       // boolean
    show,               // () => void - opens ConnectKit modal
    hide,               // () => void - closes modal
    address,            // `0x${string}` | undefined - full address
    truncatedAddress,   // string | undefined - e.g. "0x1234...abcd"
    ensName,            // string | undefined
    chain,              // Chain object | undefined
  }) => (
    <button onClick={show}>
      {isConnected ? truncatedAddress : 'Connect Wallet'}
    </button>
  )}
</ConnectKitButton.Custom>
```

**Key:** Use `truncatedAddress` directly from render props. Do NOT write your own address truncation utility. ConnectKit already formats it as `0x1234...abcd`.

### wagmi v3 Notes (Installed: wagmi 3.4.2)

This project has wagmi v3 (NOT v2). Key differences:
- `useAccount` is **deprecated** - prefer `useConnection` from `wagmi`
- `connect()` / `signMessageAsync()` are deprecated on mutation hooks - prefer `mutate` / `mutateAsync`
- However, ConnectKit 1.9.1 internally uses the deprecated aliases (they still work)

For this story, you likely do NOT need wagmi hooks directly since ConnectKitButton.Custom handles all connection state. Only use `useConnection` if you need wallet state outside the ConnectKitButton render prop.

### Tailwind Styling Conventions (from Story 6.1)

- Dark theme: `bg-gray-950` base background, `text-white` primary text
- Muted text: `text-gray-400` descriptions, `text-gray-500` fine print
- Max width container: `max-w-md` centered with `mx-auto`
- Tailwind CSS v4 - no tailwind.config.js, uses `@import "tailwindcss"` in CSS
- No custom color tokens defined yet - stick to standard Tailwind gray palette

### File Structure (DO NOT create new directories)

```
frontend/src/
├── pages/
│   └── ConnectPage.tsx      ← MODIFY THIS (main work)
├── components/
│   └── AuthGate.tsx         ← DO NOT MODIFY
├── hooks/
│   └── useAuth.ts           ← DO NOT MODIFY
└── lib/
    └── wagmi.ts             ← DO NOT MODIFY
```

### What NOT To Do

- Do NOT implement the auth flow (challenge/sign/verify) - that's Story 6.3
- Do NOT add react-router-dom - use simple conditional rendering (existing pattern)
- Do NOT modify AuthGate.tsx, useAuth.ts, or wagmi.ts
- Do NOT install new npm packages - everything needed is already installed
- Do NOT use `useAccount` - use `useConnection` (wagmi v3 correct name)
- Do NOT create a custom address truncation function - use ConnectKitButton.Custom's `truncatedAddress`
- Do NOT add wallet disconnect logic to ConnectPage - user disconnects from Dashboard (existing)
- Do NOT add excessive animations or transitions - keep it lean MVP

### Backend API Reference (For Context Only - Not Used in This Story)

The backend wallet endpoints exist and are fully implemented. Story 6.3 will integrate with them:
- `GET /api/wallet/challenge?wallet_address={addr}` → `{message, nonce, expires_at, explanation}`
- `POST /api/wallet/verify` body: `{wallet_address, signature, nonce}` → `{token, expires_at, wallet_address}`

### Testing Approach

Use Vitest + Testing Library (already configured in Story 6.1):
- Test file: `frontend/src/pages/ConnectPage.test.tsx`
- Mock ConnectKit: `vi.mock('connectkit', ...)` to control render prop values
- Test structure: render component, assert DOM elements exist
- No need to test ConnectKit internals (modal opening, MetaMask interaction) - that's ConnectKit's responsibility

Example mock pattern:
```tsx
vi.mock('connectkit', () => ({
  ConnectKitButton: {
    Custom: ({ children }: { children: (props: any) => React.ReactNode }) =>
      children({
        isConnected: false,
        isConnecting: false,
        show: vi.fn(),
        address: undefined,
        truncatedAddress: undefined,
      }),
  },
}))
```

### Previous Story Intelligence (Story 6.1)

**Key learnings from Story 6.1:**
- ConnectKit requires `ResizeObserver` polyfill in test setup (already in `frontend/src/test/setup.ts`)
- ConnectKit peer dep conflict with React 19 was resolved using `--legacy-peer-deps` during install
- wagmi installed as v3.4.2 (not v2 as originally planned - ConnectKit 1.9.x is compatible)
- `events` package was added as polyfill for ConnectKit dependency
- TOKEN_KEY constant lives in `frontend/src/lib/constants.ts` = `'kitkat_token'`
- All existing tests pass (11 tests across 3 files)
- Vitest configured with jsdom environment in vite.config.ts

**Code review feedback from 6.1:**
- M2 fix: apiClient only sets Content-Type when body is present (already fixed)
- L1 note: SettingsPage not routable from AuthGate yet (expected, wired in Epic 8)

### Git Commit Pattern

```
Story 6.2: Connect Screen & Wallet Connection UI - Implementation Complete
```

### Project Structure Notes

- Frontend at `frontend/` (separate from Python backend at `src/kitkat/`)
- Frontend dev server: `npm run dev` on localhost:5173
- Backend: `uvicorn kitkat.main:app --reload` on localhost:8000
- CORS already configured for localhost:5173

### References

- [Source: _bmad-output/planning-artifacts/epics-frontend.md#Story 1.2] - Story acceptance criteria
- [Source: _bmad-output/planning-artifacts/epics-frontend.md#Overview] - Frontend stack, UX direction
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication & Security] - Auth patterns
- [Source: _bmad-output/implementation-artifacts/6-1-frontend-project-setup-app-shell.md] - Previous story context
- [Source: frontend/src/pages/ConnectPage.tsx] - Current ConnectPage implementation
- [Source: frontend/src/components/AuthGate.tsx] - Auth routing gate
- [Source: frontend/src/hooks/useAuth.ts] - Auth state hook
- [Source: frontend/src/lib/wagmi.ts] - wagmi configuration
- [Source: src/kitkat/api/wallet.py] - Backend wallet API (context for Story 6.3)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- No blocking issues encountered during implementation

### Completion Notes List

- Replaced basic `<ConnectKitButton />` with `<ConnectKitButton.Custom>` render prop pattern for full UI control
- Enhanced ConnectPage with improved visual hierarchy: branding heading, description, feature explanation, custom wallet button, and trust copy with lock icon
- Button states: "Connect Wallet" (disconnected), "Connecting..." (disabled during connection), truncated address (connected)
- Added lock SVG icon next to trust-building copy for visual confidence
- Mobile responsive with `px-4` padding, `w-full` button, and flexible layout
- 7 new tests covering: branding/description/trust copy rendering, Connect Wallet button rendering, connected wallet address display, show() click handler, and connecting loading state
- All 19 tests pass (7 new + 12 existing) with zero regressions
- No new dependencies installed; no files modified outside permitted scope

### Change Log

- 2026-02-09: Story 6.2 implementation complete — ConnectPage UI enhanced with ConnectKitButton.Custom, trust copy, branding, responsive layout, and comprehensive tests
- 2026-02-09: Code review fixes (3 MEDIUM) — Connected button visual differentiation, trust copy test robustness, mock hygiene cleanup

## Senior Developer Review (AI)

**Review Date:** 2026-02-09
**Reviewer Model:** Claude Opus 4.6
**Review Outcome:** Approve (with fixes applied)

### Findings Summary

- **0 High** | **3 Medium** (all fixed) | **2 Low** (deferred)

### Action Items

- [x] [M1] Connected state button uses same CTA style as disconnected — differentiate with outline/muted style [ConnectPage.tsx:19-21]
- [x] [M2] Trust copy test uses two separate regex assertions that could independently pass on split elements — use single combined regex [ConnectPage.test.tsx:45-51]
- [x] [M3] `hide` mock not reset in beforeEach alongside `mockShow` — add mockHide.mockClear() [ConnectPage.test.tsx:7,31]
- [ ] [L1] Inline SVG lock icon (10 lines) could be extracted for reuse in future stories [ConnectPage.tsx:34-49]
- [ ] [L2] `React.ReactNode` type reference used without explicit React import in test mock [ConnectPage.test.tsx:22]

### File List

- frontend/src/pages/ConnectPage.tsx (modified)
- frontend/src/pages/ConnectPage.test.tsx (new)
