## 2026-09-29T10:17:13Z
You are Worker M2: Autonomous Diagnostics & Regime Memory Implementer.
Your working directory is: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m2
You MUST read:
- Original user request: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\ORIGINAL_REQUEST.md
- Project scope document: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\orchestrator\PROJECT.md
- Explorer 2 survey handoff: c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_explorer_survey_2\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive write ownership:
- `backend/app/core/services/signal_outcome_resolver.py`
- `backend/app/core/analytics/regime_memory_engine.py`
- `backend/app/core/analytics/adaptive_tuning_engine.py`
- `backend/tests/unit/test_v10_regime_memory_and_diagnostics.py`

Your tasks:
1. Complete closed-loop autonomous diagnostics in `backend/app/core/services/signal_outcome_resolver.py`:
   - When a trade outcome is resolved (especially closed at stop-loss or take-profit), invoke `regime_memory_engine.diagnose_and_record(trade, market_context)`.
   - Populate `trade.reasonForExit` and `trade.lessonLearned` directly from the forensic diagnostic result.
   - Trigger `regime_memory_engine.evaluate_strategy_health(strategy_id)` so strategies with win rate < 35% or >= 3 consecutive losses are quarantined to paper evaluation mode (`QUARANTINED_PAPER`), and resilient strategies (win rate >= 60%, PF >= 1.8) are boosted (`BOOSTED`).
   - Ensure `AdaptiveRuleTuningEngine` and `CapitalGuardianService` maintain the loss-recovery progression: 1 loss = 2.0x target, 2 losses = 4.0x target, hard $20.00 max loss ceiling across streak, and immediate reset on win (1.0x target, $0.00 streak loss).
2. Ensure strict non-custodial advisory safety: zero broker automation (`order_send = 0`, `order_modify = 0`, `order_close = 0`), read-only endpoints, pure algorithmic self-learning.
3. In `backend/tests/unit/test_v10_regime_memory_and_diagnostics.py`:
   - Add unit tests verifying that `signal_outcome_resolver` invokes `regime_memory_engine.diagnose_and_record()`, correctly updates `reasonForExit` and `lessonLearned`, and adapts strategy tuning profiles.
   - Run the test suite:
     `C:\Python313\python.exe -m pytest tests/unit/test_v10_regime_memory_and_diagnostics.py tests/unit/test_v10_dynamic_loss_recovery_and_capital.py -v`
     Verify 100% passing tests with 0 failures and 0 errors.
4. Write your handoff report to `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon\.agents\teamwork\teamwork_preview_worker_m2\handoff.md`.
5. Send a message to parent with your completion status and artifact path.
