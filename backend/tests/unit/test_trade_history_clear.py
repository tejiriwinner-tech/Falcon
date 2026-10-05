"""Tests for clearing finished trade history while keeping active trades."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage
from app.schemas.trade_journal import TradeJournalCreate


def _payload(status: str, result: str) -> TradeJournalCreate:
    return TradeJournalCreate(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.1,
        stopLoss=1.09,
        takeProfit=1.12,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=datetime.now(timezone.utc),
        reasonForEntry="test",
        status=status,
        result=result,
    )


def test_clear_history_keeps_active_trades():
    storage = InMemoryTradeJournalStorage()
    storage.create_trade(_payload("CLOSED", "WIN"))
    storage.create_trade(_payload("CLOSED", "LOSS"))
    storage.create_trade(_payload("EXPIRED", "EXPIRED"))
    storage.create_trade(_payload("OPEN", "OPEN"))
    storage.create_trade(_payload("PENDING", "PENDING"))

    deleted = storage.clear_history()

    assert deleted == 3
    remaining = {t.status for t in storage.list_trades()}
    assert remaining == {"OPEN", "PENDING"}


def test_clear_history_endpoint_route_not_shadowed(monkeypatch):
    from main import app
    from app.core.repository import trade_journal_repository as mod

    monkeypatch.setattr(mod.trade_journal_repository, "clear_history", lambda: 2)
    client = TestClient(app)
    resp = client.delete("/api/v1/trade-journal/history")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2
