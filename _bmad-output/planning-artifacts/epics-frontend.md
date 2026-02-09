---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: complete
validated: '2026-02-09'
total_epics: 3
total_stories: 11
fr_coverage: 26/26
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
workflowType: 'epics-and-stories'
project_name: 'kitkat-001'
scope: 'frontend-ui'
user_name: 'vitr'
date: '2026-02-09'
---

# kitkat-001 Frontend UI - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the kitkat-001 **frontend UI**, decomposing the frontend-relevant requirements from the PRD and Architecture into implementable stories. The backend API is fully implemented; these epics cover building the React SPA that consumes it.

**Frontend Stack:** Vite + React + TypeScript + wagmi v2 + viem + ConnectKit + TanStack Query + Tailwind CSS

**UX Direction:** 3 views (Connect, Dashboard, Settings) - lean MVP, mobile-friendly

## Requirements Inventory

### Functional Requirements

**User Authentication & Wallet (FR18-FR25):**
- FR18: User can create account by connecting wallet
- FR19: User can connect wallet (MetaMask) to kitkat-001
- FR20: User can sign delegation authority message for Extended DEX
- FR21: System can verify wallet signature matches expected wallet
- FR22: User can disconnect wallet and revoke delegation
- FR23: System can display clear explanation of what signature grants
- FR24: System can maintain user session after authentication
- FR25: System can generate unique webhook URL per user

**System Monitoring (FR26, FR30):**
- FR26: System can display health status per DEX (healthy/degraded/offline)
- FR30: User can view error log entries (last 50 entries or last 24 hours)

**Dashboard & Status (FR31-FR33):**
- FR31: User can view dashboard with system status and stats
- FR32: System can display "everything OK" indicator when all DEXs healthy and no recent errors
- FR33: System can display onboarding checklist with completion status

**Volume & Statistics (FR34-FR38):**
- FR34: System can track total volume executed per DEX
- FR35: System can display today's volume total
- FR36: System can display this week's volume total
- FR37: System can display execution count (signals processed)
- FR38: System can display success rate percentage

**Test Mode (FR39, FR41, FR43):**
- FR39: User can enable test/dry-run mode
- FR41: System can display "would have executed" details in test mode
- FR43: User can disable test mode to go live

**Configuration (FR44-FR48):**
- FR44: User can configure position size per trade
- FR45: User can configure maximum position size limit
- FR46: User can view their unique webhook URL
- FR47: User can view expected webhook payload format
- FR48: User can configure Telegram alert destination

### NonFunctional Requirements

- NFR2: Dashboard page load time < 2 seconds
- NFR6: All API traffic encrypted (HTTPS/TLS 1.2+)
- NFR9: Session token expiration 24 hours max, refresh on activity

### Additional Requirements

**From Architecture:**
- CORS middleware must be added to FastAPI for Vite dev server (localhost:5173)
- Production deployment: FastAPI serves built Vite output as static files (single deployment unit)
- API contracts defined via Pydantic models - frontend TypeScript types should mirror these
- Bearer token authentication for all authenticated API calls
- Wallet auth flow: GET /api/wallet/challenge → sign message → POST /api/wallet/verify → Bearer token

**From Party Mode UX Discussion:**
- 3 views: Connect Screen (unauthenticated), Dashboard (authenticated), Settings (authenticated)
- Mobile-friendly responsive design
- "Glance and go" dashboard UX - Alex's 30-second check-in experience
- Trust-building copy before wallet signature requests - Marco's nervousness about signing
- Onboarding progress indicator consuming GET /api/onboarding (5-step checklist)
- Test mode toggle visible on dashboard
- Webhook URL with copy-to-clipboard in settings
- Payload format reference in settings

