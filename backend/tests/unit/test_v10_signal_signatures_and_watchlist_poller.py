"""
Unit tests for Falcon Persistent Signal Signatures & Watchlist Poller Service (V10).
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.core.repository.signal_signature_repository import (
    SignalSignatureRepository,
    InMemorySignalSignatureStorage,
    format_signature_key,
    parse_signature_key,
    signal_signature_repository,
)
from app.core.services.signal_service import SignalService, canonical_signal_signature
from app.core.services.watchlist_poller_service import WatchlistPollerService
from app.schemas.signal_candidate import (
    SignalCandidate,
    CandidateDirection,
    CandidateStatus,
    CandidateMarketSnapshot,
    ConfidenceBreakdown,
)
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus


def _make_candidate(cand_id, symbol, direction, entry, sl, tp, now, readiness=90.0, confidence=90):
    return SignalCandidate(
        id=cand_id,
        strategyId="momentum-breakout",
        strategyName="Momentum Breakout",
        strategyVersion="1.0",
        strategyGrade="A",
        strategyScore=85,
        symbol=symbol,
        direction=direction,
        entryPrice=entry,
        stopLoss=sl,
        takeProfit=tp,
        confidence=confidence,
        readinessScore=readiness,
        riskReward=2.0,
        status=CandidateStatus.APPROVED,
        generatedAt=now,
        reasons=[],
        conditions=[],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Normal",
            session="London",
            spread=1.0,
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=80,
            strategyScore=85,
            sessionScore=90,
            sentimentScore=80,
            newsScore=85,
        ),
        evaluationDurationMs=10,
        marketDataAgeSeconds=5,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )


def test_signature_key_format_and_parse():
    key = format_signature_key("EUR/USD", "BUY", 1.0850, 1.0810, 1.0930)
    assert key == "EURUSD:BUY:1.0850:1.0810:1.0930"

    parsed = parse_signature_key(key)
    assert parsed is not None
    assert parsed == ("EURUSD", "BUY", 1.0850, 1.0810, 1.0930)

    # Gold XAU/USD test
    gold_key = format_signature_key("XAUUSD", "SELL", 2750.50, 2760.00, 2730.00)
    assert gold_key == "XAUUSD:SELL:2750.5000:2760.0000:2730.0000"


def test_in_memory_signal_signature_storage():
    storage = InMemorySignalSignatureStorage()
    assert storage.get_all_signatures() == set()

    key = format_signature_key("XAUUSD", "BUY", 2700.0, 2690.0, 2720.0)
    storage.record_signature(key, "XAUUSD", "BUY", 2700.0, 2690.0, 2720.0, status="HOLD")

    assert storage.has_signature(key) is True
    assert key in storage.get_all_signatures()

    sig_data = storage.get_signature(key)
    assert sig_data["symbol"] == "XAUUSD"
    assert sig_data["status"] == "HOLD"

    updated = storage.update_status(key, "ACTIVE")
    assert updated is True
    assert storage.get_signature(key)["status"] == "ACTIVE"


def test_signal_signature_repository_operations():
    repo = SignalSignatureRepository()
    repo.clear()

    key = repo.record_signature("GBPUSD", "SELL", 1.3000, 1.3040, 1.2920, status="HOLD")
    assert repo.has_signature("GBPUSD", "SELL", 1.3000, 1.3040, 1.2920) is True

    all_tuples = repo.get_all_signature_tuples()
    assert ("GBPUSD", "SELL", 1.3000, 1.3040, 1.2920) in all_tuples

    repo.update_status("GBPUSD", "SELL", 1.3000, 1.3040, 1.2920, "ACTIVE")
    assert repo.has_signature("GBPUSD", "SELL", 1.3000, 1.3040, 1.2920) is True


def test_signal_service_persists_and_deduplicates():
    signal_signature_repository.clear()
    service = SignalService()
    service._historical_triggered_signatures.clear()

    now = datetime.now(timezone.utc)
    cand = _make_candidate("cand_dedup_01", "XAUUSD", CandidateDirection.BUY, 2700.00, 2690.00, 2720.00, now)
    decision = MagicMock()
    decision.candidateId = "cand_dedup_01"
    decision.status = DecisionStatus.APPROVED
    decision.confidence = 90

    mock_mission = MagicMock()
    mock_mission.id = "mission_001"

    with patch("app.core.repository.mission_repository.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.repository.mission_repository.mission_repository.get_mission_artifacts", return_value={"candidates": [cand], "decisions": [decision]}), \
         patch("app.core.repository.trade_journal_repository.trade_journal_repository.list_trades", return_value=[]):

        resp = service.build_signals(force_refresh=True)
        assert len(resp.signals) == 1
        assert resp.signals[0].symbol == "XAUUSD"

        # Verify signature was persisted in repository
        assert signal_signature_repository.has_signature("XAUUSD", "BUY", 2700.0, 2690.0, 2720.0) is True

        # Once resolved/completed, subsequent runs across service restarts will deduplicate
        signal_signature_repository.record_signature("XAUUSD", "BUY", 2700.0, 2690.0, 2720.0, status="EXPIRED")
        service2 = SignalService()
        assert ("XAUUSD", "BUY", 2700.0, 2690.0, 2720.0) in service2._historical_triggered_signatures
        resp2 = service2.build_signals(force_refresh=True)
        # Because signature is resolved in repo, it won't duplicate or recreate as active/hold
        assert len(resp2.signals) == 0


def test_watchlist_poller_cycle():
    poller = WatchlistPollerService(poll_interval_seconds=1)
    
    with patch("app.core.services.session_budget_manager.session_budget_manager.is_active", return_value=True), \
         patch("app.core.services.signal_service.signal_service.build_signals") as mock_build:
        
        mock_resp = MagicMock()
        mock_resp.signals = []
        mock_build.return_value = mock_resp

        result = asyncio.run(poller.poll_once())
        assert result["active_count"] == 0
        assert result["hold_count"] == 0
        assert poller._stats["cycles"] == 1

    status = poller.get_status()
    assert status["is_running"] is False
    assert status["stats"]["cycles"] == 1
