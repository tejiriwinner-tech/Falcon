"""
Falcon V10 Phase 4 — Capital Guardian -> Signal Authorization Hard Gate.

Authoritatively enforces that no signal can become ACTIVE or be executed
unless Capital Guardian evaluates and permits it.

Atomic Authorization + Reservation:
1. PostgreSQL transaction begin
2. pg_advisory_xact_lock(8882026) (in PostgreSQL) + threading.Lock (in-process)
3. Query active capital cycle
4. Query existing capital-reserving trades (status in PENDING, OPEN, FILLED; closeDate is None)
5. Deduplicate against existing signal_id (prevent duplicate reservation slots)
6. Evaluate proposed trade against Capital Guardian invariants (3-trade limit & capital preservation)
7. If permitted, atomically insert PENDING reservation into trade_journal
8. Commit transaction & release advisory lock

All operations fail closed.
"""

from decimal import Decimal
import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import text

from app.core.config import settings
from app.core.database import database_enabled, get_session
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    capital_cycle_repository,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_cycle_service import (
    CapitalCycleService,
    capital_cycle_service,
)
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.schemas.capital_cycle import (
    CapitalCycleItem,
    CapitalCycleStatus,
)
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    GuardianState,
    ProposedTradeInput,
)
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem

logger = logging.getLogger("falcon.signal_authorization_service")

# Stable PostgreSQL transaction advisory lock key for Capital Guardian
FALCON_GUARDIAN_ADVISORY_LOCK_KEY: int = 8882026


