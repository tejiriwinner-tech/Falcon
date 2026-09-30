## 2026-09-29T06:51:30Z
You are Worker M1: SMC Perception Implementer.
Your working directory is: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m1
You MUST read:
- Original user request: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\ORIGINAL_REQUEST.md
- Project scope & architecture: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\orchestrator\PROJECT.md
- Explorer 1 handoff: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_explorer_survey_1\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive write ownership:
- `backend/app/core/engines/smc_structure_engine.py`
- `backend/app/schemas/smc_structure.py`
- `backend/app/api/v1/smc.py`
- `backend/app/api/v1/api.py`
- `backend/tests/unit/test_v10_smc_structure_engine.py`

Your tasks:
1. Extend `SMCStructureEngine.calculate_composite_conviction`:
   - Add parameters: `macro_news_impact: Optional[str] = None`, `minutes_to_news: Optional[int] = None`, `symbol: Optional[str] = None`.
   - If `macro_news_impact == "HIGH"` and `minutes_to_news is not None and minutes_to_news <= 15`, apply -15 points news blackout penalty and log it in score components.
   - Symbol-aware correlation: If symbol is "XAUUSD" or "GOLD", incorporate DXY inverse correlation (Bullish DXY penalizes Long Gold by -10 pts or boosts Short Gold by +10 pts; Bearish DXY boosts Long Gold by +10 pts or penalizes Short Gold by -10 pts).
   - Ensure the score remains bounded between 0% and 100% and preserve 100% backward compatibility with all default calls.
2. Implement `SMCStructureEngine.compute_session_levels(candles: List[PriceBar]) -> SessionLevels`:
   - Extract Asian (00:00-07:00 UTC), London (07:00-12:00 UTC), and NY (12:00-20:00 UTC) high and low prices from the provided candle timestamps.
3. Expose read-only REST endpoints in `backend/app/api/v1/smc.py`:
   - `GET /api/v1/smc/structure`
   - `GET /api/v1/smc/sweeps`
   - `GET /api/v1/smc/conviction`
   - Adhere strictly to R4: Purely read-only GET endpoints, zero broker automation, no mutations on queries.
   - Include router in `backend/app/api/v1/api.py`.
4. In `backend/tests/unit/test_v10_smc_structure_engine.py`:
   - Add comprehensive tests for the macro news impact, Gold/DXY correlation, `compute_session_levels`, and REST endpoints.
   - Run the tests via python pytest and verify that ALL 28 existing tests pass, plus all new tests pass with zero failures and zero regressions.
5. Create `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m1\handoff.md` with:
   - Observation: Detailed list of files modified and exact test output
   - Logic Chain: Why the changes satisfy R1 and R4
   - Caveats: Any limitations or assumptions
   - Conclusion: Summary of changes and status
   - Verification Method: Exact commands to execute and verify the tests.
6. When done, send a message to parent with a concise completion notice and artifact paths.
