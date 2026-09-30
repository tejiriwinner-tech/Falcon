# Comprehensive Codebase & Test Survey: Smart Money Concepts (SMC) & Institutional Perception (Requirement R1)

**Surveyor**: Explorer 1 — SMC Perception Surveyor  
**Date**: 2026-09-28  
**Scope**: Smart Money Concepts (SMC) Institutional Perception (Requirement R1), test suite audit (`test_v10_smc_structure_engine.py` and adjacent suites), algorithmic inspection, gap analysis, and implementation strategy.  
**Working Directory**: `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_explorer_survey_1`

---

## 1. Executive Summary

Requirement **R1** ("Smart Money Concepts & Institutional Perception — The Eyes") requires expanding Falcon's candlestick and pattern recognition to detect institutional liquidity dynamics:
1. **Order Blocks (OB)**: Unmitigated institutional footprints on **15M** and **1H** timeframes.
2. **Fair Value Gaps (FVG)**: 3-candle sequence imbalances with mitigation tracking across FX and Gold.
3. **Session Liquidity Sweeps**: Manipulation wicks (Judas swings / turtle soup) piercing previous Asian, London, and New York session highs and lows and closing back inside.
4. **Composite Conviction Score (0–100%)**: Fusing SMC structure, candlestick triggers, session killzones, macro calendar news impact, currency strength correlation (DXY vs. Gold XAUUSD), and live spread frictions into a single mathematical conviction metric.

### Key Survey Findings:
- **Core Engine & Schemas Exist & Are Functional**: The mathematical and structural foundation is fully implemented in `backend/app/core/engines/smc_structure_engine.py` and `backend/app/schemas/smc_structure.py`.
- **Existing Unit Tests Pass 100%**: The test suite `backend/tests/unit/test_v10_smc_structure_engine.py` runs cleanly in **0.51 seconds**, with all **28 passing tests** (zero failures, zero regressions).
- **Core Gaps Identified**:
  1. *Macro Calendar News Impact*: The current `calculate_composite_conviction` calculates DXY trend confluence, but does not yet accept explicit macro calendar blackout flags or event impact penalties (`macro_news_impact`).
  2. *Live Multi-Timeframe Pipeline Orchestration*: While the engine accepts `timeframe="15m"` and `"1h"`, an overarching service layer connecting `market_history_service` 15M/1H bars directly to SMC structure detection is needed.
  3. *Autonomous Session Extractor*: Session extremes currently require pre-packaged `SessionLevels`; a dedicated extractor for Asian (00:00-07:00 UTC), London (07:00-12:00 UTC), and NY (12:00-20:00 UTC) OHLC bars will make session sweep detection completely autonomous.
  4. *REST API Exposure*: There is currently no dedicated `/api/v1/smc` router registered in `backend/app/api/v1/api.py`.
  5. *Signal Candidate Pipeline Integration*: `SignalGenerationEngine` generates `CandidateMarketSnapshot` and `SignalCandidate` without currently ingesting `CompositeConvictionScore`.

---

## 2. Code Layout & Architecture Audit

### 2.1 File Inventory for Requirement R1

| Component | File Path | Status | Purpose |
|---|---|---|---|
| **SMC Schemas** | `backend/app/schemas/smc_structure.py` | Complete (211 lines) | Pydantic V2 models for OBs, FVGs, Sweeps, Session Levels, Conviction Score |
| **SMC Engine** | `backend/app/core/engines/smc_structure_engine.py` | Complete (618 lines) | Pure deterministic algorithms for OB, FVG, Sweeps, and Conviction fusion |
| **SMC Unit Tests** | `backend/tests/unit/test_v10_smc_structure_engine.py` | Complete (723 lines) | 28 unit tests covering all algorithms, schemas, edge cases |
| **Candle Data Structures** | `backend/app/core/engines/candlestick_pattern_engine.py` | Complete (438 lines) | Defines canonical `CandleBar` used by `SMCStructureEngine` |
| **Economic Calendar Service** | `backend/app/core/services/economic_calendar_service.py` | Complete (296 lines) | Sourcing, caching, and persistence of macro news events |
| **News Service & Schemas** | `backend/app/core/services/news_service.py` & `backend/app/schemas/news.py` | Complete | Maps macro calendar to frontend contracts |
| **Briefing Service** | `backend/app/core/services/briefing_service.py` | Complete (415 lines) | Synthesizes Asian levels, OB/FVG zones, and macro news for London Open Briefing |
| **Market History Service** | `backend/app/core/services/market_history_service.py` | Complete (331 lines) | Ingestion and storage of 15m/1h OHLC bars |
| **Signal Candidate Schema** | `backend/app/schemas/signal_candidate.py` | Complete (91 lines) | Defines `CandidateMarketSnapshot` and `SignalCandidate` |
| **Signal Generation Engine** | `backend/app/core/engines/signal_generation_engine.py` | Functional (663 lines) | Pipeline candidate generation (needs SMC perception hook) |
| **SMC REST Router** | *Not Yet Created* | **Missing** | Exposing read-only GET endpoints (`/api/v1/smc/structure`, `/api/v1/smc/conviction`) |
| **SMC Service Layer** | *Not Yet Created* | **Missing** | Glue service connecting `market_history_service` bars to `smc_structure_engine` |

