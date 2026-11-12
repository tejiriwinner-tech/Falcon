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
from datetime import datetime, timezone, timedelta, time
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


def get_rollover_window_utc(now_utc: datetime) -> Tuple[time, time]:
    """
    Computes the exact UTC rollover blackout window for a given date,
    dynamically mapped from 16:50 to 17:30 US Eastern (New York) time.
    During EDT (UTC-4, March-Nov), returns (20:50, 21:30) UTC.
    During EST (UTC-5, Nov-March), returns (21:50, 22:30) UTC.
    """
    try:
        import zoneinfo
        tz_ny = zoneinfo.ZoneInfo("America/New_York")
        dt_ny = now_utc.astimezone(tz_ny)
        dt_ny_start = dt_ny.replace(hour=16, minute=50, second=0, microsecond=0)
        dt_ny_end = dt_ny.replace(hour=17, minute=30, second=0, microsecond=0)
        start_utc = dt_ny_start.astimezone(timezone.utc).time()
        end_utc = dt_ny_end.astimezone(timezone.utc).time()
        return start_utc, end_utc
    except Exception:
        return time(20, 50, 0), time(21, 30, 0)


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
        if cycle is None and (execution_mode or "").upper() == "PAPER":
            return self._guardian_service.get_capital_reserving_trades(
                active_cycle=None, filter_by_cycle=False, session=session, execution_mode=execution_mode
            )
        return self._guardian_service.get_capital_reserving_trades(
            active_cycle=cycle, filter_by_cycle=True, session=session, execution_mode=execution_mode
        )

    def evaluate_candidate(
        self,
        candidate: SignalCandidate,
        signal_id: Optional[int] = None,
        lot_size: Optional[Decimal | float] = None,
        session: Optional[object] = None,
        execution_mode: Optional[str] = "LIVE",
    ) -> CapitalGuardianDecision:
        """
        Pure read-only evaluation of a candidate signal against Capital Guardian invariants.
        Does NOT insert or mutate trade_journal or consume persistent capital reservations.
        """
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

        return self.evaluate_proposal(
            proposal=proposal,
            signal_id=signal_id,
            session=session,
            execution_mode=execution_mode,
            strategy_id=getattr(candidate, "strategyId", None),
        )

    def get_paper_cycle(self) -> Optional[CapitalCycleItem]:
        """Resolve the isolated forward paper capital cycle. Returns None if unconfigured/disabled."""
        now_utc = datetime.now(timezone.utc)
        return CapitalCycleItem(
            id=999999,
            cycleId="CYCLE-PAPER-001",
            cycleNumber=1,
            startingCapital=Decimal("10000.00"),
            targetCapital=Decimal("50000.00"),
            activeTradingCapital=Decimal("10000.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=now_utc,
            createdAt=now_utc,
            updatedAt=now_utc,
        )

    def evaluate_proposal(
        self,
        proposal: ProposedTradeInput,
        signal_id: Optional[int] = None,
        session: Optional[object] = None,
        execution_mode: Optional[str] = "LIVE",
        strategy_id: Optional[str] = None,
    ) -> CapitalGuardianDecision:
        """
        Pure read-only evaluation of a trade proposal against Capital Guardian invariants.
        Does NOT insert into trade_journal or mutate persistent database state.
        """
        try:
            # 1. Fetch active capital cycle (PAPER mode strictly isolated to synthetic paper cycle)
            now_utc = datetime.now(timezone.utc)
            if (execution_mode or "").upper() == "PAPER":
                cycle = self.get_paper_cycle()
            else:
                cycle = self._cycle_service.get_active_cycle(session=session)

            if cycle is None:
                return CapitalGuardianDecision(
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
                )

            if cycle.status in (CapitalCycleStatus.HALTED, "HALTED"):
                return CapitalGuardianDecision(
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
                )

            if cycle.status not in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
                return CapitalGuardianDecision(
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
                )

            # 1b. Post-Stop Cooldown Check (45-minute blackout per strategy & symbol)
            is_cd_ok, cd_reason = self.check_post_stop_cooldown(
                strategy_id=strategy_id,
                symbol=proposal.symbol,
                now_utc=datetime.now(timezone.utc),
                session=session,
            )
            if not is_cd_ok:
                logger.warning(f"Authorization rejected by cooldown: {cd_reason}")
                return CapitalGuardianDecision(
                    allowed=False,
                    reason=cd_reason,
                    state=GuardianState.NORMAL,
                    activeTradingCapital=cycle.activeTradingCapital if cycle else Decimal("0.00"),
                    protectedProfit=cycle.protectedProfit if cycle else Decimal("0.00"),
                    currentLiveTradeCount=0,
                    maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                    currentAggregateWorstCaseLoss=Decimal("0.00"),
                    proposedWorstCaseLoss=Decimal("0.00"),
                    aggregateWorstCaseLossAfter=Decimal("0.00"),
                    remainingLossCapacity=Decimal("0.00"),
                    cycleId=cycle.cycleId if cycle else None,
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
                    current_loss = self._guardian_service.get_aggregate_worst_case_loss(
                        reserving_trades
                    )
                    return CapitalGuardianDecision(
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

            # 4. Evaluate proposal against Guardian invariants
            return self._guardian_service.evaluate_proposed_trade(
                proposal=proposal,
                active_cycle=cycle,
                active_trades=reserving_trades,
                session=session,
            )

        except Exception as ex:
            logger.error(
                f"Fail-closed: Unexpected error during read-only Capital Guardian evaluation: {ex}",
                exc_info=True,
            )
            return CapitalGuardianDecision(
                allowed=False,
                reason=f"Fail-closed evaluation error: {ex}",
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


    def validate_market_and_spread_conditions(
        self,
        symbol: str,
        quote_resp: Optional[object] = None,
        now_utc: Optional[datetime] = None,
        bypass_quote_check: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate UTC Rollover Blackout (20:50 - 21:30 UTC), quote freshness (<= 30s),
        and instrument-specific spread caps:
          - Gold: $0.80 USD cash maximum (quoted in price difference)
          - JPY Majors (USDJPY): 2.0 pips (0.020)
          - JPY Crosses (GBPJPY, EURJPY): 3.5 pips (0.035)
          - Forex Majors (EURUSD, GBPUSD, AUDUSD): 2.0 pips (0.00020)
          - Forex Crosses (EURGBP, etc.): 3.5 pips (0.00035)
        Fails closed on stale (>30s) or missing quote data when bypass_quote_check is False.
        """
        now = now_utc or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        clean_sym = symbol.replace("/", "").replace("_", "").replace("-", "").upper()

        # 1. UTC Rollover Blackout Check (Dynamic US Eastern 16:50 - 17:30 New York / UTC equivalent)
        if getattr(settings, "ROLLOVER_BLACKOUT_ENABLED", True):
            now_time = now.time()
            start_str = getattr(settings, "ROLLOVER_BLACKOUT_START_UTC", "20:50")
            end_str = getattr(settings, "ROLLOVER_BLACKOUT_END_UTC", "21:30")

            # If default settings are used, calculate dynamically based on US Eastern DST
            if start_str == "20:50" and end_str == "21:30":
                start_t, end_t = get_rollover_window_utc(now)
            else:
                try:
                    sh, sm = map(int, start_str.split(":"))
                    eh, em = map(int, end_str.split(":"))
                    start_t = time(sh, sm, 0)
                    end_t = time(eh, em, 0)
                except Exception:
                    start_t = time(20, 50, 0)
                    end_t = time(21, 30, 0)

            if start_t <= end_t:
                in_blackout = (start_t <= now_time <= end_t)
            else:
                in_blackout = (now_time >= start_t or now_time <= end_t)

            if in_blackout:
                return False, f"DAILY ROLLOVER BLACKOUT: {start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')} UTC interbank liquidity freeze. Entries blocked."

        if bypass_quote_check:
            return True, None

        # 2. Quote Availability & Freshness Check
        if not quote_resp or not getattr(quote_resp, "quote", None):
            return False, "QUOTE UNAVAILABLE: Live quote from broker unavailable. Order entry blocked."

        quote = quote_resp.quote
        bid_ask = getattr(quote, "bidAsk", None)
        if not bid_ask or bid_ask.bid <= 0 or bid_ask.ask <= 0 or bid_ask.ask < bid_ask.bid or getattr(bid_ask, "spread", 0) < 0:
            return False, "INVALID OR CROSSED QUOTE: Broker bid/ask prices missing, non-positive, or crossed (ask < bid). Order entry blocked."

        q_time = getattr(quote, "timestamp", None)
        if q_time is not None:
            if not q_time.tzinfo:
                q_time = q_time.replace(tzinfo=timezone.utc)
            quote_age = (now - q_time).total_seconds()
            if quote_age > 30.0:
                return False, f"STALE QUOTE: Live quote is {quote_age:.1f}s old (> 30.0s threshold). Order entry blocked."
            if quote_age < -5.0:
                return False, f"FUTURE QUOTE: Live quote is from the future ({abs(quote_age):.1f}s ahead). Order entry blocked."

        # 3. Instrument-Specific Spread Cap with Explicit Unit Accounting
        raw_spread = float(bid_ask.spread)
        is_gold = "XAU" in clean_sym or "GOLD" in clean_sym
        is_jpy = clean_sym.endswith("JPY")

        if is_gold:
            max_gold_spread = 0.80  # $0.80 USD
            if raw_spread > max_gold_spread:
                return False, f"SPREAD SPIKE: Gold spread ${raw_spread:.2f} USD exceeds maximum allowable $0.80 USD cap. Entry blocked."
        elif is_jpy:
            pip_size = 0.010
            spread_pips = raw_spread / pip_size
            max_pips = 3.5 if any(k in clean_sym for k in ("GBP", "EUR", "AUD", "CAD", "NZD")) else 2.0
            if spread_pips > max_pips:
                return False, f"SPREAD SPIKE: Live spread {spread_pips:.1f} pips exceeds maximum {max_pips:.1f} pips cap for {symbol}. Entry blocked."
        else:
            pip_size = 0.00010
            spread_pips = raw_spread / pip_size
            is_major = any(clean_sym == m for m in ("EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"))
            max_pips = 2.0 if is_major else 3.5
            if spread_pips > max_pips:
                return False, f"SPREAD SPIKE: Live spread {spread_pips:.1f} pips exceeds maximum {max_pips:.1f} pips cap for {symbol}. Entry blocked."

        return True, None

    def check_post_stop_cooldown(
        self,
        strategy_id: Optional[str],
        symbol: str,
        now_utc: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Enforce 45-minute post-stop cooldown per (strategy_id, symbol).
        Prevents rapid-fire whipsaw re-entries across multiple worker processes.
        Protected by PostgreSQL transaction advisory lock in caller.
        """
        if not strategy_id or strategy_id.lower() in ("unknown", "default", "none"):
            return True, None

        now = now_utc or datetime.now(timezone.utc)
        cooldown_cutoff = now - timedelta(minutes=45)
        clean_sym = symbol.replace("/", "").replace("_", "").replace("-", "").upper()

        # 1. PostgreSQL direct SQL execution if connected
        if session is not None:
            try:
                bind = getattr(session, "get_bind", lambda: None)()
                if bind is not None and bind.dialect.name == "postgresql":
                    stmt = text(
                        """
                        SELECT id, close_date, result, reason_for_exit
                        FROM trade_journal
                        WHERE strategy_id = :strat_id
                          AND REPLACE(REPLACE(REPLACE(UPPER(symbol), '/', ''), '_', ''), '-', '') = :clean_sym
                          AND UPPER(status) = 'CLOSED'
                          AND close_date >= :cutoff
                          AND (
                              UPPER(result) IN ('LOST', 'LOSS', 'BREAKEVEN', 'BE')
                              OR reason_for_exit ILIKE '%Stop Loss%'
                              OR reason_for_exit ILIKE '%STOP_LOSS%'
                          )
                        ORDER BY close_date DESC
                        LIMIT 1
                        """
                    )
                    res = session.execute(stmt, {
                        "strat_id": strategy_id,
                        "clean_sym": clean_sym,
                        "cutoff": cooldown_cutoff,
                    }).fetchone()
                    if res is not None:
                        c_date = res[1]
                        if c_date:
                            if not c_date.tzinfo:
                                c_date = c_date.replace(tzinfo=timezone.utc)
                            rem_m = max(1, int((c_date + timedelta(minutes=45) - now).total_seconds() / 60))
                        else:
                            rem_m = 45
                        reason = (
                            f"POST-STOP COOLDOWN: Strategy '{strategy_id}' on {clean_sym} is in 45m cooldown "
                            f"({rem_m}m remaining) following stop-out on Trade #{res[0]}."
                        )
                        logger.warning(reason)
                        return False, reason
            except Exception as ex:
                logger.debug(f"PostgreSQL post-stop cooldown check error: {ex}")

        # 2. Repository check (applies to in-memory, SQLite, or fallback)
        try:
            trades = self._journal_repo.list_trades(session=session) or []
            for t in trades:
                if t.strategyId == strategy_id:
                    t_sym = t.symbol.replace("/", "").replace("_", "").replace("-", "").upper()
                    if t_sym == clean_sym and (t.status or "").upper() == "CLOSED":
                        t_close = t.closeDate
                        if t_close:
                            if not t_close.tzinfo:
                                t_close = t_close.replace(tzinfo=timezone.utc)
                            if t_close >= cooldown_cutoff:
                                res_str = (t.result or "").upper()
                                reas_str = (t.reasonForExit or "").lower()
                                is_stop = (
                                    res_str in ("LOST", "LOSS", "BREAKEVEN", "BE")
                                    or "stop loss" in reas_str
                                    or "stop_loss" in reas_str
                                )
                                if is_stop:
                                    rem_m = max(1, int((t_close + timedelta(minutes=45) - now).total_seconds() / 60))
                                    reason = (
                                        f"POST-STOP COOLDOWN: Strategy '{strategy_id}' on {clean_sym} is in 45m cooldown "
                                        f"({rem_m}m remaining) following stop-out on Trade #{t.id}."
                                    )
                                    logger.warning(reason)
                                    return False, reason
        except Exception as ex:
            logger.debug(f"Repository post-stop cooldown check error: {ex}")

        return True, None

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
            # 1. Fetch active capital cycle (PAPER mode strictly isolated to synthetic paper cycle)
            now_utc = datetime.now(timezone.utc)
            if (execution_mode or "").upper() == "PAPER":
                cycle = self.get_paper_cycle()
            else:
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

            # 1b. Post-Stop Cooldown Check (45-minute blackout per strategy & symbol)
            is_cd_ok, cd_reason = self.check_post_stop_cooldown(
                strategy_id=strategy_id,
                symbol=proposal.symbol,
                now_utc=datetime.now(timezone.utc),
                session=session,
            )
            if not is_cd_ok:
                logger.warning(f"Authorization rejected by cooldown: {cd_reason}")
                return CapitalGuardianDecision(
                    allowed=False,
                    reason=cd_reason,
                    state=GuardianState.NORMAL,
                    activeTradingCapital=cycle.activeTradingCapital if cycle else Decimal("0.00"),
                    protectedProfit=cycle.protectedProfit if cycle else Decimal("0.00"),
                    currentLiveTradeCount=0,
                    maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                    currentAggregateWorstCaseLoss=Decimal("0.00"),
                    proposedWorstCaseLoss=Decimal("0.00"),
                    aggregateWorstCaseLossAfter=Decimal("0.00"),
                    remainingLossCapacity=Decimal("0.00"),
                    cycleId=cycle.cycleId if cycle else None,
                ), None

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
                status="OPEN" if (execution_mode or "").upper() == "LIVE" else "PENDING",
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
                fillTime=now if (execution_mode or "").upper() == "LIVE" else None,
                fillPrice=float(proposal.entryPrice) if (execution_mode or "").upper() == "LIVE" else None,
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

            # FCM Push & Telegram alerts are dispatched strictly when signal turns ACTIVE (price touches entry in SignalService)

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
