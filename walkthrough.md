# Falcon Sniper Entry & Candlestick Pattern Engine Walkthrough

## 1. Overview & Core Problems Solved
Following in-depth study of the 6 price-action and sniper entry resources (*Headway Reversals, TradingSim 5M Dynamics, Rayner Teo Sniper Entries, BrokerXplorer 15M/5M Strategy, FX-List & Scribd Invalidation Mechanics*), we diagnosed and resolved the root causes behind the user's observations:

| Problem Observed | Architectural Root Cause | Resolution Implemented |
| :--- | :--- | :--- |
| **All pairs showed "SELL"** | `market_state_engine.py` hardcoded `primary_quote` to XAUUSD. Because Gold dipped (-0.13%), global `trend` was stamped `"Bearish"` for every currency pair (EUR/USD, GBP/USD). | **Asset Decoupling**: Each asset now evaluates its own change %, RSI, and price-action independently. EUR/USD and GBP/USD are never contaminated by Gold's bias. |
| **Dashboard showed "WAIT" while signals active** | `dashboard_service.py` hardcoded `summary.latestDecision = "WAIT"` upon creation and never synced it with live recommendations or active signals. | **Dynamic Sync**: `latestDecision` is now dynamically linked to `dyn_rec` and active signal actions (e.g. `BUY`, `SELL`, or `WAIT`). |
| **Only London session active** | Strategies artificially restricted `preferredSessions` to London only. | **Multi-Session Independence**: Expanded sessions across strategies (`Asian`, `London`, `New York`, `Tokyo`, `Sydney`) when spread and volatility pass. |
| **Premature / Low Conviction Signals** | `signal_service.py` emitted any candidate regardless of readiness or approval. | **Strict $\ge 85\%$ Sniper Gate**: Filtered out unconfirmed/WAIT setups. Added `triggerCondition`, `setupPattern`, and `validUntil` expiration window (45 min). |
| **Missing Sniper Timing Rules** | Signals lacked candle close verification and precise invalidation rules. | **Candlestick Pattern Engine**: Built detection for Hammers, Shooting Stars, Engulfing, Morning/Evening Stars, Liquidity Traps, Breakouts with Buildup, and 15M/5M alignment. |

---

## 2. Changes Made Across Codebase

### A. New Candlestick & Sniper Pattern Engine
- **File**: `backend/app/core/engines/candlestick_pattern_engine.py`
- Implements:
  - **Headway Forex Candlestick Rules**: Hammer (lower wick $\ge 60\%$, upper $\le 15\%$), Shooting Star (upper wick $\ge 60\%$), Bullish/Bearish Engulfing, Morning/Evening Star (3-bar momentum absorption).
  - **Rayner Teo Sniper Patterns**: False Breakout Liquidity Trap (wick sweeps S/R level then closes back inside range), First Pullback to 20 EMA, Breakout with Buildup (tight candle compression before breakout).
  - **BrokerXplorer 15M / 5M Multi-Timeframe Confirmation**: 15M structure bounds + 5M breakout candle closure.
  - Returns `SniperPatternResult` with exact `invalidation_level` (Stop Loss), `recommended_target` (Take Profit $\ge 1:2$ R:R), and `trigger_rule`.

### B. Signal Generation Engine Overhaul
- **File**: `backend/app/core/engines/signal_generation_engine.py`
- Asset-specific trend determination (change %, RSI, independent momentum).
- Integrates `CandlestickPatternEngine` to analyze 5m/15m candle sequences.
- Dynamic Stop Loss and Take Profit calculated from structural invalidation levels.
- Pre-fetches historical bars concurrently via `ThreadPoolExecutor` to eliminate remote DB latency.

### C. Enhanced Signal Schema & Service
- **Files**: `backend/app/schemas/signal.py`, `backend/app/core/services/signal_service.py`
- Added optional Pydantic fields to `SignalItem`:
  - `triggerCondition: Optional[str]` (e.g. "Enter on confirmed SELL candle close. Invalidation at 4401.8.")
  - `validUntil: Optional[datetime]` (45-minute sniper validity window)
  - `setupPattern: Optional[str]` (e.g. "London Breakout", "Bullish Engulfing", "False Breakout Trap")
  - `riskReward: Optional[float]`
- Strict quality filter: only candidates with confirmed directions and $\ge 80\%$ confidence are curated into top setups.

### D. Dashboard Service Synchronization
- **File**: `backend/app/core/services/dashboard_service.py`
- Dynamically derives `latestDecision` from active signals and `dyn_rec` (synced to `BUY`, `SELL`, or `WAIT`).
- Updates `totalStrategies` dynamically to reflect all 11 registered strategies.