---

## 3. In-Depth Algorithmic Inspection

### 3.1 Order Block (OB) Detection (`detect_order_blocks`)
- **Location**: `backend/app/core/engines/smc_structure_engine.py:52-188`
- **Method Signature**:
  ```python
  def detect_order_blocks(
      self,
      candles: List[CandleBar],
      symbol: str,
      timeframe: str,
      swing_window: int = 1,
  ) -> List[OrderBlock]:
  ```
- **Detection Mechanics**:
  1. Validates `len(candles) >= 3`.
  2. Identifies prior swing highs/lows within a 20-candle lookback window.
  3. **Bullish Order Block**: Candle $j$ closes above swing high $k$ with a bullish body (`candles[j].close > candles[k].high and candles[j].is_bullish`). The engine searches backwards from $j-1$ to find the last opposing bearish candle (`close < open`).
  4. **Bearish Order Block**: Candle $j$ closes below swing low $k$ with a bearish body (`candles[j].close < candles[k].low and candles[j].is_bearish`). The engine searches backwards from $j-1$ to find the last opposing bullish candle (`close > open`).
  5. **Mitigation Tracking**: Subsequent candles ($m > j$) are evaluated:
     - Bullish OB: If `candles[m].low <= ob_candle.high`, `is_mitigated = True`.
     - Bearish OB: If `candles[m].high >= ob_candle.low`, `is_mitigated = True`.
  6. **Deduplication**: Identical blocks identified across overlapping displacement sequences are deduplicated via a `seen_blocks` set storing `(block_type, ob_idx, high, low)`.
- **Timeframe Compliance**: Accepts any timeframe (`"15m"`, `"1h"`, etc.). Operates directly on sequential `CandleBar` series.

### 3.2 Fair Value Gap (FVG) Detection (`detect_fair_value_gaps`)
- **Location**: `backend/app/core/engines/smc_structure_engine.py:189-283`
- **Method Signature**:
  ```python
  def detect_fair_value_gaps(
      self,
      candles: List[CandleBar],
      symbol: str,
      timeframe: str,
      pip_size: Optional[float] = None,
  ) -> List[FairValueGap]:
  ```
- **Detection Mechanics**:
  1. Inspects 3-candle sliding windows `(bar1, bar2, bar3)`:
     - **Bullish FVG**: `bar1.high < bar3.low`. Imbalance top = `bar3.low`, bottom = `bar1.high`.
     - **Bearish FVG**: `bar1.low > bar3.high`. Imbalance top = `bar1.low`, bottom = `bar3.high`.
  2. Dynamic Pip Resolution: Automatically invokes `_get_pip_size(symbol)`:
     - `0.0001` for major/minor FX pairs (`EURUSD`, `GBPUSD`)
     - `0.01` for JPY pairs (`USDJPY`, `EURJPY`)
     - `0.1` for Gold (`XAUUSD`, `GOLD`)
     - `1.0` for Crypto and Indices (`BTCUSD`, `US30`, `NAS100`)
     - Computes `size_pips = round((top - bottom) / actual_pip_size, 2)`.
  3. **Mitigation Tracking**: Subsequent candles ($m > i$) are checked:
     - Bullish FVG: If `candles[m].low <= top`, `is_mitigated = True`.
     - Bearish FVG: If `candles[m].high >= bottom`, `is_mitigated = True`.
  4. Stores `bar1_time` and `bar3_time` for temporal reference.

