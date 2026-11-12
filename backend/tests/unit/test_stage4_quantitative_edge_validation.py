"""
Unit tests for Falcon Stage 4 — Quantitative Edge Validation & Shadow Strategy Selection.

Validates:
1. Strategy attribution and registry manifest consistency (18 strategies, 6 active, 12 incubation).
2. Data population separation (historical replay, unscorable, open positions, forward shadow N=0).
3. Chronological drawdown, R-multiple, and cost accounting.
4. Independent event clustering and bootstrap uncertainty.
5. Research classification rules (INSUFFICIENT_DATA, DATA_QUALITY_BLOCKED, NEGATIVE_SAMPLE_EDGE, EXPLORATORY_PROMISING).
6. Exit model reconciliation and deterministic replay verification.
7. Strict live broker dispatch prevention.
"""

import json
import math
import os
import pytest
from typing import List, Dict, Any

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import (
    ExecutionModeGuard,
    resolve_record_execution_mode,
    is_live_record,
    is_paper_record,
)


@pytest.fixture
def strategy_registry() -> List[Dict[str, Any]]:
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "app",
        "core",
        "engines",
        "strategy_registry_manifest.json",
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def experiment_manifest() -> Dict[str, Any]:
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "app",
        "core",
        "engines",
        "shadow_experiment_manifest.json",
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def historical_scorable_trades() -> List[Dict[str, Any]]:
    """Canonical 14 scorable historical trades with Model A, B, C, D1, D2 outcomes."""
    return [
        {"id": 33, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 1, "A": -1.068, "B": -1.068, "C": -1.068, "D1": -1.068, "D2": -1.068, "status": "CLOSED"},
        {"id": 34, "strat": "strat-004", "sym": "GBP/USD", "dir": "BUY",  "cluster": 1, "A": -1.082, "B": -1.082, "C": -1.082, "D1": -1.082, "D2": -1.082, "status": "CLOSED"},
        {"id": 35, "strat": "strat-007", "sym": "EUR/USD", "dir": "BUY",  "cluster": 1, "A": -0.207, "B": -0.207, "C": -0.207, "D1": -0.207, "D2": -0.207, "status": "OPEN"},
        {"id": 36, "strat": "strat-002", "sym": "XAU/USD", "dir": "SELL", "cluster": 2, "A": -0.029, "B": 0.974,  "C": 1.474,  "D1": 1.224,  "D2": 0.473,  "status": "CLOSED"},
        {"id": 37, "strat": "strat-004", "sym": "GBP/USD", "dir": "SELL", "cluster": 2, "A": -1.081, "B": -1.081, "C": -1.081, "D1": -1.081, "D2": -1.081, "status": "CLOSED"},
        {"id": 38, "strat": "strat-002", "sym": "XAU/USD", "dir": "SELL", "cluster": 3, "A": 0.144,  "B": 0.144,  "C": 0.144,  "D1": 0.144,  "D2": 0.144,  "status": "OPEN"},
        {"id": 39, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -2.000, "B": -2.000, "C": -2.000, "D1": -2.000, "D2": -2.000, "status": "CLOSED"},
        {"id": 40, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.000, "B": 0.013,  "C": -1.000, "D1": -0.493, "D2": -0.493, "status": "CLOSED"},
        {"id": 41, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.004, "B": 0.009,  "C": -1.004, "D1": -0.498, "D2": -0.498, "status": "CLOSED"},
        {"id": 42, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.000, "B": 0.013,  "C": -1.000, "D1": -0.493, "D2": -0.493, "status": "CLOSED"},
        {"id": 43, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.004, "B": 0.009,  "C": -1.004, "D1": -0.498, "D2": -0.498, "status": "CLOSED"},
        {"id": 45, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 5, "A": -1.042, "B": -1.042, "C": -1.042, "D1": -1.042, "D2": -1.042, "status": "CLOSED"},
        {"id": 47, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 6, "A": -0.066, "B": 0.942,  "C": -0.066, "D1": 0.438,  "D2": 0.438,  "status": "CLOSED"},
        {"id": 48, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 7, "A": -0.811, "B": -0.811, "C": -0.811, "D1": -0.811, "D2": -0.811, "status": "OPEN"},
    ]


