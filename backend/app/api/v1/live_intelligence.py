"""
Falcon Intelligence Pipeline — Live Intelligence API Endpoint
Phase 4.3: GET /api/v1/live-intelligence/{symbol}

Executes the full Falcon intelligence pipeline for a single symbol using
live market data obtained through ProviderManager.

PIPELINE FLOW (enforced — no shortcuts):
    MarketStateEngine.get_market_snapshot([symbol])
        ↓ (via ProviderManager → cache/providers)
    LiveSafetyGate.validate()
        ↓
    SignalGenerationEngine.generate_candidates()
        ↓
    ValidationEngine.validate_candidates()
        ↓
    RiskEngine.assess_all()
        ↓
    ExecutionReadinessEngine.evaluate_execution_readiness()
        ↓
    DecisionEngine.generate_decisions()
        ↓
    Normalized JSON response

ANALYTICAL ONLY — NO BROKER CONNECTIVITY — NO ORDER EXECUTION
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.engines.market_state_engine import MarketStateEngine, FALCON_WATCHLIST
from app.core.engines.live_safety_gate import live_safety_gate, SafetyGateResult
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
from app.core.engines.decision_engine import DecisionEngine
from app.core.engines.strategy_engine import StrategyEngine

router = APIRouter()

# ── Singleton engines (provider-agnostic) ─────────────────────────────────────
_market_state_engine = MarketStateEngine()
_strategy_engine = StrategyEngine()
_signal_engine = SignalGenerationEngine()
_validation_engine = ValidationEngine()
_risk_engine = RiskEngine()
_exec_engine = ExecutionReadinessEngine()
_decision_engine = DecisionEngine()


class LiveIntelligenceResponse(BaseModel):
    """Normalized response for the live intelligence endpoint.
    
    Contains the full analytical chain output for one symbol.
    Does NOT contain broker identifiers, account information, or order commands.
    """
    symbol: str
    quoteStatus: str
    safetyGateResult: str
    providerId: Optional[str] = None
    providerName: Optional[str] = None
    freshnessSeconds: Optional[float] = None
    marketOpen: bool = False
    session: str = "Unknown"
    trend: str = "Neutral"
    spread: Optional[float] = None
    dataAgeSeconds: int = 0
    overallMarketConfidence: int = 0

    # Full pipeline artifacts (serialized dicts for flexibility)
    marketState: Optional[Dict[str, Any]] = None
    signal: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    risk: Optional[Dict[str, Any]] = None
    executionReadiness: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None

    # Pipeline metadata
    pipelineExecuted: bool = False
    blockedReason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@router.get(
    "/live-intelligence/{symbol}",
    response_model=LiveIntelligenceResponse,
    tags=["live_intelligence"],
    summary="Run the full Falcon intelligence pipeline for a single symbol",
    description=(
        "Fetches live market data through ProviderManager, runs the complete "
        "Falcon intelligence pipeline (Signal → Validation → Risk → Execution "
        "Readiness → Decision), and returns the full analytical chain. "
        "Read-only, analytical only. No broker connectivity. No order execution."
    ),
)
async def get_live_intelligence(symbol: str) -> LiveIntelligenceResponse:
    """Execute the full intelligence pipeline for the requested symbol.
    
    The symbol is normalized via SymbolMapper inside MarketStateEngine.
    Returns 200 for all analytical states (including INSUFFICIENT_DATA).
    Returns 422 only for malformed requests.
    """
    now = datetime.now(timezone.utc)
    symbol_upper = symbol.upper()

    # ── Step 1: Get live market snapshot for this symbol ──────────────────────
    # Use the full watchlist to populate cross-symbol context, but focus on
    # the requested symbol for gate/signal logic.
    try:
        market_state = _market_state_engine.get_market_snapshot([symbol_upper])
    except Exception as exc:
        # Defensive: should never crash, but be explicit rather than 500
        return LiveIntelligenceResponse(
            symbol=symbol_upper,
            quoteStatus="INSUFFICIENT_DATA",
            safetyGateResult=SafetyGateResult.INVALID_MARKET_STATE,
            blockedReason=f"MarketStateEngine error: {exc}",
            pipelineExecuted=False,
            timestamp=now,
        )

    # ── Step 2: Live Safety Gate ───────────────────────────────────────────────
    gate_ok, gate_result = live_safety_gate.validate(market_state, symbol_upper)

    # Build base response with market state summary
    base = LiveIntelligenceResponse(
        symbol=symbol_upper,
        quoteStatus=market_state.quoteStatus,
        safetyGateResult=gate_result,
        providerId=market_state.primaryProviderId,
        providerName=market_state.primaryProviderName,
        freshnessSeconds=market_state.freshnessSeconds,
        marketOpen=market_state.marketOpen,
        session=market_state.session,
        trend=market_state.trend,
        spread=market_state.spread,
        dataAgeSeconds=market_state.dataAgeSeconds,
        overallMarketConfidence=market_state.overallMarketConfidence,
        marketState=market_state.model_dump(mode="json"),
        timestamp=now,
    )

    # Gate blocks pipeline for INSUFFICIENT_DATA / EXPIRED / INVALID states
    # MARKET_CLOSED is advisory — pipeline still runs (analytical signals valid)
    hard_block_results = (
        SafetyGateResult.INSUFFICIENT_DATA,
        SafetyGateResult.INVALID_MARKET_STATE,
        SafetyGateResult.STALE_MARKET,
    )
    if not gate_ok and gate_result in hard_block_results:
        base.pipelineExecuted = False
        base.blockedReason = (
            f"Safety gate blocked pipeline: {gate_result}. "
            f"Quote status: {market_state.quoteStatus}. "
            f"Market data age: {market_state.dataAgeSeconds}s."
        )
        return base

    # ── Step 3: Get strategies for this symbol ────────────────────────────────
    all_strategies = _strategy_engine.get_strategies()
    # Filter to strategies targeting this symbol (or use all as context)
    symbol_strategies = [
        s for s in all_strategies
        if s.symbol.replace("/", "").upper() == symbol_upper.replace("/", "").upper()
    ]
    if not symbol_strategies:
        # Use all strategies so pipeline always runs with context
        symbol_strategies = all_strategies[:2]

    # ── Step 4: Signal Generation ─────────────────────────────────────────────
    try:
        candidates = _signal_engine.generate_candidates(market_state, symbol_strategies)
    except Exception as exc:
        base.pipelineExecuted = False
        base.blockedReason = f"Signal generation error: {exc}"
        return base

    # ── Step 5: Validation ────────────────────────────────────────────────────
    try:
        validations = _validation_engine.validate_candidates(
            candidates, symbol_strategies, market_state
        )
    except Exception as exc:
        base.pipelineExecuted = False
        base.blockedReason = f"Validation error: {exc}"
        return base

    # ── Step 6: Risk ──────────────────────────────────────────────────────────
    try:
        assessments = _risk_engine.assess_all(
            validations, candidates, symbol_strategies, market_state
        )
    except Exception as exc:
        base.pipelineExecuted = False
        base.blockedReason = f"Risk assessment error: {exc}"
        return base

    # ── Step 7: Execution Readiness ───────────────────────────────────────────
    try:
        readiness_items = _exec_engine.evaluate_execution_readiness(
            assessments, validations, candidates, symbol_strategies, market_state
        )
    except Exception as exc:
        base.pipelineExecuted = False
        base.blockedReason = f"Execution readiness error: {exc}"
        return base

    # ── Step 8: Decision ──────────────────────────────────────────────────────
    try:
        decisions = _decision_engine.generate_decisions(
            readiness_items, assessments, validations, candidates, symbol_strategies, market_state
        )
    except Exception as exc:
        base.pipelineExecuted = False
        base.blockedReason = f"Decision engine error: {exc}"
        return base

    # ── Step 9: Serialize artifacts (first item as primary result) ────────────
    primary_signal = candidates[0].model_dump(mode="json") if candidates else None
    primary_validation = validations[0].model_dump(mode="json") if validations else None
    primary_risk = assessments[0].model_dump(mode="json") if assessments else None
    primary_readiness = readiness_items[0].model_dump(mode="json") if readiness_items else None
    primary_decision = decisions[0].model_dump(mode="json") if decisions else None

    base.signal = primary_signal
    base.validation = primary_validation
    base.risk = primary_risk
    base.executionReadiness = primary_readiness
    base.decision = primary_decision
    base.pipelineExecuted = True
    base.blockedReason = None

    return base
