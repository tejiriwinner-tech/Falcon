# Progress - Worker M1 Fix

Last visited: 2026-09-29T09:12:00Z
Status: Completed

## Tasks
- [x] Create DISPATCH.md and BRIEFING.md
- [x] Read required documents (ORIGINAL_REQUEST.md, PROJECT.md, Challenger 1 handoff, Reviewer 1 handoff, Reviewer 2 handoff)
- [x] View target code files and inspect lines to modify
- [x] Implement fixes in backend/app/core/engines/smc_structure_engine.py:
  - Line 823: News blackout condition restricted to `0 <= minutes_to_news <= 15`
  - Lines 402-403: Defensive handling of explicit `None` on candle `high`/`low` attributes and dict properties
- [x] Implement query parameter validation in backend/app/api/v1/smc.py:
  - Added `ge=0` validation to `minutes_to_news` parameter on `/api/v1/smc/conviction`
- [x] Add tests for negative minutes_to_news in test_v10_smc_structure_engine.py and test_v10_smc_adversarial.py:
  - Added unit test in `test_v10_smc_structure_engine.py` verifying `minutes_to_news = -120` produces `macro_news_penalty == 0.0`
  - Added defensive `None` candle attribute test in `test_v10_smc_structure_engine.py`
  - Added query validation test for negative minutes (`422 Unprocessable Entity`) in `test_v10_smc_structure_engine.py`
  - Added assertions to `test_minutes_to_news_negative` and `test_minutes_to_news_large_negative` in `test_v10_smc_adversarial.py`
  - Added `test_explicit_none_candle_high_low` in `test_v10_smc_adversarial.py`
- [x] Run test suite with C:\Python313\python.exe -m pytest tests/unit/test_v10_smc_structure_engine.py tests/unit/test_v10_smc_adversarial.py -v
- [x] Verify test results: 89 passed (0 failures, 0 errors)
- [x] Update BRIEFING.md and progress.md
- [x] Write handoff.md
- [x] Send completion message to parent
