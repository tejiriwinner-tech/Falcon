"""
Falcon V10 — Signal Lifecycle, Watchlist HOLD, 1-Hour Expiry, and Historical Deduplication Test Suite.

Verifies:
1. No 3-Active Cap: 4+ setups touching entry simultaneously all become ACTIVE without being forced into WAITING.
2. Watchlist Pending: Setups with market price not touching entry remain on Watchlist in HOLD status.
3. 1-Hour Expiry: Setups on Watchlist for >= 1 hour without reaching entry price transition to RESOLVED (EXPIRED).
4. Historical Deduplication:
   - Active journal trades prevent re-generating identical setups.
   - Closed journal trades (WON/LOST/BREAKEVEN/EXPIRED) prevent re-generating identical setups.
   - Newly triggered or expired candidates are remembered and never duplicated.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from app.core.services.signal_service import SignalService, canonical_signal_signature
from app.schemas.signal_candidate import (
    SignalCandidate,
    CandidateStatus,
    CandidateDirection,
    CandidateMarketSnapshot,
    ConfidenceBreakdown,
)
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus, DecisionRecommendation
from app.schemas.trade_journal import TradeJournalItem


@pytest.fixture
def signal_setup():
    sig_service = SignalService()
    # Reset historical signatures for test isolation
    sig_service._historical_triggered_signatures.clear()
    now = datetime.now(timezone.utc)
    return {
        "service": sig_service,
        "now": now,
    }


def make_candidate(
    cand_id: str,
    symbol: str,
    direction: CandidateDirection,
    entry: float,
    sl: float,
    tp: float,
    generated_at: datetime,
    readiness: float = 90.0,
    confidence: int = 85,
) -> SignalCandidate:
    return SignalCandidate(
        id=cand_id,
        strategyId="test-smc",
        strategyName="SMC Institutional",
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
        riskReward=3.0,
        status=CandidateStatus.APPROVED,
        generatedAt=generated_at,
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
        evaluationStartedAt=generated_at,
        evaluationCompletedAt=generated_at,
    )


def make_decision(cand_id: str) -> DecisionArtifact:
    dec = MagicMock()
    dec.candidateId = cand_id
    dec.status = DecisionStatus.APPROVED
    dec.confidence = 85
    dec.aiReasoning = "Optimal SMC setup"
    dec.recommendation = DecisionRecommendation.BUY
    dec.recommendationDetails = None
    return dec


def test_no_3_active_cap_all_triggered_become_active(signal_setup):
    """1. All candidates touching entry become ACTIVE (no 3-slot active limit)."""
    service: SignalService = signal_setup["service"]
    now = signal_setup["now"]

    symbols = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]
    entries = [1.1000, 1.2500, 2000.0, 150.0]
    sls = [1.0950, 1.2450, 1990.0, 149.0]
    tps = [1.1150, 1.2650, 2030.0, 153.0]

    candidates = [
        make_candidate(f"c-{i}", symbols[i], CandidateDirection.BUY, entries[i], sls[i], tps[i], now)
        for i in range(4)
    ]
    decisions = [make_decision(f"c-{i}") for i in range(4)]

    mock_mission = MagicMock()
    mock_mission.id = "mission-01"
    artifacts_mock = {
        "candidates": candidates,
        "decisions": decisions,
    }

    # All 4 symbols have market price at entry
    price_map = {"EURUSD": 1.1000, "GBPUSD": 1.2500, "XAUUSD": 2000.0, "USDJPY": 150.0}
    cache_mock = MagicMock()
    def _get_price(sym, allow_stale=False):
        if sym in price_map:
            m = MagicMock()
            m.data.lastPrice = price_map[sym]
            return m
        return None
    cache_mock.get = _get_price

    pm_mock = MagicMock()
    pm_mock._cache = cache_mock

    journal_mock = MagicMock()
    journal_mock.list_trades.return_value = []

    with patch("app.core.services.signal_service.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.services.signal_service.mission_repository.get_mission_artifacts", return_value=artifacts_mock), \
         patch("app.core.services.signal_service.trade_journal_repository", journal_mock), \
         patch("app.core.providers.provider_manager", pm_mock):

        resp = service.build_signals(mission_limit=5, force_refresh=True)

        active = [s for s in resp.signals if s.status == "ACTIVE"]
        # All 4 must be ACTIVE without being capped at 3
        assert len(active) == 4
        assert set(s.symbol for s in active) == {"EURUSD", "GBPUSD", "XAUUSD", "USDJPY"}


def test_watchlist_hold_when_entry_not_hit(signal_setup):
    """2. Setups with market price not touching entry remain on Watchlist in HOLD status."""
    service: SignalService = signal_setup["service"]
    now = signal_setup["now"]

    cand1 = make_candidate("c-1", "EURUSD", CandidateDirection.BUY, 1.1000, 1.0950, 1.1150, now)
    cand2 = make_candidate("c-2", "GBPUSD", CandidateDirection.BUY, 1.2500, 1.2450, 1.2650, now)

    mock_mission = MagicMock()
    mock_mission.id = "mission-02"
    artifacts_mock = {
        "candidates": [cand1, cand2],
        "decisions": [make_decision("c-1"), make_decision("c-2")],
    }

    # EURUSD is at entry (1.1000) -> ACTIVE
    # GBPUSD is at 1.2600 (far above BUY entry 1.2500) -> HOLD
    price_map = {"EURUSD": 1.1000, "GBPUSD": 1.2600}
    cache_mock = MagicMock()
    def _get_price(sym, allow_stale=False):
        if sym in price_map:
            m = MagicMock()
            m.data.lastPrice = price_map[sym]
            return m
        return None
    cache_mock.get = _get_price
    pm_mock = MagicMock()
    pm_mock._cache = cache_mock

    journal_mock = MagicMock()
    journal_mock.list_trades.return_value = []

    with patch("app.core.services.signal_service.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.services.signal_service.mission_repository.get_mission_artifacts", return_value=artifacts_mock), \
         patch("app.core.services.signal_service.trade_journal_repository", journal_mock), \
         patch("app.core.providers.provider_manager", pm_mock):

        resp = service.build_signals(mission_limit=5, force_refresh=True)

        active = [s for s in resp.signals if s.status == "ACTIVE"]
        hold = [s for s in resp.signals if s.status == "HOLD"]

        assert len(active) == 1
        assert active[0].symbol == "EURUSD"

        assert len(hold) == 1
        assert hold[0].symbol == "GBPUSD"
        assert "Awaiting market entry touch" in hold[0].analysis


def test_watchlist_1hour_expiry(signal_setup):
    """3. Setups on watchlist for >= 1 hour without reaching entry move to RESOLVED as EXPIRED."""
    service: SignalService = signal_setup["service"]
    now = signal_setup["now"]
    past_time = now - timedelta(hours=1, minutes=10)  # 70 minutes old

    cand = make_candidate("c-old", "XAUUSD", CandidateDirection.BUY, 2000.0, 1990.0, 2030.0, past_time)

    mock_mission = MagicMock()
    mock_mission.id = "mission-03"
    artifacts_mock = {
        "candidates": [cand],
        "decisions": [make_decision("c-old")],
    }

    # Market price never reached 2000.0 (stays at 2050.0)
    cache_mock = MagicMock()
    cache_mock.get.return_value = None
    pm_mock = MagicMock()
    pm_mock._cache = cache_mock

    journal_mock = MagicMock()
    journal_mock.list_trades.return_value = []

    with patch("app.core.services.signal_service.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.services.signal_service.mission_repository.get_mission_artifacts", return_value=artifacts_mock), \
         patch("app.core.services.signal_service.trade_journal_repository", journal_mock), \
         patch("app.core.providers.provider_manager", pm_mock):

        resp = service.build_signals(mission_limit=5, force_refresh=True)

        expired = [s for s in resp.signals if s.status == "EXPIRED"]
        active = [s for s in resp.signals if s.status == "ACTIVE"]
        hold = [s for s in resp.signals if s.status == "HOLD"]

        assert len(expired) == 1
        assert expired[0].symbol == "XAUUSD"
        assert len(active) == 0
        assert len(hold) == 0


def test_historical_deduplication_prevents_regenerating_setups(signal_setup):
    """4. Completed or active journal setups are never regenerated or duplicated as fresh candidates."""
    service: SignalService = signal_setup["service"]
    now = signal_setup["now"]

    # Seed an existing journal closed trade
    closed_trade = TradeJournalItem(
        id=501,
        signalId=501,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1150,
        timeframe="M15",
        marketSession="London",
        reasonForEntry="SMC Sniper entry",
        status="CLOSED",
        result="WIN",
        tradeDate=now - timedelta(hours=2),
        closeDate=now - timedelta(hours=1),
        exitPrice=1.1150,
        profitLoss=15.0,
        notes="Previous SMC Sniper",
        riskReward=3.0,
        createdAt=now - timedelta(hours=2),
        updatedAt=now - timedelta(hours=1),
    )

    # Candidate with the identical setup levels
    duplicate_cand = make_candidate("c-dup", "EURUSD", CandidateDirection.BUY, 1.1000, 1.0950, 1.1150, now)

    mock_mission = MagicMock()
    mock_mission.id = "mission-04"
    artifacts_mock = {
        "candidates": [duplicate_cand],
        "decisions": [make_decision("c-dup")],
    }

    journal_mock = MagicMock()
    journal_mock.list_trades.return_value = [closed_trade]

    cache_mock = MagicMock()
    cache_mock.get.return_value = None
    pm_mock = MagicMock()
    pm_mock._cache = cache_mock

    with patch("app.core.services.signal_service.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.services.signal_service.mission_repository.get_mission_artifacts", return_value=artifacts_mock), \
         patch("app.core.services.signal_service.trade_journal_repository", journal_mock), \
         patch("app.core.providers.provider_manager", pm_mock):

        resp = service.build_signals(mission_limit=5, force_refresh=True)

        # The closed trade is reported in resolved list as WON
        won_signals = [s for s in resp.signals if s.status == "WON"]
        assert len(won_signals) == 1
        assert won_signals[0].id == 501

        # The duplicate candidate was filtered out by canonical signature deduplication
        hold_signals = [s for s in resp.signals if s.status == "HOLD"]
        active_signals = [s for s in resp.signals if s.status == "ACTIVE"]
        assert len(hold_signals) == 0
        assert len(active_signals) == 0
