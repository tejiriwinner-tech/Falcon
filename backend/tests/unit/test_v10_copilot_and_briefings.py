"""
Falcon V10 Unit Tests: Conversational AI Co-Pilot & Scheduled Briefings (Pillar 3)

Validates:
1. Natural Language Intent Reasoning:
   - Trade Rationale queries ("Why did you trigger this Gold buy?", "Why SELL GBP/USD?")
   - Streak & Risk queries ("What is our current streak?", "How much can we lose?")
   - Forensic Learning queries ("What did you learn from the last loss?")
   - Strategy & Capital Architecture queries ("What strategies are active?", "What is active capital?")
   - General Guidance and fallback queries.
2. Scheduled Briefings:
   - London Open (07:00 UTC): Asian session ranges, institutional Order Blocks & FVGs, macro calendar events, top 3 watchpoints.
   - Daily Performance Review (20:00 UTC): Executed trades, win rate, net PnL, streak headroom under $20 ceiling, forensic findings.
   - Latest briefing persistence & on-demand retrieval.
3. FastAPI REST Endpoints:
   - POST /api/v1/copilot/query
   - GET /api/v1/copilot/briefings/london-open
   - GET /api/v1/copilot/briefings/daily-review
   - GET /api/v1/copilot/briefings/latest
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.core.services.copilot_service import CopilotService, copilot_service
from app.core.services.briefing_service import BriefingService, briefing_service
from app.schemas.copilot import (
    BriefingType,
    CopilotQueryRequest,
    CopilotQueryResponse,
    IntelligenceBriefing,
)
from main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


# ── 1. Co-Pilot Natural Language Query Tests ─────────────────────────────────

class TestCopilotQueryIntents:
    """Tests natural language classification and deterministic domain reasoning."""

    def test_trade_rationale_gold_buy(self):
        """Query: 'Why did you trigger this Gold buy?'"""
        req = CopilotQueryRequest(query="Why did you trigger this Gold buy?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "TRADE_RATIONALE"
        assert resp.confidence >= 0.90
        assert "XAU/USD" in resp.response or "Gold" in resp.response
        assert "BUY" in resp.response
        assert "Smart Money Concepts" in resp.response or "SMC" in resp.response
        assert "Risk-to-Reward" in resp.response or "R:R" in resp.response

        # Context assertions
        assert resp.technical_context is not None
        assert resp.technical_context["symbol"] == "XAU/USD"
        assert resp.technical_context["direction"] == "BUY"
        assert resp.technical_context["entry_price"] > 0
        assert resp.technical_context["stop_loss"] < resp.technical_context["entry_price"]
        assert resp.technical_context["take_profit"] > resp.technical_context["entry_price"]

        assert resp.risk_context is not None
        assert resp.risk_context["max_entertaining_loss"] == 20.0
        assert "recovery_multiplier" in resp.risk_context

    def test_trade_rationale_gbp_sell(self):
        """Query: 'Why SELL GBP/USD?'"""
        req = CopilotQueryRequest(query="Why SELL GBP/USD?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "TRADE_RATIONALE"
        assert resp.confidence >= 0.90
        assert "GBP/USD" in resp.response
        assert "SELL" in resp.response

        assert resp.technical_context is not None
        assert resp.technical_context["symbol"] == "GBP/USD"
        assert resp.technical_context["direction"] == "SELL"
        assert resp.technical_context["stop_loss"] > resp.technical_context["entry_price"]
        assert resp.technical_context["take_profit"] < resp.technical_context["entry_price"]

    def test_trade_rationale_with_explicit_symbol(self):
        """Query with explicit symbol in request."""
        req = CopilotQueryRequest(query="Explain entry rationale and invalidation", symbol="EUR/USD")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "TRADE_RATIONALE"
        assert resp.technical_context["symbol"] == "EUR/USD"
        assert "EUR/USD" in resp.response

    def test_streak_and_recovery_status_query(self):
        """Query: 'What is our current streak and recovery status?'"""
        req = CopilotQueryRequest(query="What is our current streak and recovery status?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "STREAK_AND_RISK"
        assert resp.confidence >= 0.90
        assert "Streak" in resp.response
        assert "Multiplier" in resp.response
        assert "$20.00" in resp.response or "$20" in resp.response
        assert "Headroom" in resp.response or "headroom" in resp.response

        assert resp.risk_context is not None
        assert "consecutive_losses" in resp.risk_context
        assert "profit_recovery_multiplier" in resp.risk_context
        assert resp.risk_context["max_entertaining_loss"] == 20.0
        assert "loss_ceiling_headroom" in resp.risk_context

    def test_streak_how_much_can_we_lose_query(self):
        """Query: 'How much can we lose before circuit breaker?'"""
        req = CopilotQueryRequest(query="How much can we lose before circuit breaker?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "STREAK_AND_RISK"
        assert resp.risk_context is not None
        assert resp.risk_context["max_entertaining_loss"] == 20.0
        assert resp.risk_context["loss_ceiling_headroom"] >= 0.0

    def test_forensic_learning_query(self):
        """Query: 'What did you learn from the last loss?'"""
        req = CopilotQueryRequest(query="What did you learn from the last loss?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "FORENSIC_LEARNING"
        assert resp.confidence >= 0.90
        assert "Root Cause" in resp.response or "Diagnostic" in resp.response
        assert "Adaptive" in resp.response or "ATR" in resp.response

        assert resp.technical_context is not None
        assert "root_cause_diagnosis" in resp.technical_context
        assert "adaptive_stop_multiplier" in resp.technical_context
        assert resp.technical_context["adaptive_stop_multiplier"] >= 1.0

    def test_system_and_strategy_query(self):
        """Query: 'What strategies are active and what is active capital?'"""
        req = CopilotQueryRequest(query="What strategies are active and what is active capital?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "SYSTEM_AND_STRATEGY"
        assert resp.confidence >= 0.90
        assert "Capital" in resp.response
        assert "Strategies" in resp.response or "SMC Liquidity Hunter" in resp.response

        assert resp.technical_context is not None
        assert "active_strategies" in resp.technical_context
        assert len(resp.technical_context["active_strategies"]) >= 3
        assert "active_trading_capital" in resp.technical_context

    def test_general_inquiry_query(self):
        """Query: 'Hello Falcon, how can you help me today?'"""
        req = CopilotQueryRequest(query="Hello Falcon, how can you help me today?")
        resp = copilot_service.handle_query(req)

        assert resp.intent == "GENERAL_INQUIRY"
        assert "Falcon" in resp.response
        assert "Trade Rationale" in resp.response or "Risk" in resp.response


# ── 2. Scheduled Briefings Tests ─────────────────────────────────────────────

class TestScheduledBriefings:
    """Tests generation and formatting of pre-market and post-session briefings."""

    def test_generate_london_open_briefing(self):
        """Validates London Open briefing structure, market levels, and Telegram formatting."""
        briefing = briefing_service.generate_london_open_briefing()

        assert briefing.briefing_type == BriefingType.LONDON_OPEN
        assert "London Open" in briefing.title
        assert len(briefing.summary) > 20

        # Market levels must cover EUR/USD, GBP/USD, XAU/USD
        assert "EUR/USD" in briefing.market_levels
        assert "GBP/USD" in briefing.market_levels
        assert "XAU/USD" in briefing.market_levels

        eur = briefing.market_levels["EUR/USD"]
        assert eur["asian_high"] > eur["asian_low"]
        assert eur["range_pips"] > 0
        assert "bullish_order_block" in eur
        assert "bearish_order_block" in eur
        assert "liquidity_pools" in eur

        gold = briefing.market_levels["XAU/USD"]
        assert gold["asian_high"] > gold["asian_low"]
        assert gold["range_dollars"] > 0
        assert "fair_value_gap" in gold

        # Key insights / Top 3 watchpoints
        assert len(briefing.key_insights) >= 3
        assert any("Judas" in w or "Asian" in w for w in briefing.key_insights)

        # Risk state
        assert "consecutive_losses" in briefing.risk_state
        assert "loss_ceiling_headroom" in briefing.risk_state
        assert briefing.risk_state["max_entertaining_loss"] == 20.0

        # Formatted text
        assert "FALCON INTELLIGENCE BRIEFING: LONDON OPEN" in briefing.formatted_text
        assert "Asian Session Ranges & Key Levels" in briefing.formatted_text
        assert "Top 3 Watchpoints" in briefing.formatted_text
        assert "Active Risk State" in briefing.formatted_text

    def test_london_open_with_custom_quotes(self):
        """Validates that custom live quotes dynamically alter Asian ranges."""
        custom_quotes = {
            "EUR/USD": {
                "price": 1.0920,
                "asian_high": 1.0950,
                "asian_low": 1.0900,
            },
            "XAU/USD": {
                "price": 2680.00,
                "asian_high": 2690.00,
                "asian_low": 2675.00,
            },
        }
        briefing = briefing_service.generate_london_open_briefing(market_quotes=custom_quotes)

        eur = briefing.market_levels["EUR/USD"]
        assert eur["asian_high"] == 1.0950
        assert eur["asian_low"] == 1.0900
        assert eur["range_pips"] == 50.0

        gold = briefing.market_levels["XAU/USD"]
        assert gold["asian_high"] == 2690.00
        assert gold["asian_low"] == 2675.00
        assert gold["range_dollars"] == 15.00

    def test_generate_daily_review_briefing(self):
        """Validates Daily Performance Review briefing generation."""
        briefing = briefing_service.generate_daily_review_briefing()

        assert briefing.briefing_type == BriefingType.DAILY_REVIEW
        assert "Daily Performance Review" in briefing.title
        assert "market_levels" in briefing.model_dump()
        assert "session_trades" in briefing.market_levels
        assert "win_rate" in briefing.market_levels
        assert "net_pnl" in briefing.market_levels

        # Key insights should contain forensic analysis & parameter adjustments
        assert len(briefing.key_insights) >= 2
        assert any("Adaptive" in ins or "Stop" in ins or "Execution" in ins for ins in briefing.key_insights)

        # Formatted text
        assert "FALCON DAILY PERFORMANCE REVIEW" in briefing.formatted_text
        assert "Session Summary" in briefing.formatted_text
        assert "Streak & Recovery Status" in briefing.formatted_text
        assert "Adaptive Parameter Adjustments" in briefing.formatted_text

    def test_daily_review_with_custom_trade_journal_data(self):
        """Validates Daily Performance Review with explicit trade list."""
        journal_data = [
            {"result": "WIN", "profitLoss": 15.00},
            {"result": "WIN", "profitLoss": 12.50},
            {"result": "LOSS", "profitLoss": -7.50},
            {"result": "BREAKEVEN", "profitLoss": 0.00},
        ]
        briefing = briefing_service.generate_daily_review_briefing(trade_journal_data=journal_data)

        levels = briefing.market_levels
        assert levels["session_trades"] == 4
        assert levels["wins"] == 2
        assert levels["losses"] == 1
        assert levels["breakevens"] == 1
        assert levels["win_rate"] == 66.67
        assert levels["net_pnl"] == 20.00
        assert "+$20.00" in briefing.formatted_text

    def test_get_latest_briefing_persists(self):
        """Validates that get_latest_briefing() returns the most recently generated briefing."""
        lo = briefing_service.generate_london_open_briefing()
        latest = briefing_service.get_latest_briefing()
        assert latest.briefing_type == BriefingType.LONDON_OPEN
        assert latest.title == lo.title

        dr = briefing_service.generate_daily_review_briefing()
        latest2 = briefing_service.get_latest_briefing()
        assert latest2.briefing_type == BriefingType.DAILY_REVIEW
        assert latest2.title == dr.title


# ── 3. REST API Endpoint Integration Tests ───────────────────────────────────

class TestCopilotApiEndpoints:
    """Validates FastAPI HTTP endpoints and schema serialization."""

    def test_api_query_copilot_endpoint(self, client: TestClient):
        """POST /api/v1/copilot/query"""
        payload = {
            "query": "Why did you trigger this Gold buy?",
            "symbol": "XAU/USD",
        }
        res = client.post("/api/v1/copilot/query", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["query"] == payload["query"]
        assert data["intent"] == "TRADE_RATIONALE"
        assert data["confidence"] >= 0.90
        assert "response" in data
        assert data["technical_context"]["symbol"] == "XAU/USD"
        assert data["risk_context"]["max_entertaining_loss"] == 20.0

    def test_api_query_streak_endpoint(self, client: TestClient):
        """POST /api/v1/copilot/query for streak status."""
        payload = {
            "query": "What is our current streak and recovery multiplier?",
        }
        res = client.post("/api/v1/copilot/query", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["intent"] == "STREAK_AND_RISK"
        assert "consecutive_losses" in data["risk_context"]
        assert "profit_recovery_multiplier" in data["risk_context"]

    def test_api_briefings_london_open(self, client: TestClient):
        """GET /api/v1/copilot/briefings/london-open"""
        res = client.get("/api/v1/copilot/briefings/london-open")
        assert res.status_code == 200

        data = res.json()
        assert data["briefing_type"] == "LONDON_OPEN"
        assert "Falcon London Open Intelligence Briefing" in data["title"]
        assert "EUR/USD" in data["market_levels"]
        assert "XAU/USD" in data["market_levels"]
        assert len(data["key_insights"]) >= 3
        assert "formatted_text" in data

    def test_api_briefings_daily_review(self, client: TestClient):
        """GET /api/v1/copilot/briefings/daily-review"""
        res = client.get("/api/v1/copilot/briefings/daily-review")
        assert res.status_code == 200

        data = res.json()
        assert data["briefing_type"] == "DAILY_REVIEW"
        assert "Falcon Daily Performance Review" in data["title"]
        assert "session_trades" in data["market_levels"]
        assert "win_rate" in data["market_levels"]

    def test_api_briefings_latest(self, client: TestClient):
        """GET /api/v1/copilot/briefings/latest"""
        # Ensure at least one briefing has been generated
        client.get("/api/v1/copilot/briefings/london-open")

        res = client.get("/api/v1/copilot/briefings/latest")
        assert res.status_code == 200

        data = res.json()
        assert data["briefing_type"] in ("LONDON_OPEN", "DAILY_REVIEW")
        assert "title" in data
        assert "formatted_text" in data