### 3.3 Session Liquidity Sweeps (`detect_session_liquidity_sweeps`)
- **Location**: `backend/app/core/engines/smc_structure_engine.py:284-348`
- **Method Signature**:
  ```python
  def detect_session_liquidity_sweeps(
      self,
      candles: List[CandleBar],
      session_levels: SessionLevels,
      symbol: str,
  ) -> List[LiquiditySweep]:
  ```
- **Detection Mechanics**:
  1. Compares incoming candles against `session_levels` (`sess_high`, `sess_low`, `sess_name`).
  2. **High Sweep (Buy-Side Liquidity Purge)**:
     `c.high > sess_high and sess_low <= c.close <= sess_high`
     Wick penetrates above prior session high, but candle closes back inside the range.
  3. **Low Sweep (Sell-Side Liquidity Purge)**:
     `c.low < sess_low and sess_low <= c.close <= sess_high`
     Wick penetrates below prior session low, but candle closes back inside the range.
  4. **Breakout Exclusion**: Candles that pierce and close outside (`c.close > sess_high` or `c.close < sess_low`) are explicitly rejected as breakout expansions rather than liquidity sweeps.
  5. Computes `penetration_distance = abs(sweep_wick_extreme - swept_level)`.

### 3.4 Composite Conviction Score Fusion (`calculate_composite_conviction`)
- **Location**: `backend/app/core/engines/smc_structure_engine.py:349-614`
- **Scoring Architecture (0–100%)**:

$$\text{Total Score} = \text{SMC Alignment (0–35)} + \text{Sniper Trigger (0–25)} + \text{Session Timing (0–20)} + \text{Macro/DXY Correlation (0–20)} - \text{Spread Penalty (0–25)}$$

| Factor | Points | Evaluation Criteria |
|---|---|---|
| **1. SMC Alignment** | 0 to 35 pts | - Unmitigated aligned Order Block: +15 pts<br>- Mitigated aligned Order Block: +7 pts<br>- Unmitigated aligned FVG: +10 pts<br>- Mitigated aligned FVG: +5 pts<br>- Opposing session liquidity sweep (fuel): +10 pts<br>- Penalty for unmitigated opposing OB overhead/underneath: -6 pts<br>- Penalty for unmitigated opposing FVG: -4 pts |
| **2. Sniper Trigger** | 0 to 25 pts | - Turtle Soup liquidity sweep pattern confirmed: 25 pts<br>- Direct OB/FVG mitigation trigger: 20 pts<br>- Basic price action breakout: 15 pts<br>- Neutral / No pattern: 0 pts |
| **3. Session Timing** | 0 to 20 pts | - London Open / London Session: +20 pts<br>- New York / Overlap Killzone: +20 pts<br>- Asian Accumulation: +10 pts<br>- Off-peak hours: +5 pts |
| **4. Macro / DXY Correlation** | 0 to 20 pts | - Aligned DXY trend (Bearish DXY for EUR/Gold long, Bullish DXY for short): +20 pts<br>- Opposing DXY trend (Macro headwind): 0 pts<br>- Neutral / unassigned DXY: +10 pts |
| **5. Live Spread Penalty** | 0 to -25 pts | - Tight spread ($\le 1.2$ pips): 0 deduction<br>- Moderate spread ($1.2 - 2.5$ pips): $-(spread - 1.2) \times 2.5$<br>- Elevated spread ($2.5 - 4.0$ pips): $-[3.25 + (spread - 2.5) \times 4.5]$<br>- Wide spread ($> 4.0$ pips): progressive penalty up to -25 pts |

- **Directional Bias Resolution**:
  - $\ge 60.0 \implies$ Directional `BULLISH` or `BEARISH`
  - $40.0 \le \text{Score} < 60.0 \implies$ Directional if `smc_alignment_score >= 12.0`, else `NEUTRAL`
  - $< 40.0 \implies \text{NEUTRAL}$

---

## 4. Test Suite Audit & Execution Verification

### 4.1 Primary Unit Test Suite: `test_v10_smc_structure_engine.py`
We executed the primary test suite directly via `C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py`:
- **Result**: **28 passed, 36 warnings in 0.51s**
- **Failures / Regressions**: **0**

#### Detailed Breakdown of the 28 Unit Tests:

1. **Order Block Detection & Mitigation (5 tests)**:
   - `test_bullish_order_block_detection_unmitigated`: PASSED
   - `test_bullish_order_block_mitigated`: PASSED
   - `test_bearish_order_block_detection_unmitigated`: PASSED
   - `test_bearish_order_block_mitigated`: PASSED
   - `test_order_block_edge_cases`: PASSED (handles empty candles, $<3$ candles, flat candles)