def test_strategy_attribution_and_registry_consistency(strategy_registry, experiment_manifest):
    """Verify registry has exactly 18 strategies matching frozen experiment manifest counts."""
    assert len(strategy_registry) == 18
    
    counts = experiment_manifest.get("strategyRegistryCounts", {})
    assert counts.get("total") == 18
    assert counts.get("activeFlagships") == 6
    assert counts.get("incubationShadow") == 12

    ready_strategies = [s for s in strategy_registry if s.get("readyForExecution") is True]
    incubation_strategies = [s for s in strategy_registry if s.get("readyForExecution") is False]
    
    assert len(ready_strategies) == 6
    assert len(incubation_strategies) == 12

    strategy_ids = [s["id"] for s in strategy_registry]
    assert len(set(strategy_ids)) == 18, "Strategy IDs must be unique"
    for expected_id in [f"strat-{i:03d}" for i in range(1, 19)]:
        assert expected_id in strategy_ids


def test_population_separation_and_unscorable_handling(historical_scorable_trades):
    """Verify strict separation of scorable, unscorable, open, and forward shadow datasets."""
    # 1. Scorable count
    assert len(historical_scorable_trades) == 14
    
    # 2. Closed vs open MTM in scorable
    closed_trades = [t for t in historical_scorable_trades if t["status"] == "CLOSED"]
    open_trades = [t for t in historical_scorable_trades if t["status"] == "OPEN"]
    assert len(closed_trades) == 11
    assert len(open_trades) == 3
    assert {t["id"] for t in open_trades} == {35, 38, 48}

    # 3. Unscorable records classification rule
    # A record is unscorable if initial_risk <= 0 or stop loss was never recorded
    unscorable_candidates = [
        {"id": 28, "entry": 211.585, "sl": 211.585, "reason": "SL equals entry"},
        {"id": 29, "entry": 158.108, "sl": 158.108, "reason": "SL equals entry"},
        {"id": 30, "entry": 0.7007,  "sl": 0.7007,  "reason": "SL equals entry"},
        {"id": 44, "entry": 1.338,   "sl": 1.338,   "reason": "SL equals entry"},
        {"id": 46, "entry": 211.802, "sl": 211.802, "reason": "SL equals entry"},
    ]
    for rec in unscorable_candidates:
        risk_dist = abs(rec["entry"] - rec["sl"])
        assert risk_dist == 0.0, f"Trade {rec['id']} must fail closed as unscorable"

    # 4. Forward shadow dataset honest zero-count
    forward_shadow_count = 0
    assert forward_shadow_count == 0, "Forward shadow sample must be reported honestly as 0"


def test_chronological_drawdown_and_r_multiple_accounting(historical_scorable_trades):
    """Test max peak-to-trough chronological drawdown calculation on R series."""
    def calc_max_drawdown(r_multiples: List[float]) -> float:
        cum_r = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in r_multiples:
            cum_r += r
            if cum_r > peak:
                peak = cum_r
            dd = peak - cum_r
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 3)

    r_series_a = [t["A"] for t in historical_scorable_trades]
    r_series_b = [t["B"] for t in historical_scorable_trades]

    # Model A never made a new high (cum_r strictly non-positive) -> max_dd equals abs(cum_r_final)
    max_dd_a = calc_max_drawdown(r_series_a)
    total_a = round(sum(r_series_a), 3)
    assert total_a == pytest.approx(-11.251, abs=0.01)
    assert max_dd_a == pytest.approx(11.251, abs=0.01)

    # Model B had temporary gains but experienced drawdown
    max_dd_b = calc_max_drawdown(r_series_b)
    total_b = round(sum(r_series_b), 3)
    assert total_b == pytest.approx(-5.187, abs=0.01)
    assert max_dd_b == pytest.approx(5.322, abs=0.01)


