---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
userProvidedContext: |
  Auto market making bot that runs with user strategies in TradingView.
  - Exposes webhook to receive TradingView signals
  - Integrates with perp DEXs to create long/short positions based on signals
  - Target DEXs: Hyperliquid, Lighter, Extended, Paradex, Variational
date: 2026-01-17
author: vitr
---

# Product Brief: kitkat-001

## Executive Summary

kitkat-001 is a TradingView-to-Perp DEX signal execution bot enabling solo traders to hit airdrop volume thresholds across multiple perpetual decentralized exchanges simultaneously while executing their proven TradingView strategies automatically.

The system receives custom Pine Script webhook alerts and executes long/short positions across Hyperliquid, Lighter, Extended, Paradex, and Variational - targeting 500k+ daily volume per DEX for airdrop eligibility. No existing tool bridges TradingView signals to perp DEXs, making this a first-mover opportunity in the airdrop farming space.

---

## Core Vision

### Problem Statement

Solo traders running strategies on TradingView cannot directly execute trades on perpetual DEXs. Each DEX has its own API, authentication mechanism, and rate limits - forcing traders to manually place orders across multiple platforms when alerts fire. This manual process is slow, error-prone, and makes it nearly impossible to farm meaningful volume across multiple DEXs simultaneously for airdrop qualification.

### Problem Impact

- **Missed airdrop eligibility**: Cannot realistically hit 500k+ daily volume per DEX manually across 5 platforms
- **Execution delays**: Manual order placement causes slippage and missed entries
- **API fragmentation**: Managing authentication, rate limits, and different API formats is complex
- **No unified tooling**: Traders must build custom integrations for each DEX individually

### Why Existing Solutions Fall Short

No existing tool bridges TradingView signals to perp DEXs. The market gap exists because:
- Each DEX has unique API patterns, auth flows, and order formats
- Maintaining reliable integrations across multiple DEXs requires significant engineering
- The airdrop farming use case is niche but high-value
- Current options require building and maintaining separate integrations per platform

### Proposed Solution

A webhook-based execution engine that:
1. Exposes a single endpoint to receive TradingView custom Pine Script alerts
2. Parses signal payload (long/short, entry/exit)
3. Simultaneously executes across all configured perp DEXs
4. Tracks open positions per DEX for accurate entry/exit execution
5. Handles errors gracefully - alerts on failure, continues on others
6. Supports user-configurable position sizing

### Key Differentiators

| Differentiator | Value |
|----------------|-------|
| **Unified DEX Adapter Architecture** | Abstracts 5 different APIs behind single interface - the technical moat |
| **Multi-DEX Simultaneous Execution** | One signal triggers trades across all DEXs instantly |
| **Airdrop-Optimized Design** | Built specifically for volume farming use case (500k+/day/DEX) |
| **Position Awareness** | Tracks open positions to execute entries/exits correctly |
| **Resilient Execution** | Failures on one DEX don't block others; clear alerting on issues |
| **First-Mover Advantage** | No existing tools in this space |

---

## Target Users

### Primary Users

**Persona: "Alex the Airdrop Farmer"**

| Attribute | Details |
|-----------|---------|
| **Background** | Crypto-native trader, treating trading as a side hustle alongside main income |
| **Technical Skills** | Low to none - needs plug-and-play solution, cannot code |
| **Trading Style** | Runs one proven TradingView Pine Script strategy |
| **Goal** | Farm volume across multiple perp DEXs to qualify for airdrops |
| **Capital** | Varies - configures position size (e.g., 0.1 ETH to 1 ETH per trade) |
| **Time Commitment** | Part-time, user-defined operating hours (not 24/7) |

**User Sub-Segments (MVP Focus: Segment 1):**

| Segment | Description | Needs |
|---------|-------------|-------|
| **Experienced Farmers** (MVP target) | Already familiar with perp DEXs and airdrop mechanics | Speed - "just give me the webhook URL" |
| **Aspiring Farmers** (Future) | Know TradingView, new to perp DEX airdrop farming | Hand-holding through DEX setup |

