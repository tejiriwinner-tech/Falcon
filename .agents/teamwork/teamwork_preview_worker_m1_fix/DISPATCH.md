## 2026-09-29T08:46:12Z
You are Worker M1 Fix: Milestone 1 Remediation Worker.
Your working directory is: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m1_fix
You MUST read:
- Original user request: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\ORIGINAL_REQUEST.md
- Project scope document: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\orchestrator\PROJECT.md
- Challenger 1 handoff: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_challenger_m1_1\handoff.md
- Reviewer 1 handoff: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_reviewer_m1_1\handoff.md
- Reviewer 2 handoff: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_reviewer_m1_2\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive write ownership:
- `backend/app/core/engines/smc_structure_engine.py`
- `backend/app/api/v1/smc.py`
- `backend/tests/unit/test_v10_smc_structure_engine.py`
- `backend/tests/unit/test_v10_smc_adversarial.py`

Your tasks:
1. In `backend/app/core/engines/smc_structure_engine.py`:
   - Line 823: Fix the news blackout condition so past news does not trigger false penalties:
     Change:
     `if minutes_to_news is not None and minutes_to_news <= 15:`
     To:
     `if minutes_to_news is not None and 0 <= minutes_to_news <= 15:`
   - Lines 402-403: In `compute_session_levels`, handle explicit `None` values on candle attributes defensively:
     `hi = getattr(c, "high", None)`
     `hi_val = float(hi) if hi is not None else 0.0`
     `lo = getattr(c, "low", None)`
     `lo_val = float(lo) if lo is not None else 0.0`
2. In `backend/app/api/v1/smc.py`:
   - Add `ge=0` validation to query parameter `minutes_to_news`:
     `minutes_to_news: Optional[int] = Query(default=None, ge=0, description="Minutes until high-impact release")`
3. In `backend/tests/unit/test_v10_smc_structure_engine.py` and `backend/tests/unit/test_v10_smc_adversarial.py`:
   - Add unit test verifying that negative minutes (e.g. `minutes_to_news = -120`) yields `macro_news_penalty == 0.0` and no penalty in `key_reasons`.
   - Run the test suite:
     `C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py tests/unit/test_v10_smc_adversarial.py -v`
     Verify all 85+ tests pass with 0 failures and 0 errors.
4. Write your handoff report to `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m1_fix\handoff.md`.
5. Send a message to parent with completion status and artifact path.