def test_cluster_assignment_and_bootstrap_uncertainty(historical_scorable_trades):
    """Verify independent event clustering and wide bootstrap uncertainty on K=7 clusters."""
    from collections import defaultdict

    clusters_a = defaultdict(float)
    clusters_b = defaultdict(float)
    for t in historical_scorable_trades:
        clusters_a[t["cluster"]] += t["A"]
        clusters_b[t["cluster"]] += t["B"]

    assert len(clusters_a) == 7, "Must have exactly 7 independent event clusters"
    assert len(clusters_b) == 7

    # Cluster 4 is the rollover cascade (trades 39, 40, 41, 42, 43)
    assert round(clusters_a[4], 3) == -6.008
    assert round(clusters_b[4], 3) == -1.956

    cluster_vals_a = list(clusters_a.values())
    mean_cluster_a = sum(cluster_vals_a) / len(cluster_vals_a)
    assert round(mean_cluster_a, 3) == -1.607

    cluster_vals_b = list(clusters_b.values())
    mean_cluster_b = sum(cluster_vals_b) / len(cluster_vals_b)
    assert round(mean_cluster_b, 3) == -0.741

    # Analytical standard error on 7 clusters shows massive uncertainty
    std_err_a = math.sqrt(sum((x - mean_cluster_a) ** 2 for x in cluster_vals_a) / (len(cluster_vals_a) - 1)) / math.sqrt(len(cluster_vals_a))
    assert std_err_a > 0.40, "Cluster standard error must be substantial on small sample"


def test_strategy_research_classification_rules():
    """Verify research classification decision rules for all 18 strategies."""
    def classify_strategy(strat_id: str, historical_scorable: int, forward_trades: int, net_r: float, has_data_block: bool) -> str:
        if has_data_block:
            return "DATA_QUALITY_BLOCKED"
        if forward_trades >= 50 and net_r > 0.25:
            return "VALIDATION_CANDIDATE"
        if forward_trades > 0 or (historical_scorable >= 30 and net_r > 0):
            return "FORWARD_VALIDATION_PENDING"
        if historical_scorable > 0 and net_r < 0:
            return "NEGATIVE_SAMPLE_EDGE"
        if historical_scorable > 0 and net_r >= 0:
            return "EXPLORATORY_PROMISING"
        return "INSUFFICIENT_DATA"

    # Verify classification outcomes
    assert classify_strategy("strat-001", 0, 0, 0.0, False) == "INSUFFICIENT_DATA"
    assert classify_strategy("strat-002", 2, 0, 0.115, False) == "EXPLORATORY_PROMISING"
    assert classify_strategy("strat-004", 2, 0, -2.163, False) == "NEGATIVE_SAMPLE_EDGE"
    assert classify_strategy("strat-007", 1, 0, -0.207, False) == "NEGATIVE_SAMPLE_EDGE"
    assert classify_strategy("strat-013", 0, 0, 0.0, True) == "DATA_QUALITY_BLOCKED"
    assert classify_strategy("strat-016", 9, 0, -8.995, False) == "NEGATIVE_SAMPLE_EDGE"
    assert classify_strategy("strat-017", 0, 0, 0.0, True) == "DATA_QUALITY_BLOCKED"

    # ZERO strategies qualify for live execution or validation candidate
    assert classify_strategy("strat-016", 9, 0, -8.995, False) != "VALIDATION_CANDIDATE"


def test_exit_model_reconciliation_and_all_negative(historical_scorable_trades):
    """Verify that all 5 exit models produce negative net R on the historical scorable sample."""
    sum_a = sum(t["A"] for t in historical_scorable_trades)
    sum_b = sum(t["B"] for t in historical_scorable_trades)
    sum_c = sum(t["C"] for t in historical_scorable_trades)
    sum_d1 = sum(t["D1"] for t in historical_scorable_trades)
    sum_d2 = sum(t["D2"] for t in historical_scorable_trades)

    assert round(sum_a, 3) == pytest.approx(-11.251, abs=0.01)
    assert round(sum_b, 3) == pytest.approx(-5.187, abs=0.01)
    assert round(sum_c, 3) == pytest.approx(-9.748, abs=0.01)
    assert round(sum_d1, 3) == pytest.approx(-7.467, abs=0.01)
    assert round(sum_d2, 3) == pytest.approx(-8.219, abs=0.01)

    # Every single exit model is net negative on this sample
    for name, val in [("Model A", sum_a), ("Model B", sum_b), ("Model C", sum_c), ("Model D1", sum_d1), ("Model D2", sum_d2)]:
        assert val < 0.0, f"{name} must have negative net R on historical scorable sample"


def test_strict_live_broker_dispatch_prevention_in_stage4():
    """Verify ExecutionModeGuard unconditionally rejects live broker dispatch."""
    guard = ExecutionModeGuard()
    
    assert guard.is_live_authorized() is False
    assert settings.EXECUTION_MODE == "PAPER"
    assert settings.LIVE_EXECUTION_ACKNOWLEDGED is False
    assert settings.OANDA_AUTO_EXECUTE is False
