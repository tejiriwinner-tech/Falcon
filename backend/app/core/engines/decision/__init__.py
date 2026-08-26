"""
Falcon Phase 7 — Decision Intelligence Engine Package

This package contains the modular Decision Intelligence Engine introduced in Phase 7.
It upgrades the existing DecisionEngine (Stage 6 of the pipeline) from a flat rule-tree
into a fully modular, explainable, and deterministic intelligence system.

Sub-packages:
    evaluators/           — Independent technical evaluators (Trend, Structure, etc.)
    strategy_evaluators/  — Strategy-specific rule validators

Modules:
    context_builder.py    — Builds the immutable DecisionContext
    risk_gate.py          — Risk veto layer (PASS / WARN / VETO)
    confidence_engine.py  — Weighted multi-factor confidence scoring
    decision_generator.py — Produces the final GeneratedDecision
    reasoning_generator.py — Converts evidence into human-readable reasoning chains
"""