**Problem Experience:**
- Has a working TradingView strategy but cannot execute automatically on perp DEXs
- Manually placing orders across 5 DEXs is impossible while holding a day job
- Missing airdrop volume thresholds due to execution limitations
- Frustrated by fragmented DEX interfaces and different setup requirements

**Trust Requirement:**
- Must trust kitkat-001 with delegated trading authority via wallet signature
- Understands signature requests grant execution permissions (not transactions)
- Comfortable with non-custodial wallet setup (MetaMask, Rabby, etc.)

**Success Vision:**
- Set it and forget it within their defined trading hours
- Hit 500k+ volume per DEX without manual intervention
- Track volume accumulation and optionally monitor PnL
- Qualify for multiple DEX airdrops simultaneously

### Secondary Users

N/A - Single-user system with no admin, team, or oversight roles required.

### User Journey

| Stage | Experience |
|-------|------------|
| **Discovery** | Finds kitkat-001 through crypto Twitter, Discord, or airdrop farming communities |
| **Prerequisites** | Already has: (1) TradingView Pro with Pine Script strategy, (2) Funded accounts on target DEXs, (3) Non-custodial wallet |
| **Onboarding** | 1. Connect wallet<br>2. Approve signature for each DEX (delegated trading authority)<br>3. Configure position size per DEX<br>4. Set operating hours schedule<br>5. Copy webhook URL and payload format to TradingView alert<br>6. **Run test/dry-run to validate setup before going live** |
| **Webhook Format** | Provided payload template:<br>`{"symbol":"{{ticker}}","side":"{{strategy.order.action}}","positionSide":"BOTH","investmentType":"coin_qty","qty":"1","price":"market","reduceOnly":false,"positionMode":"one_way_mode","signalId":"...","uid":"..."}` |
| **Core Usage** | TradingView fires alert → kitkat-001 receives webhook → executes simultaneously across all configured DEXs |
| **Aha Moment** | First successful multi-DEX execution from their own strategy - "it actually works!" |
| **Ongoing Value** | Volume stats accumulating toward airdrop thresholds, optional PnL tracking |
| **Trust Model** | User grants delegated trading authority via wallet signatures; no private keys stored |

---

## Success Metrics

### User Success Metrics

| Metric | Target | Definition |
|--------|--------|------------|
| **Execution Success Rate** | ≥99% per DEX | Order successfully submitted to DEX API (tracked per-DEX separately) |
| **Signal-to-Execution Latency** | <1 second | Time from webhook receipt to order submitted to DEX API |
| **Volume Accumulation** | Tracked per DEX | Daily/weekly/monthly volume dashboard per DEX |
| **Position Accuracy** | 100% | Positions correctly tracked across all DEXs |

**Success Definition Clarity:**
- "Successful execution" = Order submitted to DEX API and acknowledged
- Partial fills count as success (fill rate is a separate metric)
- Per-DEX tracking: If 4/5 DEXs succeed, that's 80% for that signal, not a system failure

**User "Win" Indicators:**
- First successful multi-DEX execution within onboarding session
- Consistent daily volume accumulation toward airdrop thresholds
- Zero unexpected position states (no orphaned or mismatched positions)

### Business Objectives

| Timeframe | Objective |
|-----------|-----------|
| **3 months** | 10 active users |
| **Ongoing** | Sustainable revenue through fee model |

**Revenue Model:**
- 2 bps (0.02%) per trading volume executed
- Example: 500k volume/day/DEX × 5 DEXs = $2.5M volume = **$500/day per user**
- 10 users at full utilization = **$5,000/day potential revenue**

### Key Performance Indicators

| KPI | Target | Priority | Acceptance Criteria |
|-----|--------|----------|---------------------|
| **Execution Success Rate** | ≥99% per DEX | Critical | 99 of 100 consecutive signals execute successfully per DEX |
| **Latency** | <1 second | Critical | Order submission completes within 1000ms of webhook receipt |
| **System Uptime** | 99.9% | Critical | Our infrastructure responds to health checks 99.9% of intervals |
| **DEX Recovery Time** | <30 seconds | Critical | Failed DEX connection re-established within 30s |
| **Concurrent User Capacity** | 10 users | Launch | System supports 10 concurrent users from day one |
| **Avg Volume per User per DEX** | Track (leading indicator) | Growth | Primary revenue predictor |
| **Active Users (3 month)** | 10 | Growth | Business goal, not dev responsibility |