2. **Fair Value Gap Detection & Mitigation (7 tests)**:
   - `test_bullish_fvg_detection_unmitigated`: PASSED
   - `test_bullish_fvg_mitigated`: PASSED
   - `test_bearish_fvg_detection_unmitigated`: PASSED
   - `test_bearish_fvg_mitigated`: PASSED
   - `test_fvg_gold_symbol_pip_size`: PASSED (validates 0.1 pip size for Gold XAUUSD)
   - `test_fvg_overlapping_no_gap`: PASSED (confirms zero false positives on overlapping candles)
   - `test_fvg_insufficient_candles`: PASSED

3. **Session Liquidity Sweeps (5 tests)**:
   - `test_asian_high_swept_during_london_open`: PASSED (verifies HIGH_SWEEP / Judas Swing above Asian high)
   - `test_asian_low_swept_during_london_open`: PASSED (verifies LOW_SWEEP below Asian low)
   - `test_breakout_candle_closing_outside_not_a_sweep`: PASSED (expansion candle excluded)
   - `test_candle_inside_range_not_a_sweep`: PASSED
   - `test_sweep_empty_or_none_inputs`: PASSED

4. **Composite Conviction Score Calculation (6 tests)**:
   - `test_maximum_conviction_bullish_setup`: PASSED (100% score on full confluence)
   - `test_maximum_conviction_bearish_setup`: PASSED (100% score on full confluence)
   - `test_dxy_macro_headwind_reduces_score`: PASSED (correlation drops to 0 pts on headwind)
   - `test_wide_spread_penalty_applied`: PASSED (verifies progressive spread deduction)
   - `test_contradicting_structure_penalty`: PASSED (verifies -6/-4 penalty for opposing structure)
   - `test_neutral_and_empty_inputs_behavior`: PASSED (verifies graceful baseline fallback)

5. **Schema Invariants & Property Helpers (5 tests)**:
   - `test_order_block_properties`: PASSED (`is_bullish`, `range`, `mid_price`)
   - `test_fair_value_gap_properties`: PASSED (`is_bearish`, `midpoint`)
   - `test_liquidity_sweep_properties`: PASSED (`is_high_sweep`, `penetration_distance`)
   - `test_session_levels_properties`: PASSED (`session_range`, `mid_price`)
   - `test_pip_size_helper`: PASSED (EURUSD, USDJPY, XAUUSD, BTCUSD, US30, NAS100)

### 4.2 Adjacent Test Suites Audit
To ensure zero regressions across Falcon's foundation:
- `backend/tests/unit/test_v10_dynamic_loss_recovery_and_capital.py`: 54 tests passing.
- `backend/tests/unit/test_v10_copilot_and_briefings.py`: 18 tests passing.
- `backend/tests/unit/test_v10_regime_memory_and_diagnostics.py`: 18 tests passing.
- `backend/tests/unit/test_v10_phase3_capital_guardian.py`: 23 tests passing.
- `backend/tests/unit/test_v10_phase4_guardian_integration.py`: 25 tests passing.

---

## 5. Gap Analysis (Current Implementation vs. Requirement R1)

| Requirement Sub-Item | Current Code Status | Gap Description | Severity |
|---|---|---|---|
| **OB & FVG on 15M and 1H** | Core logic complete in `smc_structure_engine.py` | Engine accepts `timeframe="15m"` and `"1h"`. However, no scheduled task or service automatically queries 15M/1H bars from `market_history_service` to build and maintain an active cache of unmitigated OBs/FVGs across watchlisted instruments. | Medium |
| **Session Liquidity Sweeps** (Asian, London, NY) | Core logic complete in `detect_session_liquidity_sweeps` | Requires external injection of `SessionLevels`. There is no automated `extract_session_levels(candles, session_name)` method in `smc_structure_engine` to calculate the high/low/close of Asian (00-07 UTC), London (07-12 UTC), and NY (12-20 UTC) automatically from raw price history. | Medium |
| **Macro Calendar News Impact Fusion** | Sourced via `economic_calendar_service`, but omitted in conviction score | `calculate_composite_conviction` takes `dxy_trend: Optional[str]`, but does NOT accept `macro_news_impact: Optional[str]` or check news blackout proximity. High-impact news proximity should apply a risk penalty (-10 to -15 pts). | High |
| **Currency Strength Correlation (DXY vs. Gold XAUUSD)** | Handled via static string comparison (`dxy_clean in [...]`) | Explicit inverse correlation calculation for Gold (XAUUSD vs. DXY) is evaluated based on `dxy_trend` string rather than asset-specific correlation strength. Adding explicit symbol-aware correlation logic (`XAUUSD` inverse to DXY, `USDJPY` direct with DXY) will strengthen institutional reasoning. | Low |
| **Read-Only REST API Endpoints** | Zero SMC endpoints registered in `api.py` | Mobile app and external consumers have no direct way to query current OBs, FVGs, or Conviction Scores via HTTP GET. Needs `GET /api/v1/smc/structure` and `GET /api/v1/smc/conviction`. | High |
| **Pipeline Candidate Integration** | `SignalGenerationEngine` creates candidates without SMC conviction | `CandidateMarketSnapshot` has `newsImpact`, `session`, `spread`, but does not populate `smcConvictionScore` or embed institutional OB/FVG mitigation reasons in `CandidateReason`. | Medium |

