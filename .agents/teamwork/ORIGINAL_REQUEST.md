# Original User Request

## Initial Request — 2026-09-28T18:55:38Z

# Teamwork Project Prompt

> Requested team: Full multi-agent team (parallel implementation, adversarial review, and testing)

Transform Falcon into an evolving, autonomous AI trading intelligence by implementing Phase 2 (Smart Money Institutional Perception & Regime Memory) and Phase 3 (Conversational AI Co-Pilot & Telegram Briefings), building on top of the verified Phase 1 foundation.

Working directory: `c:\Users\ACER\Documents\SCHOOLWORKS\Falcon`
Integrity mode: development

## Requirements

### R1. Smart Money Concepts (SMC) & Institutional Perception (The Eyes)
Expand Falcon's candlestick and pattern recognition to detect institutional liquidity dynamics:
- Algorithmically identify Order Blocks (unmitigated institutional footprints) and Fair Value Gaps (FVG imbalances across 3-candle sequences) on 15M and 1H timeframes.
- Detect session liquidity sweeps above/below previous Asian, London, and New York session highs and lows (manipulation wicks that sweep stops and reverse).
- Fuse macro calendar news impact, currency strength correlation (e.g. DXY vs. Gold XAUUSD), and live spreads into a single Composite Conviction Score (0–100%).

### R2. Autonomous Root-Cause Diagnostics & Regime Memory (The Brain)
Enable Falcon to perform automated forensic self-learning and adapt strategy rules after every closed trade:
- Automatically diagnose stop-out outcomes:
  - If swept by liquidity wick before reversal -> dynamically expand asset ATR stop buffer (+35%).
  - If momentum stalled during off-peak hours -> restrict asset to London/New York session overlap.
  - If reversed on macroeconomic release -> automatically tighten news blackout windows.
- Dynamic Strategy Health Scoring: quarantine underperforming strategies into paper evaluation mode while boosting allocation to resilient strategies.
- Maintain the autonomous loss-recovery progression (1 loss = 2.0x target, 2 losses = 4.0x target, hard $20 max entertaining loss ceiling across streak) with immediate reset on win.

### R3. Conversational AI Co-Pilot & Morning/Evening Briefings (The Voice)
Provide a natural language reasoning interface and automated scheduled intelligence briefings:
- REST API `/api/v1/copilot/query`: Accepts natural language questions from the trader ("Why did you trigger this Gold buy?", "What did you learn from yesterday's loss?", "What is our current streak?") and responds with precise technical, session, and risk context.
- Scheduled Telegram Briefings:
  - 07:00 UTC (London Open Briefing): Overnight Asian range summary, key structural levels, high-impact news schedule, and top 3 watchpoints.
  - 20:00 UTC (Daily Performance Review): Closed trades debrief, PnL, lessons committed to memory, and parameter adjustments tuned for the next session.

### R4. Advisory Safety & Broker Execution Isolation (The Shield)
Strictly preserve Falcon's fundamental non-custodial advisory principles:
- Zero broker automation (`order_send` = 0, `order_modify` = 0, `order_close` = 0).
- Purely read-only HTTP GET endpoints (no database mutations on queries).
- Flexible balance sizing ($50 to $10,000+) adhering strictly to the $20.00 cumulative loss ceiling across any losing streak.

## Verification Resources
The implementing team must test against and maintain the existing test suites:
- `backend/tests/unit/test_v10_dynamic_loss_recovery_and_capital.py` (54 tests passing)
- `backend/tests/unit/test_v10_smc_structure_engine.py` (28 tests passing)
- `backend/tests/unit/test_v10_regime_memory_and_diagnostics.py` (18 tests passing)
- `backend/tests/unit/test_v10_copilot_and_briefings.py` (18 tests passing)
- `backend/tests/unit/test_v10_phase3_capital_guardian.py` (23 tests passing)
- `backend/tests/unit/test_v10_phase4_guardian_integration.py` (25 tests passing)
- `mobile/test/` (Flutter test suite passing)

## Acceptance Criteria

### Institutional Perception (SMC)
- [ ] Fair Value Gap (FVG) and Order Block detection algorithms execute deterministically with comprehensive unit test coverage.
- [ ] Liquidity sweep detection accurately flags manipulation wicks across Asian/London/NY session boundaries.

### Cognitive Memory & Diagnostics
- [ ] When a trade closes with a loss, root-cause diagnostics automatically populate `reasonForExit`, `lessonLearned`, and adapt the strategy tuning profile.
- [ ] Consecutive loss progression (1 loss -> 2.0x, 2 losses -> 4.0x) and hard $20.00 streak ceiling remain strictly enforced.
- [ ] Winning trades reset the recovery multiplier to 1.0x and accumulated streak loss to $0.00.

### Conversational Co-Pilot & Telegram
- [ ] `/api/v1/copilot/query` endpoint responds accurately to trade rationale, loss diagnostics, and recovery status queries.
- [ ] London Open (07:00 UTC) and Daily Review (20:00 UTC) briefings generate complete structured summaries without crashing.

### Regression & Deployment
- [ ] All Python unit and integration tests pass with zero regressions.
- [ ] Mobile Flutter test suite passes with zero regressions.
- [ ] Backend deploys cleanly to Fly.io (`https://falcon-api-tejiri.fly.dev/`).
