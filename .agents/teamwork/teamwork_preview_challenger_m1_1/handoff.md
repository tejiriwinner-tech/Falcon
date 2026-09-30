# Adversarial Handoff Report: Milestone M1 — SMC Perception Engine

**Author**: Challenger 1 (`teamwork_preview_challenger_m1_1`)  
**Target Milestone**: M1 (SMC Perception Engine & REST API)  
**Parent Agent**: `parent` (`88902fed-33f0-4817-bfd0-62d9140bbc2f`)  
**Date**: 2026-09-29  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### Codebase State & Implementation Artifacts
- **Target Implementation**:
  - `backend/app/core/engines/smc_structure_engine.py`:
    - `compute_session_levels` (lines 349–530)
    - `calculate_composite_conviction` (lines 532–868)
  - `backend/app/schemas/smc_structure.py`:
    - `SessionLevels`, `CompositeConvictionScore`, `SMCStructureResponse`, `SMCSweepsResponse`
  - `backend/app/api/v1/smc.py`:
    - `GET /api/v1/smc/structure`, `GET /api/v1/smc/sweeps`, `GET /api/v1/smc/conviction`
  - `backend/tests/unit/test_v10_smc_structure_engine.py`: 48 tests passing.

### Test Harness Execution
Challenger 1 created and executed a dedicated adversarial test suite containing 37 automated tests:
`backend/tests/unit/test_v10_smc_adversarial.py`

Command executed:
```powershell
C:\Python313\python.exe -m pytest backend/tests/unit/test_v10_smc_structure_engine.py backend/tests/unit/test_v10_smc_adversarial.py -v
```
Verbatim result:
```
======================= 85 passed, 36 warnings in 1.59s =======================
```

### Specific Empirical Observations
1. **News Minutes Boundary Condition (`smc_structure_engine.py`, lines 821–828)**:
   ```python
   # 7. Macro High-Impact News Blackout Penalty (0-15 deduction)
   macro_news_penalty = 0.0
   if macro_news_impact and macro_news_impact.strip().upper() == "HIGH":
       if minutes_to_news is not None and minutes_to_news <= 15:
           macro_news_penalty = 15.0
           key_reasons.append(
               f"Macro Event Risk: High-impact news in {minutes_to_news}m applies -15 pts news blackout penalty"
           )
   ```
   - For `minutes_to_news = 0`: `macro_news_penalty = 15.0` (Correct).
   - For `minutes_to_news = 15`: `macro_news_penalty = 15.0` (Correct boundary).
   - For `minutes_to_news = 16`: `macro_news_penalty = 0.0` (Correct non-penalty).
   - For `minutes_to_news = None`: `macro_news_penalty = 0.0` (Correct).
   - **Vulnerability**: For negative values (`minutes_to_news = -1`, `minutes_to_news = -120`, `minutes_to_news = -1440`):
     Executed empirical check:
     ```python
     smc_structure_engine.calculate_composite_conviction([], [], [], 'BUY', 'LONDON', 1.0, macro_news_impact='HIGH', minutes_to_news=-120)
     ```
     Result:
     - `macro_news_penalty: 15.0`
     - `key_reasons: ['Macro Event Risk: High-impact news in -120m applies -15 pts news blackout penalty']`
     - REST API call `GET /api/v1/smc/conviction?macro_news_impact=HIGH&minutes_to_news=-120` returns HTTP 200 with `macro_news_penalty: 15.0`.
     - Any past news release, even hours or days in the past, permanently triggers the -15 pts blackout penalty due to the absence of a lower bound check (`minutes_to_news >= 0` or a symmetric window check `abs(minutes_to_news) <= 15`).

2. **Spread Friction Clamping (`smc_structure_engine.py`, lines 806–819)**:
   - For `spread_pips = 1000.0`: `spread_penalty = 25.0` (Properly clamped at max 25.0 pts).
   - For `spread_pips = -5.0`: `spread_penalty = 0.0` (Treated as `<= 1.2`, does not inflate score).
   - Tier boundaries at 1.2, 2.5, 4.0 pips behave deterministically and continuously.