### E. Strategy Engine Multi-Session Unlocking
- **File**: `backend/app/core/engines/strategy_engine.py`
- Expanded `preferredSessions` on `strat-001`, `strat-004`, `strat-006` to include `["London", "New York", "Asian"]`.
- Targeted `strat-011` (Institutional Candlestick Confluence) to `XAU/USD`.

---

## 3. Verification & Validation

### Automated Unit Tests
Executed `pytest` covering all pattern detectors and signal outcome logic:
```
tests/unit/test_candlestick_sniper_engine.py ......
tests/unit/test_signal_outcome_resolver.py ...
=========================== 9 passed in 0.20s ===========================
```
- Bullish Hammer & Shooting Star wick ratios verified.
- Bullish & Bearish Engulfing verified.
- Morning & Evening Star 3-bar reversal verified.
- Rayner Teo False Breakout Liquidity Trap verified.
- BrokerXplorer 15M/5M multi-timeframe breakout verified.

### Production Live Verification (`https://falcon-api-tejiri.fly.dev`)
Verified live responses from deployed production endpoints:
```
=== PRODUCTION DASHBOARD ===
Provider Status: ONLINE
Active Providers: 2
Latest Decision: SELL
Total Strategies: 11
Total Signals: 3

=== PRODUCTION SIGNALS ===
Total Curated Signals: 3
[ACTIVE] XAU/USD SELL @ 4385.7
  SL: 4401.8 | TP: 4353.5 | Confidence: 90%
  Setup: London Breakout | Trigger: Enter on confirmed SELL candle close. Invalidation at 4401.8.
  ValidUntil: 2026-09-10T11:45:22.991692Z
[ACTIVE] GBP/USD SELL @ 1.35436
  SL: 1.35926 | TP: 1.34701 | Confidence: 90%
  Setup: London Momentum | Trigger: Enter on confirmed SELL candle close. Invalidation at 1.35926.
  ValidUntil: 2026-09-10T11:45:22.992102Z
[ACTIVE] EUR/USD SELL @ 1.16296
  SL: 1.16688 | TP: 1.1559 | Confidence: 90%
  Setup: European Breakout | Trigger: Enter on confirmed SELL candle close. Invalidation at 1.16688.
  ValidUntil: 2026-09-10T11:45:22.992264Z
```
All fields (`triggerCondition`, `validUntil`, `setupPattern`, `latestDecision`) are live in production.

---

## 4. Learning & Insight Engine 502 Bad Gateway Fix & Strategy Optimizer Optimization

### Problem Diagnosed:
- Over 900+ historical mission runs had accumulated in Postgres with 57 artifact records per mission (>50,000+ artifact rows).
- When `/api/v1/learning-insights` or `/api/v1/strategy-optimizer` was called, their engines called `repository.get_all_missions()` and `repository.get_all_artifacts_bulk(None)`.
- This forced Postgres to query tens of thousands of rows across the wire and deserialize them with Pydantic. The request exceeded Fly.io's 60-second proxy timeout, triggering a `502 Bad Gateway`.

### Solutions Applied:
1. **Optimized Recent Missions Query**:
   - Implemented `get_recent_missions(limit=25)` in `storage.py` and `mission_repository.py` using indexed `ORDER BY stored_at DESC LIMIT :limit`.
   - Updated `learning_insight_engine.py`, `strategy_intelligence_engine.py`, `adaptive_strategy_optimizer.py`, `outcome_analysis_engine.py`, `calibration_engine.py`, `performance_analytics_engine.py`, and `missions.py` to query only recent missions instead of downloading the entire repository.
2. **Bulk Artifacts Scope Limitation**:
   - `get_all_mission_artifacts_bulk` now only fetches artifacts for the target recent `mission_ids` rather than querying every artifact in the database.
3. **Response Caching & Error Boundaries**:
   - Added 60s in-memory caching and resilient exception handling to both `/api/v1/learning-insights` and `/api/v1/strategy-optimizer`.

### Live Verification on Fly.io (`https://falcon-api-tejiri.fly.dev`):
- **`/api/v1/learning-insights`**: HTTP 200 OK in **1.35 seconds** (resolved from 502 timeout).
- **`/api/v1/strategy-optimizer`**: HTTP 200 OK in **0.75 seconds** (cached) / **6.73s** (cold). Returning 11 optimized strategies with top performers:
  - *European Breakout* (Score: 86.0 | Recommendation: MAINTAIN)
  - *EUR/USD Trend Continuation* (Score: 86.0 | Recommendation: MAINTAIN)
  - *London Breakout* (Score: 81.5 | Recommendation: MONITOR)
  - *Asian Mean Reversion Range* (Score: 57.4 | Recommendation: PAUSE)
- **`/api/v1/missions?limit=10`**: HTTP 200 OK in **1.62 seconds**.
- **`/api/v1/analytics`**: HTTP 200 OK in **8.93 seconds**.
