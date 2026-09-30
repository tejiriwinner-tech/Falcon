# Project: Falcon Trading Intelligence (Phases 2 & 3)

## Architecture
Falcon is a non-custodial, institutional-grade AI trading intelligence system built on FastAPI (backend) and Flutter (mobile).
- **Perception Layer (SMC Structure Engine)**: Algorithms detecting Fair Value Gaps (15M & 1H), Order Blocks (displacement footprints), session manipulation sweeps (Asian/London/NY), and calculating a 0–100% Composite Conviction Score incorporating macro news, DXY correlation, and spreads.
- **Cognitive / Diagnostic Layer (Regime Memory & Adaptive Tuning)**: Forensic diagnostics classifying stop-outs (liquidity sweep -> +35% ATR buffer, off-peak momentum stall -> session restriction, macro release -> widen blackout window), dynamic strategy health scoring (quarantine/boost), and loss-recovery progression (1 loss = 2.0x, 2 losses = 4.0x, hard $20 max streak loss ceiling, reset on win).
- **Conversational & Delivery Layer (Co-Pilot & Briefings)**: REST API `/api/v1/copilot/query` answering trade rationale, risk, and forensic learning inquiries; automated scheduled Telegram briefings (07:00 UTC London Open and 20:00 UTC Daily Review).
- **Execution & Safety Layer (The Shield)**: Non-custodial advisory isolation with zero broker execution (`order_send = 0`, `order_modify = 0`, `order_close = 0`), read-only HTTP endpoints, and hard capital loss guards.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Order Block & FVG Detection | 15M/1H institutional displacement and 3-candle imbalance detection | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Session Liquidity Sweeps | Flag manipulation wicks sweeping Asian, London, and NY high/low levels | M1 | ORIGINAL_REQUEST §R1 |
| F3 | Composite Conviction Scoring | Fuse SMC alignment, session timing, DXY vs Gold correlation, macro news blackout, and live spreads into 0-100% score | M1 | ORIGINAL_REQUEST §R1 |
| F4 | SMC REST Endpoints | Read-only endpoints for structure, sweeps, and conviction adhering to R4 | M1 | Survey Finding |
| F5 | Root-Cause Stop-Out Diagnostics | Auto-diagnose: liquidity sweep (+35% ATR stop buffer), off-peak stall (session restriction), macro release (tighten blackout) | M2 | ORIGINAL_REQUEST §R2 |
| F6 | Dynamic Strategy Health Scoring | Quarantine underperforming strategies to paper mode (0.0x) and boost allocation to resilient (1.5x) | M2 | ORIGINAL_REQUEST §R2 |
| F7 | Loss-Recovery Progression & Ceiling | 1 loss = 2.0x, 2 losses = 4.0x target, hard $20.00 max streak loss ceiling, immediate reset on win | M2 | ORIGINAL_REQUEST §R2, §R4 |
| F8 | Continuous Diagnostics Hook | Connect trade outcome resolution to regime memory engine to record diagnostics on closed trades | M2 | Survey Finding |
| F9 | Conversational Co-Pilot Query API | `/api/v1/copilot/query` natural language endpoint with technical, session, and risk context | M3 | ORIGINAL_REQUEST §R3 |
| F10 | Scheduled Telegram Briefings | Automated 07:00 UTC London Open and 20:00 UTC Daily Review briefings via Telegram service | M3 | ORIGINAL_REQUEST §R3 |
| F11 | Advisory Safety & Non-Custodial Isolation | Strict zero broker automation (`order_send=0, order_modify=0, order_close=0`), read-only query endpoints | M4 | ORIGINAL_REQUEST §R4 |
| F12 | Full Regression Test Pass | Verify all 118 V10 unit/integration tests and resolve legacy schema import drift | M4 | ORIGINAL_REQUEST §Verification |
| F13 | Mobile Flutter Verification | Ensure Flutter test suite passes cleanly with zero errors | M4 | ORIGINAL_REQUEST §Verification |
| F14 | Clean Fly.io Deployment Readiness | Validate production health and deployment configuration for Fly.io | M4 | ORIGINAL_REQUEST §Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | SMC Perception & Conviction Enhancement | Features F1, F2, F3, F4 | none | DONE |
| M2 | Autonomous Diagnostics & Regime Memory Loop | Features F5, F6, F7, F8 | M1 | IN_PROGRESS |
| M3 | Conversational Co-Pilot & Scheduled Briefings | Features F9, F10 | M2 | PLANNED |
| M4 | Comprehensive Integration, Regression & Deployment | Features F11, F12, F13, F14 | M1, M2, M3 | PLANNED |