**Backend API Endpoints Available:**
- GET /api/wallet/challenge - Generate signature challenge
- POST /api/wallet/verify - Verify signature, create session
- POST /api/wallet/disconnect - End session
- POST /api/wallet/revoke - Revoke all sessions
- GET /api/auth/user/status - Authenticated user status
- GET /api/health - System health (public)
- GET /api/dashboard - Aggregated dashboard data (auth)
- GET /api/onboarding - Onboarding checklist (auth)
- GET /api/stats/volume - Volume stats (auth)
- GET /api/stats/executions - Execution stats (auth)
- GET /api/config - Position size config (auth)
- PUT /api/config - Update position size (auth)
- GET /api/config/webhook - Webhook URL and instructions (auth)
- GET /api/config/telegram - Telegram config status (auth)
- PUT /api/config/telegram - Configure Telegram (auth)
- GET /api/errors - Error log entries (auth)
- GET /api/executions - Execution history (public)

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR18 | Epic 1 | User can create account by connecting wallet |
| FR19 | Epic 1 | User can connect wallet (MetaMask) |
| FR20 | Epic 1 | User can sign delegation authority message |
| FR21 | Epic 1 | System can verify wallet signature |
| FR23 | Epic 1 | System can display explanation of what signature grants |
| FR24 | Epic 1 | System can maintain user session after authentication |
| FR26 | Epic 2 | Display health status per DEX |
| FR31 | Epic 2 | User can view dashboard with status and stats |
| FR32 | Epic 2 | Display "everything OK" indicator |
| FR33 | Epic 2 | Display onboarding checklist |
| FR34 | Epic 2 | Track total volume per DEX (display) |
| FR35 | Epic 2 | Display today's volume total |
| FR36 | Epic 2 | Display this week's volume total |
| FR37 | Epic 2 | Display execution count |
| FR38 | Epic 2 | Display success rate percentage |
| FR22 | Epic 3 | User can disconnect wallet and revoke delegation |
| FR25 | Epic 3 | Display unique webhook URL per user |
| FR30 | Epic 3 | User can view error log entries |
| FR39 | Epic 3 | User can enable test/dry-run mode |
| FR41 | Epic 3 | Display "would have executed" details in test mode |
| FR43 | Epic 3 | User can disable test mode |
| FR44 | Epic 3 | User can configure position size |
| FR45 | Epic 3 | User can configure max position size limit |
| FR46 | Epic 3 | User can view webhook URL |
| FR47 | Epic 3 | User can view webhook payload format |
| FR48 | Epic 3 | User can configure Telegram alert destination |

**Coverage: 26/26 FRs mapped (100%)**

## Epic List

### Epic 1: Wallet Connection & Authentication (Connect Screen)
User can visit kitkat-001, connect their MetaMask wallet, understand what they're signing, complete the delegation signature, and be authenticated into the application.
**FRs covered:** FR18, FR19, FR20, FR21, FR23, FR24

### Epic 2: Dashboard & System Status (Daily Driver)
User can see the full status of their kitkat-001 system at a glance - DEX health, volume accumulated, execution stats, and onboarding progress - in under 30 seconds.
**FRs covered:** FR26, FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR38

### Epic 3: Settings, Configuration & Account Management
User can configure trading parameters, access webhook setup instructions for TradingView, manage Telegram alerts, toggle test mode for safe validation, review error history, and manage their account.
**FRs covered:** FR22, FR25, FR30, FR39, FR41, FR43, FR44, FR45, FR46, FR47, FR48

---

## Epic 1: Wallet Connection & Authentication (Connect Screen)

User can visit kitkat-001, connect their MetaMask wallet, understand what they're signing, complete the delegation signature, and be authenticated into the application.

### Story 1.1: Frontend Project Setup & App Shell

As a **developer**,
I want **the frontend project initialized with Vite, React, TypeScript, Tailwind CSS, wagmi, ConnectKit, and TanStack Query, with CORS enabled on the backend**,
So that **I have a working development environment to build the kitkat-001 UI**.

**Acceptance Criteria:**

**Given** the kitkat-001 repository exists with a working FastAPI backend
**When** a developer runs the frontend dev server
**Then** a Vite + React + TypeScript application starts on localhost:5173
**And** Tailwind CSS is configured and functional
**And** wagmi v2 + viem + ConnectKit are installed and configured with provider wrappers in main.tsx
**And** TanStack Query is configured with QueryClientProvider
**And** CORS middleware is added to FastAPI allowing localhost:5173 in development
**And** a basic App shell renders with placeholder routing (unauthenticated → Connect, authenticated → Dashboard)
**And** the project structure follows: `frontend/src/{components,hooks,api,lib}/`

### Story 1.2: Connect Screen & Wallet Connection UI

As a **user**,
I want **to see a Connect Screen with a wallet connect button and clear explanations of what connecting does**,
So that **I feel confident connecting my MetaMask wallet to kitkat-001**.

**Acceptance Criteria:**

**Given** I am not authenticated
**When** I visit the kitkat-001 application
**Then** I see a Connect Screen with the kitkat-001 branding and a brief description
**And** I see a "Connect Wallet" button powered by ConnectKit
**And** I see trust-building copy explaining: "Signs a message to verify ownership - no fund access granted"
**And** clicking the button opens the ConnectKit modal with MetaMask as an option
**And** after selecting MetaMask, the MetaMask popup appears requesting connection approval
**And** upon successful wallet connection, the wallet address is displayed (abbreviated: 0x1234...abcd)
**And** the Connect Screen is responsive and works on mobile viewports

