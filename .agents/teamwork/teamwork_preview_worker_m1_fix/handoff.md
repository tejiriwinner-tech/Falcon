# Remediation Handoff Report: Milestone M1 Fixes

**Author**: Worker M1 Fix (`teamwork_preview_worker_m1_fix`)  
**Target Milestone**: M1 (SMC Perception Engine & REST API Remediation)  
**Parent Agent**: `parent` (`88902fed-33f0-4817-bfd0-62d9140bbc2f`)  
**Date**: 2026-09-29  
**Verdict**: **COMPLETE**

---

## 1. Observation

### Findings Remediated
1. **News Blackout Negative Minutes Vulnerability**:
   - Location: `backend/app/core/engines/smc_structure_engine.py:829` (previously line 823).
   - Original code:
     ```python
     if minutes_to_news is not None and minutes_to_news <= 15:
     ```
   - Previous behavior: When `minutes_to_news` was negative (e.g. `-120`), indicating a news release in the past, `macro_news_penalty = 15.0` was applied with reason `"Macro Event Risk: High-impact news in -120m applies -15 pts news blackout penalty"`.
   - Remediated code:
     ```python
     if minutes_to_news is not None and 0 <= minutes_to_news <= 15:
     ```
   - Observed behavior after remediation:
     Running REPL:
     ```python
     smc_structure_engine.calculate_composite_conviction([], [], [], 'BUY', 'LONDON', 1.0, macro_news_impact='HIGH', minutes_to_news=-120)
     ```
     Yields:
     - `macro_news_penalty: 0.0`
     - `key_reasons`: `['Sniper Entry: Bullish breakout / price-action trigger (+15 pts)', 'Prime Session Timing: London Killzone (LONDON) (+20 pts)', 'Macro Correlation: DXY unassigned, neutral baseline (+10 pts)', 'Execution Quality: Tight spread at 1.0 pips (0 penalty)']` (Zero penalty and no blackout penalty text).