### Operational Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| **System Uptime** | 99.9% (~8.7 hours downtime/year) | Our infrastructure only |
| **DEX Availability** | Monitored separately | Not our SLA - external dependency |
| **Error Alerting** | Real-time | Notification on any failed execution |
| **DEX API Health** | Continuous monitoring | Track connectivity to all 5 DEXs |
| **Observability** | Dashboard from day one | Can't improve what you can't measure |

---

## MVP Scope

### Core Features (Tiered Priority)

**Tier 1: Must Ship (Week 1-4)**

| Feature | Description |
|---------|-------------|
| **Webhook Endpoint** | Receive TradingView custom Pine Script alerts |
| **Extended DEX Integration** | Full trading API integration - FIRST PRIORITY |
| **Wallet Signature Auth** | Delegated trading authority via wallet signatures |
| **Order Execution** | Submit long/short orders from signal |
| **Error Alerting** | Real-time notification on failed executions (Telegram/Discord) |
| **Test/Dry-Run Mode** | Validate setup before going live with real capital |

**Tier 2: Should Ship (Week 5-6)**

| Feature | Description |
|---------|-------------|
| **Paradex DEX Integration** | Second DEX - proves adapter pattern works |
| **Position Tracking** | Track positions we submitted (not full DEX sync) |
| **Volume Tracking per DEX** | Daily/weekly/monthly volume per DEX |

**Tier 3: Could Ship (Week 7-8)**

| Feature | Description |
|---------|-------------|
| **Operating Hours** | Simple on/off toggle (full scheduler is V2) |
| **PnL Tracking** | Track PnL from our trades only (ignore funding rates) |
| **Simple Config Page** | Basic UI; could be config file initially |

### Build Order

| Phase | Focus | Outcome |
|-------|-------|---------|
| **Phase 1** | Extended end-to-end | One DEX working reliably |
| **Phase 2** | Paradex integration | Adapter pattern proven |
| **Phase 3** | Polish & tracking | Volume, PnL, config UI |

**Principle:** One DEX working reliably > two DEXs working poorly.

### Out of Scope for MVP

| Feature | Reason | Target |
|---------|--------|--------|
| **Hyperliquid Integration** | Already airdropped | V2 |
| **Lighter Integration** | Already airdropped | V2 |
| **Variational Integration** | No API support | Not feasible |
| **Full Dashboard with Charts** | Polish, not essential | V2 |
| **Multiple Strategies per User** | Complexity | V2+ |
| **Full DEX State Sync** | Complex; just track our submissions | V2 |
| **Funding Rate Tracking** | PnL complexity; simplify for MVP | V2 |
| **Advanced Scheduling** | Simple on/off toggle sufficient for MVP | V2 |

### MVP Success Criteria

**Platform Metrics (What We Control):**

| Criteria | Target |
|----------|--------|
| **Execution Success Rate** | ≥99% per DEX |
| **Latency** | <1 second (signal to order submission) |
| **System Uptime** | 99.9% |
| **DEX Recovery** | <30 seconds reconnection |
| **Concurrent Users** | Support 10 users |

**User-Controlled (Not Our SLA):**
- Volume achieved depends on user's strategy frequency
- Position sizing configured by user
- Strategy performance is user's responsibility

**Go/No-Go Decision:**
- Extended achieves ≥99% execution success → add Paradex
- Both DEXs stable → proceed to V2 (Hyperliquid, Lighter, full dashboard)

### Future Vision

**V2:**
- Hyperliquid + Lighter integrations
- Full dashboard with volume/PnL charts
- Advanced operating hours scheduler
- Full DEX state sync + funding rate tracking

**V3+:**
- Additional DEX integrations as APIs available
- Multi-strategy support
- Mobile monitoring app
- White-label for trading communities