---

## 6. Recommended Implementation Strategy

### Phase 2 Implementation Plan for Implementing Agents:

#### Step 1: Enhance `SMCStructureEngine` (Zero-Regression Signature Expansion)
1. Add optional parameters to `calculate_composite_conviction`:
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
       macro_news_impact: Optional[str] = None,  # NEW: "HIGH", "MEDIUM", "LOW"
       minutes_to_news: Optional[int] = None,    # NEW: Proximity to high impact release
       symbol: Optional[str] = None,             # NEW: Context for DXY vs Gold/FX
   ) -> CompositeConvictionScore:
   ```
2. Integrate Macro News Impact logic:
   - If `macro_news_impact == "HIGH"` and `minutes_to_news is not None and minutes_to_news <= 30`:
     - Deduct macro news penalty (-15 pts).
     - Append caution: `"Macro Blackout Warning: High-impact news release within {minutes_to_news} min (-15 pts)"`.
   - If `symbol` has `"XAU"` or `"GOLD"`, explicitly verify inverse correlation with DXY (`BEARISH DXY -> BULLISH Gold`).
3. Add `compute_session_levels(candles: List[CandleBar], session_name: str) -> Optional[SessionLevels]` helper method to `SMCStructureEngine`.

#### Step 2: Build `SMCPerceptionService` Layer
Create `backend/app/core/services/smc_perception_service.py`:
- Queries `market_history_service` for 15M and 1H bars for target symbols (`EURUSD`, `GBPUSD`, `XAUUSD`).
- Computes Asian, London, and NY `SessionLevels`.
- Runs `detect_order_blocks`, `detect_fair_value_gaps`, and `detect_session_liquidity_sweeps`.
- Obtains macro news status from `economic_calendar_service`.
- Produces aggregated multi-timeframe perception snapshots.

#### Step 3: Implement Read-Only REST Endpoints (`backend/app/api/v1/smc.py`)
Expose pure GET endpoints adhering strictly to R4:
- `GET /api/v1/smc/structure?symbol=XAUUSD&timeframe=15m`: Returns detected OBs and FVGs.
- `GET /api/v1/smc/sweeps?symbol=XAUUSD`: Returns detected session liquidity sweeps.
- `GET /api/v1/smc/conviction?symbol=XAUUSD&direction=BUY`: Returns real-time `CompositeConvictionScore`.
- Register the router in `backend/app/api/v1/api.py`.

#### Step 4: Expand Unit Tests
- Add 5-8 new unit tests in `test_v10_smc_structure_engine.py` validating:
  - Macro news blackout penalty deduction.
  - Gold vs. DXY inverse correlation precision.
  - Automated session level extraction from timestamped bars.
  - Ensure all 28 existing unit tests continue to pass 100%.

---

## 7. Conclusion

Falcon's Phase 1 foundation for Smart Money Concepts (SMC) & Institutional Perception is robust, mathematically deterministic, and backed by a comprehensive unit test suite passing 28 of 28 tests in 0.51s. The core algorithms for Order Blocks, Fair Value Gaps, Session Sweeps, and Composite Conviction are already soundly constructed. Completing Requirement R1 requires targeted enhancements: explicit macro calendar news impact fusion into conviction scoring, symbol-aware DXY vs. Gold inverse correlation refinement, automated session level extraction, service-level 15M/1H multi-timeframe caching, and read-only REST API endpoint exposure.