*FRs addressed: FR18, FR19, FR23*

### Story 1.3: Wallet Signature Auth Flow & Session Management

As a **user**,
I want **to sign a delegation message and be automatically authenticated into kitkat-001**,
So that **I can access the dashboard and manage my trading configuration**.

**Acceptance Criteria:**

**Given** I have connected my MetaMask wallet on the Connect Screen
**When** the wallet connection succeeds
**Then** the frontend calls `GET /api/wallet/challenge?wallet_address={address}` to get a challenge message
**And** the challenge message is displayed briefly explaining what the signature grants (delegation authority, not fund access)
**And** MetaMask opens a signature request with the challenge message
**And** upon signing, the frontend sends the signature to `POST /api/wallet/verify`
**And** upon successful verification, the Bearer token is stored in localStorage
**And** the app automatically navigates to the Dashboard view (auth gate)
**And** if the user rejects the MetaMask signature, a clear message is shown: "Signature rejected - you can try again anytime"
**And** if the token expires (401 response), the user is redirected to the Connect Screen
**And** on subsequent visits, if a valid token exists in localStorage, the user is auto-routed to Dashboard

*FRs addressed: FR20, FR21, FR23, FR24*

---

## Epic 2: Dashboard & System Status (Daily Driver)

User can see the full status of their kitkat-001 system at a glance - DEX health, volume accumulated, execution stats, and onboarding progress - in under 30 seconds.

### Story 2.1: Dashboard Layout & System Health Status

As a **user**,
I want **to see a dashboard with DEX health status indicators and an overall system status**,
So that **I can instantly tell if kitkat-001 is running correctly**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Dashboard view
**When** the dashboard loads
**Then** it fetches data from `GET /api/dashboard` using TanStack Query
**And** I see a header bar with "kitkat-001" branding and a test mode badge if test mode is active
**And** I see a health status indicator per DEX showing one of: healthy (green), degraded (yellow), or offline (red)
**And** when all DEXs are healthy and no recent errors exist, I see an "Everything OK" indicator
**And** the dashboard page loads in under 2 seconds (NFR2)
**And** data auto-refreshes on a polling interval (every 30 seconds)
**And** the layout is responsive and works on mobile viewports
**And** a navigation element provides access to Settings

*FRs addressed: FR26, FR31, FR32*

### Story 2.2: Volume Stats & Execution Metrics

As a **user**,
I want **to see my trading volume and execution statistics on the dashboard**,
So that **I can track my progress toward airdrop volume targets**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Dashboard view
**When** the dashboard loads
**Then** I see today's total volume displayed prominently (formatted as USD, e.g., "$31k")
**And** I see this week's total volume displayed
**And** volume is broken down per DEX when multiple DEXs are active
**And** I see the total execution count (signals processed today)
**And** I see the success rate as a percentage (e.g., "100%")
**And** stats are fetched from `GET /api/stats/volume` and `GET /api/stats/executions`
**And** if no executions exist yet, the stats section shows zeros with no error state

*FRs addressed: FR34, FR35, FR36, FR37, FR38*

### Story 2.3: Onboarding Progress & Recent Errors

As a **user**,
I want **to see my onboarding progress and any recent errors on the dashboard**,
So that **I know what setup steps remain and whether any issues need attention**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Dashboard view
**When** the dashboard loads
**Then** I see an onboarding progress indicator showing completion status (e.g., "4/5" with a progress bar)
**And** each onboarding step is listed with its completion state (wallet connected, DEX authorized, webhook configured, test signal sent, first live trade)
**And** incomplete steps are visually distinct and hint at what action is needed
**And** when all 5 steps are complete, the onboarding section collapses or shows a completion message
**And** I see a recent errors summary section
**And** if no recent errors exist, it shows "No recent errors" with a checkmark
**And** if errors exist, the most recent 3 are displayed with timestamp, error type, and DEX
**And** onboarding data is fetched from `GET /api/onboarding`

*FRs addressed: FR33*

---

## Epic 3: Settings, Configuration & Account Management

User can configure trading parameters, access webhook setup instructions for TradingView, manage Telegram alerts, toggle test mode for safe validation, review error history, and manage their account.

### Story 3.1: Settings Layout & Position Size Configuration

As a **user**,
I want **to access a Settings view and configure my position size per trade**,
So that **I can control how much is traded on each signal execution**.