## Interface Contracts

### M1: SMC Perception
- `SMCStructureEngine.calculate_composite_conviction(..., macro_news_impact: Optional[str] = None, minutes_to_news: Optional[int] = None, symbol: Optional[str] = None)` -> `CompositeConvictionScore`
  - High-impact news within 15 min imposes -15 pts penalty.
  - XAUUSD with Bullish DXY imposes -10 pts inverse penalty; Bearish DXY grants +10 pts boost.
- `SMCStructureEngine.compute_session_levels(candles: List[PriceBar]) -> SessionLevels`
  - Extracts Asian (00:00-07:00 UTC), London (07:00-12:00 UTC), New York (12:00-20:00 UTC) high/low levels.
- Router: `backend/app/api/v1/smc.py`
  - `GET /api/v1/smc/structure?symbol=...&timeframe=...`
  - `GET /api/v1/smc/sweeps?symbol=...`
  - `GET /api/v1/smc/conviction?symbol=...&direction=...`

### M2: Autonomous Diagnostics & Regime Memory Loop
- `SignalOutcomeResolver.resolve_trade_outcome(trade: Trade, market_context: dict)`:
  - Invokes `RegimeMemoryEngine.diagnose_and_record(trade, market_context)`
  - Updates `trade.reasonForExit` and `trade.lessonLearned`
  - Triggers `RegimeMemoryEngine.evaluate_strategy_health(strategy_id)`
  - Coordinates with `AdaptiveRuleTuningEngine` and `CapitalGuardianService` for loss streak recovery and $20 ceiling.

### M3: Conversational Co-Pilot & Scheduled Telegram Briefings
- Router: `backend/app/api/v1/copilot.py`
  - `POST /api/v1/copilot/query`: Accepts `{"query": "..."}`, returns `{"response": "...", "intent": "...", "context": {...}}`
  - `GET /api/v1/copilot/briefings/london-open`
  - `GET /api/v1/copilot/briefings/daily-review`
- Background Cron Triggers:
  - Schedule jobs at 07:00 UTC and 20:00 UTC dispatching generated briefings via `TelegramAlertService.dispatch_raw_message()`.

### M4: Integration, Safety & Deployment
- Zero broker execution: verified with static analysis scan.
- Tests passing: all 118 unit tests + regression tests + Flutter tests (12/12).
- Fly.io health check at `https://falcon-api-tejiri.fly.dev/api/v1/health` verified.

## Code Layout
- Backend: `backend/app/core/engines/smc_structure_engine.py` (SMC algorithms)
- Backend: `backend/app/schemas/smc_structure.py` (SMC schemas)
- Backend: `backend/app/api/v1/smc.py` (SMC REST endpoints)
- Backend: `backend/app/core/analytics/regime_memory_engine.py` (Forensic diagnostics & regime memory)
- Backend: `backend/app/core/analytics/adaptive_tuning_engine.py` (Loss recovery & streak multiplier)
- Backend: `backend/app/core/services/signal_outcome_resolver.py` (Trade outcome resolution)
- Backend: `backend/app/core/services/copilot_service.py` (Co-pilot query reasoning)
- Backend: `backend/app/core/services/briefing_service.py` (London Open & Daily Review briefings)
- Backend: `backend/app/services/alerts/telegram_alert_service.py` (Telegram delivery)
- Backend: `backend/app/services/scheduler/` (Briefing scheduled triggers)
- Mobile: `mobile/lib/` and `mobile/test/` (Flutter test suites)