3. **Case-Insensitive Symbols & Gold/DXY Confluence (`smc_structure_engine.py`, lines 732–776)**:
   - Evaluated inputs: `"xauusd"`, `"Gold"`, `"XAUUSD"`, `"XAU/USD"`, `"xau/usd"`, `"GOLD"`, `"xau"`, `" gold "`.
   - All variations are successfully normalized (`sym_clean = symbol.strip().upper().replace("/", "").replace(" ", "")`).
   - Long Gold with Bullish DXY imposes 0.0 correlation score (penalty); Bearish DXY awards 20.0 correlation score (boost).
   - Non-gold symbols (`"EURUSD"`, `"gbpusd"`, `"USDCAD"`) route cleanly to generic currency macro correlation.
   - `symbol = None` and `symbol = ""` default safely to neutral baseline 10.0 pts.

4. **Composite Score Clamping (`smc_structure_engine.py`, lines 830–838)**:
   - Minimum bound test: All worst penalties applied (smc=0, sniper=0, session=off-hours(+5), dxy opposing (+0), spread=1000 (-25), news blackout (-15) -> raw total = -35.0).
     - Result: `total_score = 0.0`, `bias = ConvictionBias.NEUTRAL`. Pydantic validation passes (`ge=0.0`).
   - Maximum bound test: Maximum alignment yields `total_score = 100.0`. Pydantic validation passes (`le=100.0`).

5. **Session Levels Boundary Handling (`smc_structure_engine.py`, lines 349–530)**:
   - Empty list `candles = []`: Returns `SessionLevels(session_name="NONE", high=0.0, low=0.0, open_price=0.0, close_price=0.0)` with zero exceptions.
   - Single candle lists:
     - 03:00 UTC candle -> `res.asian_high = 1.1050`, `res.london_high = None`, `res.ny_high = None`.
     - 09:00 UTC candle -> `res.london_high = 1.2050`.
     - 21:00 UTC candle -> `primary.session_name = "ALL"`, `res.high = 1.3050`.
   - Candles across midnight: Correctly clusters bars across UTC calendar date boundary; fallback logic retains previous day's session levels if the current day has not yet reached that session.
   - Malformed timestamps: String parsing fallbacks (`"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%dT%H:%M:%S"`, `isoformat`) safely catch `ValueError` and fall back to overall max/min across all candles. `None` timestamps and mixed `int`/`float` timestamps (both seconds and milliseconds) parse without raising errors.
   - Candle types: Interoperable across `PriceBar`, `CandleBar`, and raw dictionaries.

6. **REST API Invariants (`backend/app/api/v1/smc.py`)**:
   - `GET /api/v1/smc/structure`, `GET /api/v1/smc/sweeps`, `GET /api/v1/smc/conviction` return valid HTTP 200 responses.
   - Mutation requests (POST, PUT, DELETE) are rejected with HTTP 405 Method Not Allowed, strictly maintaining Requirement R4.
   - Query limits are bounded (`ge=10, le=500`), returning HTTP 422 for `limit=1` or `limit=9999`.

---

## 2. Logic Chain

1. **Premise 1**: The interface contract for macro news blackout in `PROJECT.md` specifies:
   `High-impact news within 15 min imposes -15 pts penalty.`
   In `smc_structure_engine.py`:
   `minutes_to_news: Optional minutes remaining to nearest economic news release.`
2. **Premise 2**: In production systems, `minutes_to_news` can be computed dynamically as `(release_time - current_time).total_seconds() / 60`. Once a news event passes into the past, this value becomes negative (e.g., `-1`, `-60`, `-120`). Alternatively, API consumers might pass negative values.
3. **Premise 3**: Line 823 implements:
   `if minutes_to_news is not None and minutes_to_news <= 15:`
   Because there is no lower bound, any negative number satisfies `minutes_to_news <= 15`.
