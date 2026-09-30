# Handoff Report: SMC Perception Surveyor (Requirement R1)

**Agent**: Explorer 1 — SMC Perception Surveyor  
**Date**: 2026-09-28  
**Handoff Type**: Hard (Task Complete)  
**Primary Deliverable**: `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_explorer_survey_1\analysis.md`

---

## 1. Observation

1. **Unit Test Execution Results**:
   - Command: `$env:PYTHONPATH="."; C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py -q`
   - Output: `28 passed, 36 warnings in 0.51s`
   - Result: All 28 tests in `backend/tests/unit/test_v10_smc_structure_engine.py` pass cleanly with zero failures and zero regressions.
   - Adjacent Test Suites Verified:
     - `test_v10_regime_memory_and_diagnostics.py`: `18 passed in 5.18s`
     - `test_v10_phase3_capital_guardian.py`: `23 passed in 1.06s`
     - `test_v10_phase4_guardian_integration.py`: `25 passed in 22.03s`
     - `test_v10_copilot_and_briefings.py`: `18 passed in 67.90s`

2. **Core Implementation Files**:
   - `backend/app/schemas/smc_structure.py` (211 lines): Defines `OrderBlock`, `OrderBlockType`, `FairValueGap`, `FairValueGapType`, `LiquiditySweep`, `SweepType`, `SessionLevels`, `CompositeConvictionScore`, `ConvictionBias`.
   - `backend/app/core/engines/smc_structure_engine.py` (618 lines): Implements:
     - Lines 52–188: `detect_order_blocks(candles, symbol, timeframe, swing_window)`
     - Lines 189–283: `detect_fair_value_gaps(candles, symbol, timeframe, pip_size)`
     - Lines 284–348: `detect_session_liquidity_sweeps(candles, session_levels, symbol)`
     - Lines 349–614: `calculate_composite_conviction(smc_blocks, fvgs, sweeps, pattern_direction, session, spread_pips, dxy_trend)`

3. **Current Function Signatures & Parameters**:
   - `calculate_composite_conviction` parameters:
     ```python
     def calculate_composite_conviction(
         self,
         smc_blocks: List[OrderBlock],
         fvgs: List[FairValueGap],
         sweeps: List[LiquiditySweep],
         pattern_direction: str,
         session: str,
         spread_pips: float,
         dxy_trend: Optional[str] = None,
     ) -> CompositeConvictionScore:
     ```
   - Notice: `macro_news_impact` and news blackout timing are NOT present in the parameter list.

4. **API Router Registration**:
   - Inspected `backend/app/api/v1/api.py` lines 40–78.
   - 0 endpoints exist under `/smc` or `/market-structure`. No router exposes `SMCStructureEngine` directly to HTTP clients.

5. **Upstream Services**:
   - Economic calendar events are collected and cached in `backend/app/core/services/economic_calendar_service.py` via `get_events(lookback_hours, lookahead_hours)`.
   - Historical OHLC price bars are stored in `backend/app/core/services/market_history_service.py` (`PriceBar` with 15m/1h intervals).
   - `briefing_service.py` lines 65–100 computes Asian session high/low for EUR/USD, GBP/USD, and XAU/USD, but this logic is private to briefings and not unified into a shared session extractor.

---

## 2. Logic Chain