2. **Defensive Candle Attribute Extraction in `compute_session_levels`**:
   - Location: `backend/app/core/engines/smc_structure_engine.py:401-417`.
   - Original code:
     ```python
     hi = getattr(c, "high", 0.0)
     lo = getattr(c, "low", 0.0)
     ```
   - Defect risk: If a candle object had an explicit `high=None` or `low=None` attribute, `getattr(c, "high", 0.0)` returned `None`, causing `float(hi)` to raise `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
   - Remediated code:
     ```python
     hi = getattr(c, "high", None)
     hi_val = float(hi) if hi is not None else 0.0
     lo = getattr(c, "low", None)
     lo_val = float(lo) if lo is not None else 0.0
     cl = getattr(c, "close", None) if getattr(c, "close", None) is not None else getattr(c, "close_price", 0.0)
     if isinstance(c, dict):
         op = c.get("open", op)
         hi_dict = c.get("high")
         if hi_dict is not None:
             hi_val = float(hi_dict)
         lo_dict = c.get("low")
         if lo_dict is not None:
             lo_val = float(lo_dict)
         cl = c.get("close", cl)

     return dt, float(op if op is not None else 0.0), hi_val, lo_val, float(cl if cl is not None else 0.0)
     ```
   - Observed behavior after remediation: Mock candle objects with `high=None` and `low=None` parse cleanly, returning `0.0` without any exceptions.

3. **Query Parameter Validation in `smc.py`**:
   - Location: `backend/app/api/v1/smc.py:136`.
   - Original code:
     ```python
     minutes_to_news: Optional[int] = Query(default=None, description="Minutes until high-impact release"),
     ```
   - Remediated code:
     ```python
     minutes_to_news: Optional[int] = Query(default=None, ge=0, description="Minutes until high-impact release"),
     ```
   - Observed behavior after remediation: Passing negative query parameter `GET /api/v1/smc/conviction?minutes_to_news=-120` returns `HTTP 422 Unprocessable Entity`.

4. **Test Suite Execution**:
   Command:
   ```powershell
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py tests/unit/test_v10_smc_adversarial.py -v
   ```
   Verbatim output:
   ```
   ======================= 89 passed, 36 warnings in 1.49s =======================
   ```
   89 of 89 tests passed (49 tests in `test_v10_smc_structure_engine.py` and 40 tests in `test_v10_smc_adversarial.py`).

---

## 2. Logic Chain

1. **Step 1 (Macro News Boundary)**:
   - Observation: Past news events can result in negative values for `minutes_to_news` when calculated as `(event_time - current_time)`.
   - Premise: The previous check `minutes_to_news <= 15` matched any negative number (e.g. `-120 <= 15` is `True`), triggering false-positive news blackout penalties long after releases concluded.
   - Deduction: Constraining the condition to `0 <= minutes_to_news <= 15` guarantees that only upcoming or immediate releases within the 15-minute pre-release window trigger the -15 pts penalty.

2. **Step 2 (Defensive Attribute Extraction)**:
   - Observation: In Python, `getattr(obj, "attr", default)` returns `None` if `obj.attr` is explicitly set to `None`, bypassing the default value.
   - Premise: `float(None)` raises a fatal `TypeError`.
   - Deduction: Explicitly checking `float(hi) if hi is not None else 0.0` prevents type conversion errors across malformed objects or dictionaries.

3. **Step 3 (API Contract Enforcement)**:
   - Observation: The REST API query parameter `minutes_to_news` represents minutes *until* release.
   - Premise: Negative countdown values are invalid client input for this parameter.
   - Deduction: FastAP/Pydantic `Query(default=None, ge=0, ...)` correctly rejects negative inputs at the HTTP boundary with 422 Unprocessable Entity.

---

## 3. Caveats

- **Time Horizon for Past News**: The current fix ensures news releases in the past (`minutes_to_news < 0`) do not trigger the pre-release blackout penalty. If a subsequent milestone requires a post-release volatility blackout window (e.g., within 15 minutes *after* release), that would be implemented with a separate post-release parameter or symmetric window `abs(minutes_to_news) <= 15`.
- **Database Fixtures**: As verified by Challenger and Reviewers, unit tests utilize mocks for `market_history_service.get_bars` to remain isolated from remote database network dependencies.

---

## 4. Conclusion

All remediation tasks assigned to Worker M1 Fix are complete:
- `backend/app/core/engines/smc_structure_engine.py` line 829 now enforces `0 <= minutes_to_news <= 15`.
- `backend/app/core/engines/smc_structure_engine.py` lines 401-417 defensively handle explicit `None` values on candle attributes.
- `backend/app/api/v1/smc.py` line 136 enforces `ge=0` on `minutes_to_news`.
- Regression tests in `test_v10_smc_structure_engine.py` and `test_v10_smc_adversarial.py` verify zero news penalty for negative minutes, rejection with 422 in the API, and graceful handling of `None` attributes.
- 89 of 89 tests pass cleanly with 0 failures and 0 errors.

---

## 5. Verification Method

To independently verify the fixes:

1. **Run Full M1 Test Suite (Baseline + Adversarial)**:
   ```powershell
   cd c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\backend
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py tests/unit/test_v10_smc_adversarial.py -v
   ```
   *Expected outcome*: 89 passed in ~1.5s.

2. **Verify Negative Minutes Behavior in REPL**:
   ```powershell
   cd c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\backend
   C:\Python313\python.exe -c "from app.core.engines.smc_structure_engine import smc_structure_engine; score = smc_structure_engine.calculate_composite_conviction([], [], [], 'BUY', 'LONDON', 1.0, macro_news_impact='HIGH', minutes_to_news=-120); print('Penalty:', score.macro_news_penalty); print('Reasons:', score.key_reasons)"
   ```
   *Expected outcome*: `Penalty: 0.0`, no `"news blackout penalty"` in reasons.

3. **Verify API 422 Rejection on Negative Minutes**:
   ```powershell
   cd c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\backend
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py -k "test_smc_conviction_endpoint_negative_minutes_rejected" -v
   ```
   *Expected outcome*: 1 passed (HTTP 422 returned).

4. **Verify Candle None Attribute Handling**:
   ```powershell
   cd c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\backend
   C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_adversarial.py -k "test_explicit_none_candle_high_low" -v
   ```
   *Expected outcome*: 1 passed (no TypeError).