4. **Premise 4**: Consequently, news released 2 hours ago (`minutes_to_news = -120`) or 24 hours ago (`minutes_to_news = -1440`) inflicts the full -15 pts blackout penalty, outputting `"Macro Event Risk: High-impact news in -120m applies -15 pts news blackout penalty"`.
5. **Deduction**: This is an incorrect boundary condition that causes false-positive macro news blackout penalties for past events.
6. **Required Correction**:
   - In `smc_structure_engine.py`, enforce:
     ```python
     if minutes_to_news is not None and 0 <= minutes_to_news <= 15:
     ```
     *(Or if a two-sided blackout window before and after news release is intended: `if minutes_to_news is not None and -15 <= minutes_to_news <= 15:`)*.
   - In `backend/app/api/v1/smc.py`, define `ge=0` on `minutes_to_news: Optional[int] = Query(default=None, ge=0, ...)` if only pre-release countdown is supported.

---

## 3. Caveats

- **Test Suite Placement**: Challenger test suite `backend/tests/unit/test_v10_smc_adversarial.py` was created within the designated backend test directory (`backend/tests/unit/`) to maintain layout compliance and avoid placing test code in `.agents/teamwork/`.
- **Implementation Code Untouched**: In strict adherence to the Challenger archetype and the constraint *"Review-only — do NOT modify implementation code"*, Challenger 1 has not modified `smc_structure_engine.py` or `smc.py`. The required fix must be applied by Worker M1.
- No other caveats.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Worker M1's implementation of Milestone M1 is largely well-engineered, robust across extreme spreads, case-insensitive symbols, score clamping, empty candle arrays, multi-day session levels, and read-only REST endpoints (85 of 85 unit and adversarial tests pass).

However, a concrete boundary defect exists in the news blackout penalty logic:
- `minutes_to_news <= 15` lacks a lower bound, causing negative minute values (representing news releases in the past) to trigger the -15 pts blackout penalty indefinitely.

### Required Changes for Worker M1:
1. Update `backend/app/core/engines/smc_structure_engine.py` (line 823):
   Change:
   ```python
   if minutes_to_news is not None and minutes_to_news <= 15:
   ```
   To:
   ```python
   if minutes_to_news is not None and 0 <= minutes_to_news <= 15:
   ```
   *(Or `if minutes_to_news is not None and -15 <= minutes_to_news <= 15:` if post-release blackout is required by design; if so, update rationale message accordingly)*.
2. In `backend/app/api/v1/smc.py`:
   Add `ge=0` validation to `minutes_to_news`:
   ```python
   minutes_to_news: Optional[int] = Query(default=None, ge=0, description="Minutes until high-impact release"),
   ```

---

## 5. Verification Method

To independently reproduce the finding and verify all tests:

1. **Reproduce Negative News Minutes Vulnerability**:
   ```powershell
   cd backend
   C:\Python313\python.exe -c "from app.core.engines.smc_structure_engine import smc_structure_engine; score = smc_structure_engine.calculate_composite_conviction([], [], [], 'BUY', 'LONDON', 1.0, macro_news_impact='HIGH', minutes_to_news=-120); print('Penalty:', score.macro_news_penalty); print('Reasons:', score.key_reasons)"
   ```
   *Expected defect manifestation*: Outputs `Penalty: 15.0` with reason `"High-impact news in -120m applies -15 pts news blackout penalty"`.

2. **Run Full Test Suite (Baseline + Adversarial)**:
   ```powershell
   cd backend
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py tests/unit/test_v10_smc_adversarial.py -v
   ```
   *Expected outcome*: 85 passed in ~1.6s.

3. **Invalidation Condition**:
   Once Worker M1 adds the `0 <= minutes_to_news <= 15` (or `-15 <= minutes_to_news <= 15`) constraint, re-running test case `minutes_to_news = -120` will yield `macro_news_penalty = 0.0`.