1. **From Observation 1**: The existing test suite `test_v10_smc_structure_engine.py` passes 28 of 28 unit tests in 0.51s, establishing that the fundamental mathematical algorithms for Order Block displacement detection, FVG 3-bar sequence detection, manipulation wick sweeps, and 5-factor conviction scoring are working as designed without regressions.
2. **From Observation 2 & 3**: While the engine successfully fuses SMC alignment (35 pts), sniper patterns (25 pts), session timing (20 pts), DXY correlation (20 pts), and spread penalty (-25 pts), Requirement R1 explicitly specifies: *"Fuse macro calendar news impact, currency strength correlation (e.g. DXY vs. Gold XAUUSD), and live spreads fused into a single Composite Conviction Score (0–100%)"*. Because `calculate_composite_conviction` currently lacks a parameter for macro calendar news impact, high-impact news blackout windows cannot influence the score without updating the signature.
3. **From Observation 3**: Adding optional parameters `macro_news_impact: Optional[str] = None`, `minutes_to_news: Optional[int] = None`, and `symbol: Optional[str] = None` to `calculate_composite_conviction` will satisfy Requirement R1 while preserving 100% backward compatibility with all 28 existing tests.
4. **From Observation 4 & 5**: To operationalize SMC perception across the platform and make it accessible to the AI Co-Pilot (R3) and mobile interface without violating non-custodial advisory safety (R4), a dedicated read-only router (`/api/v1/smc`) and a multi-timeframe service layer (`smc_perception_service.py`) should be implemented to connect stored 15M/1H price bars from `market_history_service` to `smc_structure_engine`.

---

## 3. Caveats

- **Live Market Data Feed Connectivity**: In test and development environments, live market data feeds depend on API keys (TwelveData, AlphaVantage, FMP). Offline tests utilize cached or synthetic price bars; algorithmic verification remains valid regardless of live provider connectivity.
- **FastAPI TestClient Startup Events**: Running test files that import `main.py` directly executes startup event handlers (`market_data_scheduler`, `scheduler_service`, `learning_scheduler_service`), which can take 10-60 seconds due to background scheduler task creation. In contrast, pure engine tests (`test_v10_smc_structure_engine.py`) execute in 0.51 seconds.
- **Correlation Data Source**: DXY trend is currently provided as a categorical string (`"BULLISH"`, `"BEARISH"`, `"NEUTRAL"`). Real-time mathematical Pearson correlation against Gold XAUUSD tick data would require a streaming price buffer.

---

## 4. Conclusion

1. **Readiness Status**: Phase 1 SMC Institutional Perception is fully functional with 28/28 passing unit tests.
2. **Implementation Target for Builders**:
   - **Enhance `SMCStructureEngine.calculate_composite_conviction`**: Add optional macro news impact and news blackout window penalties (-15 pts for imminent high-impact news), and explicit Gold XAUUSD inverse correlation evaluation.
   - **Implement `compute_session_levels`**: Add automated extraction of Asian (00-07 UTC), London (07-12 UTC), and NY (12-20 UTC) ranges from candle histories.
   - **Build `SMCPerceptionService`**: Aggregate 15M and 1H Order Blocks and FVGs from `market_history_service`.
   - **Expose Read-Only REST Endpoints**: Add `GET /api/v1/smc/structure`, `GET /api/v1/smc/sweeps`, and `GET /api/v1/smc/conviction` adhering to Requirement R4.
   - **Expand Test Suite**: Add tests for news blackout penalties and session level extraction while verifying all 28 existing tests continue to pass.

---

## 5. Verification Method

To independently verify all findings and test suite health:

1. **Verify SMC Unit Tests**:
   ```powershell
   $env:PYTHONPATH="."
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py -v
   ```
   *Expected Result*: 28 passed in ~0.5s.

2. **Verify Adjacent Engine Unit Tests**:
   ```powershell
   $env:PYTHONPATH="."
   C:\Python313\python.exe -m pytest tests/unit/test_v10_regime_memory_and_diagnostics.py -q
   C:\Python313\python.exe -m pytest tests/unit/test_v10_phase3_capital_guardian.py -q
   ```
   *Expected Result*: 18 passed and 23 passed, zero regressions.

3. **Inspect Core Files**:
   - `backend/app/schemas/smc_structure.py`
   - `backend/app/core/engines/smc_structure_engine.py`
   - `backend/tests/unit/test_v10_smc_structure_engine.py`

4. **Invalidation Condition**:
   If any of the 28 tests in `test_v10_smc_structure_engine.py` fail, or if `detect_order_blocks`, `detect_fair_value_gaps`, or `detect_session_liquidity_sweeps` fails to handle boundary inputs (e.g. $<3$ candles, None sessions), this survey's stability conclusion is invalidated.