**Acceptance Criteria:**

**Given** I am authenticated and click the Settings navigation element from the Dashboard
**When** the Settings view loads
**Then** I see a "Settings" header with a back navigation to Dashboard
**And** I see a Position Size section with the current position size displayed (fetched from `GET /api/config`)
**And** I can edit the position size value (decimal input)
**And** I can edit the maximum position size limit (decimal input)
**And** the unit (e.g., "ETH") is displayed alongside the inputs
**And** I can save changes via `PUT /api/config` with a Save button
**And** on successful save, a success confirmation is shown
**And** validation prevents values ≤ 0 or max > 100
**And** on validation error from the API, the error message is displayed

*FRs addressed: FR44, FR45*

### Story 3.2: Webhook Setup Display

As a **user**,
I want **to see my unique webhook URL and the expected payload format**,
So that **I can configure my TradingView alerts to send signals to kitkat-001**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Settings view
**When** the Webhook section is visible
**Then** I see my unique webhook URL fetched from `GET /api/config/webhook`
**And** a "Copy" button copies the webhook URL to the clipboard
**And** a visual confirmation appears when the URL is copied (e.g., "Copied!" tooltip)
**And** I see the expected JSON payload format displayed in a code block
**And** I see TradingView setup instructions explaining how to paste the URL and payload into a TradingView alert
**And** the webhook token is partially masked for security (showing last 4 characters only)

*FRs addressed: FR25, FR46, FR47*

### Story 3.3: Telegram Alerts & Test Mode Configuration

As a **user**,
I want **to configure Telegram alerts and toggle test mode**,
So that **I receive error notifications and can safely validate my setup before going live**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Settings view
**When** the Telegram section is visible
**Then** I see the current Telegram configuration status (configured/not configured) from `GET /api/config/telegram`
**And** I can enter a Telegram chat ID and save via `PUT /api/config/telegram`
**And** setup instructions are displayed explaining how to get a chat ID from the Telegram bot
**And** on successful save, the status updates to "Configured"

**Given** I am authenticated and on the Settings view
**When** the Test Mode section is visible
**Then** I see a toggle switch showing the current test mode state
**And** I can enable test mode, which shows a confirmation: "Test mode enabled - signals will be processed but NOT executed on DEXs"
**And** I can disable test mode, which shows a confirmation: "Live mode enabled - signals WILL execute real trades"
**And** when test mode is active, recent dry-run results are displayed showing "would have executed" details (symbol, side, size, DEX) from `GET /api/executions?test_mode=true&limit=5`

*FRs addressed: FR39, FR41, FR43, FR48*

### Story 3.4: Error Log & Account Management

As a **user**,
I want **to view error logs and manage my wallet connection**,
So that **I can troubleshoot issues and control my account access**.

**Acceptance Criteria:**

**Given** I am authenticated and on the Settings view
**When** the Error Log section is visible
**Then** I see the most recent error log entries (up to 50) fetched from `GET /api/errors`
**And** each entry shows timestamp, error type, DEX, and error message
**And** if no errors exist, a "No errors recorded" message is shown
**And** I can filter errors by time range (last 24 hours, last 7 days)

**Given** I am authenticated and on the Settings view
**When** the Account section is visible
**Then** I see my connected wallet address (abbreviated)
**And** I see a "Disconnect Wallet" button
**And** clicking Disconnect shows a confirmation dialog: "This will end your current session"
**And** confirming calls `POST /api/wallet/disconnect`, clears the stored token, and redirects to the Connect Screen
**And** I see a "Revoke All Sessions" button for full revocation
**And** clicking Revoke shows a warning: "This will end ALL active sessions across all devices"
**And** confirming calls `POST /api/wallet/revoke`, clears the stored token, and redirects to the Connect Screen

*FRs addressed: FR22, FR30*

### Story 3.5: Production Build & Static File Serving

As a **user**,
I want **the kitkat-001 frontend to be served from the same deployment as the backend**,
So that **I can access the application at a single URL without separate hosting**.

**Acceptance Criteria:**

**Given** the frontend is built with `npm run build` producing output in `frontend/dist/`
**When** FastAPI starts in production
**Then** it serves the built frontend at the root path (`/`)
**And** API routes (`/api/*`) continue to work normally
**And** client-side routing works (refreshing on `/dashboard` or `/settings` serves index.html)
**And** a build script or Makefile command exists to build the frontend and prepare for deployment
**And** the Vite `base` config is set correctly for the deployment path
**And** CORS middleware is conditional: enabled in development, unnecessary in production (same origin)