class SignalAuthorizationService:
    """
    Hard safety gate ensuring every live signal is evaluated and reserved
    by Capital Guardian before authorization.
    """

    def __init__(
        self,
        cycle_service: Optional[CapitalCycleService] = None,
        guardian_service: Optional[CapitalGuardianService] = None,
        journal_repo: Optional[TradeJournalRepository] = None,
        cycle_repo: Optional[CapitalCycleRepository] = None,
    ) -> None:
        self._cycle_service = cycle_service or capital_cycle_service
        self._guardian_service = guardian_service or capital_guardian_service
        self._journal_repo = journal_repo or trade_journal_repository
        self._cycle_repo = cycle_repo or capital_cycle_repository
        self._in_process_lock = threading.Lock()

    def get_active_reservations(
        self, session: Optional[object] = None, execution_mode: Optional[str] = "LIVE"
    ) -> List[TradeJournalItem]:
        """Return all trades currently reserving capital in the active cycle for the execution mode."""
        cycle = self._cycle_service.get_active_cycle(session=session)
        return self._guardian_service.get_capital_reserving_trades(
            active_cycle=cycle, filter_by_cycle=True, session=session, execution_mode=execution_mode
        )

    def authorize_candidate(
        self,
        candidate: SignalCandidate,
        signal_id: int,
        lot_size: Optional[Decimal | float] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        market_session: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: Optional[int] = None,
        session: Optional[object] = None,
        execution_mode: Optional[str] = "LIVE",
    ) -> Tuple[CapitalGuardianDecision, Optional[TradeJournalItem]]:
        """
        Evaluate a candidate signal through Capital Guardian and create
        a PENDING reservation if authorized.
        """
        # Resolve lot size from execution settings if not specified
        if lot_size is None:
            from app.schemas.execution_order import ExecutionSettings
            lot_size = ExecutionSettings().default_lot_size

        proposal = ProposedTradeInput(
            symbol=candidate.symbol.upper(),
            direction=candidate.direction.value.upper(),
            entryPrice=Decimal(str(candidate.entryPrice)),
            stopLoss=Decimal(str(candidate.stopLoss)),
            takeProfit=Decimal(str(candidate.takeProfit)),
            lotSize=Decimal(str(lot_size)),
            riskReward=Decimal(str(round(candidate.riskReward, 2)))
            if candidate.riskReward
            else None,
        )

        strategy_version = getattr(candidate, "strategyVersion", None)
        spread_at_entry = (
            float(candidate.marketSnapshot.spread)
            if getattr(candidate, "marketSnapshot", None) and getattr(candidate.marketSnapshot, "spread", None) is not None
            else None
        )
        atr_at_entry = getattr(candidate, "atr", None) or (
            float(candidate.marketSnapshot.atr)
            if getattr(candidate, "marketSnapshot", None) and getattr(candidate.marketSnapshot, "atr", None) is not None
            else None
        )
        # Blocker 2: Exact provenance from the candidate snapshot itself (NEVER fresh tuning lookup)
        adaptive_rule_version = getattr(candidate, "adaptiveRuleVersion", None)
        adaptive_stop_multiplier = (
            float(candidate.adaptiveStopMultiplier)
            if getattr(candidate, "adaptiveStopMultiplier", None) is not None
            else None
        )

        return self.authorize_and_reserve(
            proposal=proposal,
            signal_id=signal_id,
            strategy_id=strategy_id or candidate.strategyId,
            timeframe=timeframe,
            market_session=market_session,
            notes=notes or f"Auto-reserved from signal candidate #{signal_id}",
            confidence=confidence or getattr(candidate, "confidence", 80),
            session=session,
            strategy_version=strategy_version,
            adaptive_rule_version=adaptive_rule_version,
            adaptive_stop_multiplier=adaptive_stop_multiplier,
            spread_at_entry=spread_at_entry,
            atr_at_entry=atr_at_entry,
            execution_mode=execution_mode,
        )

    def authorize_and_reserve(
        self,
        proposal: ProposedTradeInput,
        signal_id: Optional[int] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        market_session: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: Optional[int] = None,
        session: Optional[object] = None,
        strategy_version: Optional[str] = None,
        adaptive_rule_version: Optional[str] = None,
        adaptive_stop_multiplier: Optional[float] = None,
        spread_at_entry: Optional[float] = None,
        atr_at_entry: Optional[float] = None,
        execution_mode: Optional[str] = "LIVE",
    ) -> Tuple[CapitalGuardianDecision, Optional[TradeJournalItem]]:
        """
        Authoritatively evaluate and reserve a trade within an atomic transaction
        protected by PostgreSQL advisory lock (pg_advisory_xact_lock(8882026))
        and thread-safe in-process lock.
        """
        # In-process lock serializes concurrent callers within the process
        with self._in_process_lock:
            if session is not None:
                # External session provided: lock if Postgres and execute
                self._acquire_advisory_lock_if_postgres(session)
                return self._execute_authorize_and_reserve(
                    proposal=proposal,
                    signal_id=signal_id,
                    strategy_id=strategy_id,
                    timeframe=timeframe,
                    market_session=market_session,
                    notes=notes,
                    confidence=confidence,
                    session=session,
                    strategy_version=strategy_version,
                    adaptive_rule_version=adaptive_rule_version,
                    adaptive_stop_multiplier=adaptive_stop_multiplier,
                    spread_at_entry=spread_at_entry,
                    atr_at_entry=atr_at_entry,
                    execution_mode=execution_mode,
                )

            # Check if repository storage is persistent database
            is_persistent = getattr(self._journal_repo, "persistent", False) and database_enabled()
            if is_persistent:
                with get_session() as db_session:
                    with db_session.begin():
                        self._acquire_advisory_lock_if_postgres(db_session)
                        return self._execute_authorize_and_reserve(
                            proposal=proposal,
                            signal_id=signal_id,
                            strategy_id=strategy_id,
                            timeframe=timeframe,
                            market_session=market_session,
                            notes=notes,
                            confidence=confidence,
                            session=db_session,
                            strategy_version=strategy_version,
                            adaptive_rule_version=adaptive_rule_version,
                            adaptive_stop_multiplier=adaptive_stop_multiplier,
                            spread_at_entry=spread_at_entry,
                            atr_at_entry=atr_at_entry,
                            execution_mode=execution_mode,
                        )

            # In-memory storage mode
            return self._execute_authorize_and_reserve(
                proposal=proposal,
                signal_id=signal_id,
                strategy_id=strategy_id,
                timeframe=timeframe,
                market_session=market_session,
                notes=notes,
                confidence=confidence,
                session=None,
                strategy_version=strategy_version,
                adaptive_rule_version=adaptive_rule_version,
                adaptive_stop_multiplier=adaptive_stop_multiplier,
                spread_at_entry=spread_at_entry,
                atr_at_entry=atr_at_entry,
                execution_mode=execution_mode,
            )


    def _acquire_advisory_lock_if_postgres(self, session: object) -> None:
        """Acquire PostgreSQL transaction advisory lock if connected to PostgreSQL."""
        try:
            bind = session.get_bind()
            if bind is not None and bind.dialect.name == "postgresql":
                session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": FALCON_GUARDIAN_ADVISORY_LOCK_KEY},
                )
                logger.debug(
                    f"Acquired pg_advisory_xact_lock({FALCON_GUARDIAN_ADVISORY_LOCK_KEY})"
                )
        except Exception as ex:
            logger.warning(f"Could not acquire PostgreSQL advisory lock: {ex}")

    def _execute_authorize_and_reserve(
        self,
        proposal: ProposedTradeInput,
        signal_id: Optional[int],
        strategy_id: Optional[str],
        timeframe: Optional[str],
        market_session: Optional[str],
        notes: Optional[str],
        confidence: Optional[int],
        session: Optional[object],
        strategy_version: Optional[str] = None,
        adaptive_rule_version: Optional[str] = None,
        adaptive_stop_multiplier: Optional[float] = None,
        spread_at_entry: Optional[float] = None,
        atr_at_entry: Optional[float] = None,
        execution_mode: Optional[str] = "LIVE",
    ) -> Tuple[CapitalGuardianDecision, Optional[TradeJournalItem]]:
        """
        Execute core Guardian checks and insert reservation atomically.
        Fails closed on any unexpected error.
        """
        cycle: Optional[CapitalCycleItem] = None
        reserving_trades: List[TradeJournalItem] = []

        try:
            # 1. Fetch active capital cycle
            cycle = self._cycle_service.get_active_cycle(session=session)
            if cycle is None:
                return (
                    CapitalGuardianDecision(
                        allowed=False,
                        reason="No active capital cycle",
                        state=GuardianState.HALTED,
                        activeTradingCapital=Decimal("0.00"),
                        protectedProfit=Decimal("0.00"),
                        currentLiveTradeCount=0,
                        maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                        currentAggregateWorstCaseLoss=Decimal("0.00"),
                        proposedWorstCaseLoss=Decimal("0.00"),
                        aggregateWorstCaseLossAfter=Decimal("0.00"),
                        remainingLossCapacity=Decimal("0.00"),
                        cycleId=None,
                    ),
                    None,
                )

            if cycle.status in (CapitalCycleStatus.HALTED, "HALTED"):
                return (
                    CapitalGuardianDecision(
                        allowed=False,
                        reason="Active capital cycle is HALTED",
                        state=GuardianState.HALTED,
                        activeTradingCapital=cycle.activeTradingCapital,
                        protectedProfit=cycle.protectedProfit,
                        currentLiveTradeCount=0,
                        maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                        currentAggregateWorstCaseLoss=Decimal("0.00"),
                        proposedWorstCaseLoss=Decimal("0.00"),
                        aggregateWorstCaseLossAfter=Decimal("0.00"),
                        remainingLossCapacity=Decimal("0.00"),
                        cycleId=cycle.cycleId,
                    ),
                    None,
                )

            if cycle.status not in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
                return (
                    CapitalGuardianDecision(
                        allowed=False,
                        reason=f"Active capital cycle has invalid status '{cycle.status}'",
                        state=GuardianState.HALTED,
                        activeTradingCapital=cycle.activeTradingCapital,
                        protectedProfit=cycle.protectedProfit,
                        currentLiveTradeCount=0,
                        maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                        currentAggregateWorstCaseLoss=Decimal("0.00"),
                        proposedWorstCaseLoss=Decimal("0.00"),
                        aggregateWorstCaseLossAfter=Decimal("0.00"),
                        remainingLossCapacity=Decimal("0.00"),
                        cycleId=cycle.cycleId,
                    ),
                    None,
                )

            # 2. Fetch current capital-reserving trades for this execution mode
            reserving_trades = self._guardian_service.get_capital_reserving_trades(
                active_cycle=cycle, filter_by_cycle=True, session=session, execution_mode=execution_mode
            )

            # 3. Deduplication against existing active reservation for the exact same signal_id
            if signal_id is not None:
                existing_res = next(
                    (t for t in reserving_trades if t.signalId == signal_id),
                    None,
                )
                if existing_res is not None:
                    # Already reserved — return existing reservation without consuming an extra slot
                    current_loss = self._guardian_service.get_aggregate_worst_case_loss(
                        reserving_trades
                    )
                    decision = CapitalGuardianDecision(
                        allowed=True,
                        reason=f"Signal #{signal_id} is already reserved in active cycle (trade #{existing_res.id})",
                        state=GuardianState.NORMAL,
                        activeTradingCapital=cycle.activeTradingCapital,
                        protectedProfit=cycle.protectedProfit,
                        currentLiveTradeCount=len(reserving_trades),
                        maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                        currentAggregateWorstCaseLoss=current_loss,
                        proposedWorstCaseLoss=Decimal("0.00"),
                        aggregateWorstCaseLossAfter=current_loss,
                        remainingLossCapacity=cycle.activeTradingCapital - current_loss,
                        cycleId=cycle.cycleId,
                    )
                    logger.info(
                        f"Signal #{signal_id} already has active reservation #{existing_res.id}. Returning existing reservation."
                    )
                    return decision, existing_res

            # 4. Evaluate proposal against Guardian invariants
            decision = self._guardian_service.evaluate_proposed_trade(
                proposal=proposal,
                active_cycle=cycle,
                active_trades=reserving_trades,
                session=session,
            )

            if not decision.allowed:
                logger.warning(
                    f"Capital Guardian rejected trade proposal: {decision.reason} "
                    f"(Live trades: {decision.currentLiveTradeCount}/{decision.maxLiveTradeCount}, "
                    f"Agg Loss: ${decision.currentAggregateWorstCaseLoss} + ${decision.proposedWorstCaseLoss} vs ${decision.activeTradingCapital})"
                )
                return decision, None

            # 5. Atomic Reservation Creation in trade_journal
            now = datetime.now(timezone.utc)
            rr_val = 0.0
            if getattr(proposal, "riskReward", None) is not None:
                rr_val = float(proposal.riskReward)
            elif proposal.entryPrice and proposal.stopLoss:
                risk_dist = abs(proposal.entryPrice - proposal.stopLoss)
                if risk_dist > 0 and proposal.takeProfit:
                    rr_val = float(round(abs(proposal.takeProfit - proposal.entryPrice) / risk_dist, 2))

            trade_create = TradeJournalCreate(
                signalId=signal_id,
                strategyId=strategy_id or "FALCON_AI",
                symbol=proposal.symbol.upper(),
                direction=proposal.direction.upper(),
                entryPrice=float(proposal.entryPrice),
                stopLoss=float(proposal.stopLoss),
                takeProfit=float(proposal.takeProfit or proposal.entryPrice),
                timeframe=timeframe or "M15",
                marketSession=market_session or "London / New York",
                tradeDate=now,
                closeDate=None,
                status="PENDING",
                result="PENDING",
                profitLoss=0.0,
                riskReward=rr_val,
                confidence=confidence or 80,
                reasonForEntry=f"Capital Guardian authorized reservation for signal #{signal_id or 'N/A'}",
                notes=notes
                or f"Capital-reserving pending authorization. Worst-case loss: ${decision.proposedWorstCaseLoss}",
                executionMode=execution_mode,
                # V10 Performance & Validation Fields (Populated at PENDING creation)
                strategyVersion=strategy_version,
                adaptiveRuleVersion=adaptive_rule_version,
                adaptiveStopMultiplier=adaptive_stop_multiplier,
                spreadAtEntry=spread_at_entry,
                atrAtEntry=atr_at_entry,
                # Preserved authoritative initial monetary risk from Capital Guardian
                initialMonetaryRisk=decision.proposedWorstCaseLoss,
                # Explicitly unpopulated until real lifecycle events occur
                fillTime=None,
                fillPrice=None,
                realizedRMultiple=None,
                peakPrice=None,
                troughPrice=None,
                mfeR=None,
                maeR=None,
            )

            created_trade = self._journal_repo.create_trade(
                trade_create, session=session
            )
            logger.info(
                f"[AUTHORIZED] Capital Guardian authorized and reserved trade #{created_trade.id} "
                f"for signal #{signal_id} ({proposal.symbol} {proposal.direction}). "
                f"Mode: {execution_mode}, "
                f"Slots: {decision.currentLiveTradeCount + 1}/{decision.maxLiveTradeCount}, "
                f"Loss After: ${decision.aggregateWorstCaseLossAfter}/${decision.activeTradingCapital}"
            )

            return decision, created_trade


        except Exception as ex:
            logger.error(f"Capital Guardian authorization failed closed: {ex}")
            current_count = len(reserving_trades) if reserving_trades else 0
            fail_decision = CapitalGuardianDecision(
                allowed=False,
                reason=f"Authorization failed closed: {str(ex)}",
                state=GuardianState.NORMAL,
                activeTradingCapital=cycle.activeTradingCapital
                if cycle
                else Decimal("0.00"),
                protectedProfit=cycle.protectedProfit
                if cycle
                else Decimal("0.00"),
                currentLiveTradeCount=current_count,
                maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                currentAggregateWorstCaseLoss=Decimal("0.00"),
                proposedWorstCaseLoss=Decimal("0.00"),
                aggregateWorstCaseLossAfter=Decimal("0.00"),
                remainingLossCapacity=Decimal("0.00"),
                cycleId=cycle.cycleId if cycle else None,
            )
            return fail_decision, None


signal_authorization_service = SignalAuthorizationService()
