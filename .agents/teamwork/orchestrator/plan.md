# Orchestrator Plan: Falcon Trading Intelligence

## Objective
Implement Phase 2 (Smart Money Institutional Perception & Regime Memory) and Phase 3 (Conversational AI Co-Pilot & Telegram Briefings), building on top of the verified Phase 1 foundation, with 100% test pass rate, adversarial validation, and deployment readiness.

## Step-by-Step Execution Plan

### Step 0: Parallel Survey (Exploration Track)
- Dispatch 3 Explorers in parallel:
  - **Explorer 1 (SMC & Perception)**: Investigate SMC detection (Order Blocks, FVG, session liquidity sweeps, Asian/London/NY manipulation wicks, Composite Conviction Score) and existing tests (`test_v10_smc_structure_engine.py`).
  - **Explorer 2 (Brain & Voice)**: Investigate autonomous diagnostics, regime memory, strategy health scoring, loss-recovery progression, copilot endpoint (`/api/v1/copilot/query`), scheduled Telegram briefings, and tests (`test_v10_regime_memory_and_diagnostics.py`, `test_v10_copilot_and_briefings.py`, `test_v10_dynamic_loss_recovery_and_capital.py`).
  - **Explorer 3 (Integration, Mobile & Deployment)**: Investigate mobile Flutter tests, backend tests, deployment files (Fly.io `fly.toml`, Dockerfile, fly deployment configuration), and non-custodial advisory invariants.
- Synthesize findings into `PROJECT.md` at project root with architecture, feature inventory, code layout, and milestones.

### Step 1: Decomposition & Interface Contracts
- Establish milestones with clear contracts:
  - Milestone 1: SMC Structure Engine & Liquidity Sweep Detection & Composite Conviction Scoring.
  - Milestone 2: Autonomous Root-Cause Diagnostics, Regime Memory, Dynamic Strategy Health & Loss Recovery Progression.
  - Milestone 3: Conversational AI Co-Pilot API (`/api/v1/copilot/query`) & Scheduled Telegram Briefings (London Open 07:00 UTC & Daily Review 20:00 UTC).
  - Milestone 4: Full E2E Integration, Regression Testing (Python & Flutter), and Fly.io Deployment Verification.

### Step 2: Milestone Iteration Loops (Worker -> Reviewer -> Challenger -> Auditor)
- For each milestone:
  - Dispatch Worker with precise boundaries, requirements, and anti-cheat constraints.
  - Dispatch Reviewers and Challengers to verify correctness, test passing, and adversarial robustness.
  - Dispatch Forensic Auditor for integrity validation.
  - Evaluate gate conditions in `GATE_STATUS.md`.

### Step 3: Final Verification & Deployment
- Verify all unit and integration test suites pass with 0 regressions.
- Verify Flutter mobile tests pass with 0 regressions.
- Verify Fly.io clean deployment readiness.
- Report complete results to Sentinel parent.
