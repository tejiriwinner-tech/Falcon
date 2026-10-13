"""
Falcon Capital Guardian Service (V10 Phase 3)
Safety service enforcing capital preservation, deterministic trade-count limits,
and fail-closed loss boundaries before signal authorization.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging
from typing import Callable, List, Optional, Set

logger = logging.getLogger("falcon.capital_guardian")

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import parse_execution_mode
from app.core.instruments.instrument_registry import (
    CanonicalInstrumentRegistry,
    instrument_registry,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_cycle_service import (
    CapitalCycleService,
    capital_cycle_service,
)
from app.schemas.capital_cycle import CapitalCycleItem, CapitalCycleStatus
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    GuardianState,
    ProposedTradeInput,
)
from app.schemas.trade_journal import TradeJournalItem

# Capital-reserving lifecycle states confirmed from signal_outcome_resolver & trade_journal
CAPITAL_RESERVING_STATUSES: Set[str] = {"PENDING", "OPEN", "FILLED"}
NON_RESERVING_STATUSES: Set[str] = {"CLOSED", "EXPIRED", "INVALIDATED"}


class CapitalGuardianService:
    """
    Dedicated safety gatekeeper enforcing capital-preservation rules:
    1. Active trading capital is strictly isolated from protected banked profit.
    2. Hard maximum of 3 simultaneous capital-reserving trades.
    3. Aggregate worst-case loss + proposed loss must be strictly less than active trading capital.
    4. Deterministic fail-closed validation on all trade and market parameters.
    """

    def __init__(
        self,
        cycle_service: Optional[CapitalCycleService] = None,
        journal_repository: Optional[TradeJournalRepository] = None,
        instrument_registry: Optional[CanonicalInstrumentRegistry] = None,
        registry: Optional[CanonicalInstrumentRegistry] = None,
        monetary_risk_calculator: Optional[Callable[..., Optional[Decimal]]] = None,
    ) -> None:
        self._cycle_service = cycle_service or capital_cycle_service
        self._journal_repo = journal_repository or trade_journal_repository
        self._registry = instrument_registry or registry or globals()["instrument_registry"]
        self._monetary_calculator = monetary_risk_calculator

    def get_capital_reserving_trades(
        self,
        active_cycle: Optional[CapitalCycleItem] = None,
        filter_by_cycle: bool = True,
        session: Optional[object] = None,
        execution_mode: Optional[str] = None,
    ) -> List[TradeJournalItem]:
        """
        Retrieve all trades currently reserving capital exposure in Falcon.
        
        A trade reserves capital if:
        - status is in ('PENDING', 'OPEN', 'FILLED')
        - closeDate is None
        
        Mode Isolation (Phase 5F):
        - When execution_mode is 'LIVE': only LIVE / manual trades (and unclassified legacy trades)
          are counted. PAPER trades are strictly excluded so paper activity CANNOT consume
          LIVE Guardian slots or capital.
        - When execution_mode is 'PAPER': only PAPER trades are counted in the paper context.
        - When execution_mode is None: all reserving trades are returned.
        
        Cycle Association Note:
        trade_journal currently has no persistent cycle_id.
        When active_cycle is provided and filter_by_cycle=True, a conservative
        timestamp filter (tradeDate >= active_cycle.startedAt - 5s) is applied
        as a Phase 3 compatibility mechanism to avoid counting ancient historical tests.
        """
        all_trades = self._journal_repo.list_trades(session=session)
        reserving = []

        for trade in all_trades:
            status_clean = (trade.status or "").strip().upper()
            if status_clean in CAPITAL_RESERVING_STATUSES and trade.closeDate is None:
                # Mode isolation filter
                trade_mode = getattr(trade, "executionMode", None) or parse_execution_mode(trade.notes)
                if execution_mode is not None:
                    mode_req = execution_mode.strip().upper()
                    if mode_req == "LIVE":
                        # LIVE capacity only includes LIVE trades (or unclassified legacy trades), NOT PAPER
                        if trade_mode == "PAPER":
                            continue
                    elif mode_req == "PAPER":
                        # PAPER capacity only includes PAPER trades
                        if trade_mode != "PAPER":
                            continue

                if filter_by_cycle and active_cycle is not None:
                    # Conservative compatibility filter for current cycle
                    cycle_start = active_cycle.startedAt
                    trade_date = trade.tradeDate
                    if trade_date.tzinfo is None:
                        trade_date = trade_date.replace(tzinfo=timezone.utc)
                    if cycle_start.tzinfo is None:
                        cycle_start = cycle_start.replace(tzinfo=timezone.utc)

                    if trade_date >= (cycle_start - timedelta(seconds=5)):
                        reserving.append(trade)
                else:
                    reserving.append(trade)

        return reserving


    def calculate_trade_worst_case_loss(
        self,
        direction: str,
        entry_price: Decimal | float,
        stop_loss: Decimal | float,
        quantity: Optional[Decimal | float] = None,
        lot_size: Optional[Decimal | float] = None,
        monetary_risk: Optional[Decimal | float] = None,
        symbol: Optional[str] = None,
        is_verified_risk: bool = False,
    ) -> Decimal:
        """
        Deterministically calculate account-currency monetary worst-case loss at stop-loss.
        
        Strict Safety Invariants:
        1. Direction must be 'BUY' or 'SELL'.
        2. BUY: stop_loss must be strictly < entry_price and > 0.
        3. SELL: stop_loss must be strictly > entry_price and > 0.
        4. Arbitrary caller monetary_risk is ignored unless is_verified_risk is True.
        5. Position quantity or lot_size must be strictly positive.
        6. Instrument must have validated USD quote currency or conversion layer.
        7. Fail closed on any missing, invalid, or unsupported conversion data.
        """
        dir_clean = str(direction).strip().upper()
        if dir_clean not in ("BUY", "SELL"):
            raise ValueError(f"Invalid direction '{direction}': must be 'BUY' or 'SELL'")

        try:
            entry = Decimal(str(entry_price))
            sl = Decimal(str(stop_loss))
        except (InvalidOperation, TypeError, ValueError) as ex:
            raise ValueError(f"Invalid price representation: {ex}")

        if entry <= Decimal("0.00") or sl <= Decimal("0.00"):
            raise ValueError("Entry price and stop loss must be strictly positive")

        if dir_clean == "BUY":
            if sl >= entry:
                raise ValueError(
                    f"Invalid stop loss for BUY trade: stop loss ({sl}) must be strictly below entry price ({entry})"
                )
            price_risk = entry - sl
        else:  # SELL
            if sl <= entry:
                raise ValueError(
                    f"Invalid stop loss for SELL trade: stop loss ({sl}) must be strictly above entry price ({entry})"
                )
            price_risk = sl - entry

        # 1. Authoritative verified risk bypass (only when produced by verified internal validator)
        if is_verified_risk and monetary_risk is not None:
            try:
                risk_dec = Decimal(str(monetary_risk))
            except (InvalidOperation, TypeError, ValueError) as ex:
                raise ValueError(f"Invalid verified monetary risk value: {ex}")
            if risk_dec <= Decimal("0.00"):
                raise ValueError("Verified monetary risk must be strictly positive")
            return risk_dec.quantize(Decimal("0.01"))

        # 2. Rejection of unverified caller-supplied monetaryRisk
        if monetary_risk is not None and not is_verified_risk:
            raise ValueError(
                "Unverified monetaryRisk input rejected: arbitrary caller-supplied monetaryRisk cannot bypass validation"
            )

        # 3. Custom injected monetary risk calculator (if configured)
        if self._monetary_calculator is not None:
            calc_res = self._monetary_calculator(
                direction=dir_clean,
                entry_price=entry,
                stop_loss=sl,
                price_risk=price_risk,
                quantity=quantity,
                lot_size=lot_size,
                symbol=symbol,
            )
            if calc_res is not None:
                calc_dec = Decimal(str(calc_res))
                if calc_dec <= Decimal("0.00"):
                    raise ValueError("Calculated monetary risk must be strictly positive")
                return calc_dec.quantize(Decimal("0.01"))

        # 4. Deterministic Account-Currency Conversion
        if quantity is None and lot_size is None:
            raise ValueError("Missing position sizing: quantity or lotSize must be provided")

        if quantity is not None:
            try:
                qty_dec = Decimal(str(quantity))
            except (InvalidOperation, TypeError, ValueError) as ex:
                raise ValueError(f"Invalid quantity representation: {ex}")
            if qty_dec <= Decimal("0.00"):
                raise ValueError("Position quantity must be strictly positive")
        else:
            qty_dec = None

        if lot_size is not None:
            try:
                lot_dec = Decimal(str(lot_size))
            except (InvalidOperation, TypeError, ValueError) as ex:
                raise ValueError(f"Invalid lot size representation: {ex}")
            if lot_dec <= Decimal("0.00"):
                raise ValueError("Lot size must be strictly positive")
        else:
            lot_dec = None

        if not symbol:
            raise ValueError("Instrument symbol is required for monetary loss conversion")

        sym_clean = str(symbol).strip().upper().replace("/", "").replace("_", "")
        inst = self._registry.get_instrument(sym_clean)

        if not inst:
            raise ValueError(
                f"Monetary loss cannot be reliably calculated: instrument '{symbol}' is not registered in Falcon"
            )

        # Check quote currency: Falcon account capital is USD
        if inst.currency != "USD":
            raise ValueError(
                f"Monetary loss cannot be reliably calculated for instrument '{symbol}': "
                f"quote currency is '{inst.currency}', but account currency is USD (no live exchange conversion available)"
            )

        if qty_dec is not None:
            loss = price_risk * qty_dec
            return loss.quantize(Decimal("0.01"))

        if lot_dec is not None:
            if "XAU" in sym_clean or "GOLD" in sym_clean:
                units = lot_dec * Decimal("100")  # 100 oz per standard lot
            elif sym_clean in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"):
                units = lot_dec * Decimal("100000")  # 100,000 units per standard lot
            else:
                units = lot_dec * Decimal("100000")
            loss = price_risk * units
            return loss.quantize(Decimal("0.01"))

        raise ValueError("Unable to determine monetary risk from provided parameters")

    def get_aggregate_worst_case_loss(
        self,
        trades: List[TradeJournalItem],
    ) -> Decimal:
        """
        Calculate sum of worst-case monetary losses for all provided capital-reserving trades.
        Fails closed if any trade's loss cannot be reliably calculated.
        """
        total_loss = Decimal("0.00")
        for t in trades:
            total_loss += self.get_trade_worst_case_loss(t)
        return total_loss.quantize(Decimal("0.01"))

    def get_trade_worst_case_loss(self, t: TradeJournalItem) -> Decimal:
        """Calculates or extracts worst-case monetary loss for an individual trade."""
        if getattr(t, "initialMonetaryRisk", None) is not None and Decimal(str(t.initialMonetaryRisk)) > 0:
            return Decimal(str(t.initialMonetaryRisk)).quantize(Decimal("0.01"))
        return self.calculate_trade_worst_case_loss(
            direction=t.direction,
            entry_price=t.entryPrice,
            stop_loss=t.stopLoss,
            lot_size=Decimal("0.01"),
            symbol=t.symbol,
            is_verified_risk=False,
        )

    def evaluate_proposed_trade(
        self,
        proposal: ProposedTradeInput,
        active_cycle: Optional[CapitalCycleItem] = None,
        active_trades: Optional[List[TradeJournalItem]] = None,
        session: Optional[object] = None,
    ) -> CapitalGuardianDecision:
        """
        Evaluate proposed trade against Falcon V10 capital preservation invariants.
        Returns a deterministic CapitalGuardianDecision.
        """
        # Step 1: Active Capital Cycle Evaluation
        cycle = active_cycle or self._cycle_service.get_active_cycle(session=session)
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

        active_capital = cycle.activeTradingCapital
        protected_profit = cycle.protectedProfit

        # Step 2: Validate Active Trading Capital
        if active_capital <= Decimal("0.00"):
            return CapitalGuardianDecision(
                allowed=False,
                reason="Active trading capital is zero or negative",
                state=GuardianState.HALTED,
                activeTradingCapital=active_capital,
                protectedProfit=protected_profit,
                currentLiveTradeCount=0,
                maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
                currentAggregateWorstCaseLoss=Decimal("0.00"),
                proposedWorstCaseLoss=Decimal("0.00"),
                aggregateWorstCaseLossAfter=Decimal("0.00"),
                remainingLossCapacity=Decimal("0.00"),
                cycleId=cycle.cycleId,
            )

        # Step 3: Capital-Reserving Trades & Hard 3-Trade Limit
        if active_trades is not None:
            live_trades = active_trades
        else:
            live_trades = self.get_capital_reserving_trades(
                active_cycle=cycle, filter_by_cycle=True, session=session
            )

        current_count = len(live_trades)
        max_trades = settings.MAX_SIMULTANEOUS_TRADES  # 3

        # Calculate current aggregate exposure
        try:
            current_agg_loss = self.get_aggregate_worst_case_loss(live_trades)
        except Exception as ex:
            return CapitalGuardianDecision(
                allowed=False,
                reason=f"Failed to calculate existing trade exposure: {ex}",
                state=GuardianState.NORMAL,
                activeTradingCapital=active_capital,
                protectedProfit=protected_profit,
                currentLiveTradeCount=current_count,
                maxLiveTradeCount=max_trades,
                currentAggregateWorstCaseLoss=Decimal("0.00"),
                proposedWorstCaseLoss=Decimal("0.00"),
                aggregateWorstCaseLossAfter=Decimal("0.00"),
                remainingLossCapacity=active_capital,
                cycleId=cycle.cycleId,
            )

        remaining_capacity = active_capital - current_agg_loss

        # Enforce Hard 3-Trade Limit
        if current_count >= max_trades:
            return CapitalGuardianDecision(
                allowed=False,
                reason=f"Maximum simultaneous capital-reserving trades ({max_trades}) reached",
                state=GuardianState.NORMAL,
                activeTradingCapital=active_capital,
                protectedProfit=protected_profit,
                currentLiveTradeCount=current_count,
                maxLiveTradeCount=max_trades,
                currentAggregateWorstCaseLoss=current_agg_loss,
                proposedWorstCaseLoss=Decimal("0.00"),
                aggregateWorstCaseLossAfter=current_agg_loss,
                remainingLossCapacity=remaining_capacity,
                cycleId=cycle.cycleId,
            )

        # Step 4: Validate Proposed Trade Inputs (Fail Closed)
        if not proposal.symbol:
            return self._fail_closed(
                "Missing instrument symbol", cycle, current_count, current_agg_loss, remaining_capacity
            )

        dir_clean = (proposal.direction or "").strip().upper()
        if dir_clean not in ("BUY", "SELL"):
            return self._fail_closed(
                f"Invalid trade direction '{proposal.direction}': must be 'BUY' or 'SELL'",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        if proposal.entryPrice is None or proposal.entryPrice <= Decimal("0.00"):
            return self._fail_closed(
                "Missing or invalid entry price: must be strictly positive",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        if proposal.stopLoss is None or proposal.stopLoss <= Decimal("0.00"):
            return self._fail_closed(
                "Missing or invalid stop loss: must be strictly positive",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        if dir_clean == "BUY" and proposal.stopLoss >= proposal.entryPrice:
            return self._fail_closed(
                f"Invalid stop loss for BUY trade: stop loss ({proposal.stopLoss}) must be strictly below entry price ({proposal.entryPrice})",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        if dir_clean == "SELL" and proposal.stopLoss <= proposal.entryPrice:
            return self._fail_closed(
                f"Invalid stop loss for SELL trade: stop loss ({proposal.stopLoss}) must be strictly above entry price ({proposal.entryPrice})",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        # Step 5: Calculate Proposed Trade Worst-Case Loss
        try:
            proposed_loss = self.calculate_trade_worst_case_loss(
                direction=dir_clean,
                entry_price=proposal.entryPrice,
                stop_loss=proposal.stopLoss,
                quantity=proposal.quantity,
                lot_size=proposal.lotSize,
                monetary_risk=proposal.monetaryRisk,
                symbol=proposal.symbol,
                is_verified_risk=proposal.isVerifiedRisk,
            )
        except Exception as ex:
            return self._fail_closed(
                f"Monetary loss cannot be reliably calculated: {ex}",
                cycle,
                current_count,
                current_agg_loss,
                remaining_capacity,
            )

        # Step 6: Enforce Worst-Case Loss Invariants
        # Invariant 6A: current_aggregate_worst_case_loss + proposed_worst_case_loss < active_trading_capital
        agg_loss_after = current_agg_loss + proposed_loss

        if agg_loss_after >= active_capital:
            return CapitalGuardianDecision(
                allowed=False,
                reason=(
                    f"Proposed trade causes aggregate worst-case loss (${agg_loss_after:.2f}) "
                    f"to equal or exceed active trading capital (${active_capital:.2f})"
                ),
                state=GuardianState.NORMAL,
                activeTradingCapital=active_capital,
                protectedProfit=protected_profit,
                currentLiveTradeCount=current_count,
                maxLiveTradeCount=max_trades,
                currentAggregateWorstCaseLoss=current_agg_loss,
                proposedWorstCaseLoss=proposed_loss,
                aggregateWorstCaseLossAfter=agg_loss_after,
                remainingLossCapacity=remaining_capacity,
                cycleId=cycle.cycleId,
            )

        # Invariant 6B: Percentage-Based Risk & Daily Drawdown Circuit Breakers (Optional Portfolio Layer)
        circuit_breaker_enabled = getattr(settings, "ENABLE_DRAWDOWN_CIRCUIT_BREAKER", False)
        if circuit_breaker_enabled:
            try:
                # 1. Daily Loss Limit (% of active capital lost today)
                daily_limit_pct = Decimal(str(getattr(settings, "DAILY_LOSS_LIMIT_PCT", 3.0)))
                max_daily_loss = (active_capital * daily_limit_pct) / Decimal("100.00")
                
                now_utc = datetime.now(timezone.utc)
                start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
                today_closed = self._journal_repo.list_closed_trades_as_of(as_of=now_utc, session=session)
                today_loss = Decimal("0.00")
                for t in today_closed:
                    if t.closeDate and t.closeDate >= start_of_day:
                        if (t.result or "").upper() in ("LOSS", "LOST"):
                            pnl = abs(Decimal(str(t.profitLoss or 0.0)))
                            today_loss += pnl

                if today_loss >= max_daily_loss and max_daily_loss > Decimal("0.00"):
                    return CapitalGuardianDecision(
                        allowed=False,
                        reason=(
                            f"Daily loss limit reached (${today_loss:.2f} >= ${max_daily_loss:.2f}, {daily_limit_pct}% of capital). "
                            f"Trading paused for remaining UTC day to preserve capital."
                        ),
                        state=GuardianState.HALTED,
                        activeTradingCapital=active_capital,
                        protectedProfit=protected_profit,
                        currentLiveTradeCount=current_count,
                        maxLiveTradeCount=max_trades,
                        currentAggregateWorstCaseLoss=current_agg_loss,
                        proposedWorstCaseLoss=proposed_loss,
                        aggregateWorstCaseLossAfter=agg_loss_after,
                        remainingLossCapacity=remaining_capacity,
                        cycleId=cycle.cycleId,
                    )

                # 2. Maximum Drawdown Pause from Cycle Starting Capital
                dd_pause_pct = Decimal(str(getattr(settings, "MAX_DRAWDOWN_PAUSE_PCT", 10.0)))
                cycle_start = getattr(cycle, "startingCapital", None) or active_capital
                if cycle_start and cycle_start > Decimal("0.00") and active_capital < cycle_start:
                    drawdown_amount = cycle_start - active_capital
                    max_drawdown_allowed = (cycle_start * dd_pause_pct) / Decimal("100.00")
                    if drawdown_amount >= max_drawdown_allowed:
                        return CapitalGuardianDecision(
                            allowed=False,
                            reason=(
                                f"Maximum account drawdown limit reached (${drawdown_amount:.2f} >= ${max_drawdown_allowed:.2f}, {dd_pause_pct}%). "
                                f"Trading paused to preserve account safety."
                            ),
                            state=GuardianState.HALTED,
                            activeTradingCapital=active_capital,
                            protectedProfit=protected_profit,
                            currentLiveTradeCount=current_count,
                            maxLiveTradeCount=max_trades,
                            currentAggregateWorstCaseLoss=current_agg_loss,
                            proposedWorstCaseLoss=proposed_loss,
                            aggregateWorstCaseLossAfter=agg_loss_after,
                            remainingLossCapacity=remaining_capacity,
                            cycleId=cycle.cycleId,
                        )
            except Exception as ex:
                logger.warning(f"Error checking percentage risk/drawdown limits in Capital Guardian: {ex}")

        # Invariant 6C: Currency Cluster Correlation Firewall & Aggregate Risk Cap
        # Caps simultaneous directional exposure and monetary risk on correlated currency clusters
        cluster_gate_enabled = getattr(settings, "ENABLE_CURRENCY_CLUSTER_GATE", False)
        cluster_limit = getattr(settings, "MAX_CURRENCY_CLUSTER_EXPOSURE", 2)
        cluster_risk_limit_pct = Decimal(str(getattr(settings, "MAX_CURRENCY_CLUSTER_RISK_PCT", 2.0)))
        max_cluster_risk_amount = (active_capital * cluster_risk_limit_pct) / Decimal("100.00")

        if cluster_gate_enabled:
            try:
                prop_sym = proposal.symbol.replace("/", "").replace("_", "").upper()
                prop_dir = dir_clean
                prop_currencies = []
                if "XAU" in prop_sym:
                    prop_currencies.append(("GOLD", prop_dir))
                    prop_currencies.append(("USD", "SELL" if prop_dir == "BUY" else "BUY"))
                elif len(prop_sym) == 6:
                    base, quote = prop_sym[:3], prop_sym[3:]
                    prop_currencies.append((base, prop_dir))
                    prop_currencies.append((quote, "SELL" if prop_dir == "BUY" else "BUY"))

                for curr, direction in prop_currencies:
                    matching_cluster_trades = 0
                    cluster_monetary_loss = proposed_loss
                    for lt in live_trades:
                        lt_sym = getattr(lt, "symbol", "").replace("/", "").replace("_", "").upper()
                        lt_dir = getattr(lt, "direction", "").upper()
                        if not lt_sym or not lt_dir:
                            continue
                        is_match = False
                        if "XAU" in lt_sym and curr == "USD":
                            lt_usd_dir = "SELL" if lt_dir == "BUY" else "BUY"
                            if lt_usd_dir == direction:
                                is_match = True
                        elif len(lt_sym) == 6:
                            lt_base, lt_quote = lt_sym[:3], lt_sym[3:]
                            if lt_base == curr and lt_dir == direction:
                                is_match = True
                            elif lt_quote == curr and ("SELL" if lt_dir == "BUY" else "BUY") == direction:
                                is_match = True

                        if is_match:
                            matching_cluster_trades += 1
                            try:
                                lt_loss = self.get_trade_worst_case_loss(lt)
                                cluster_monetary_loss += lt_loss
                            except Exception:
                                pass

                    if matching_cluster_trades >= cluster_limit:
                        return CapitalGuardianDecision(
                            allowed=False,
                            reason=f"Currency cluster limit exceeded: Already {matching_cluster_trades} active trades with {direction} exposure to {curr}. Max allowed is {cluster_limit}.",
                            state=GuardianState.NORMAL,
                            activeTradingCapital=active_capital,
                            protectedProfit=protected_profit,
                            currentLiveTradeCount=current_count,
                            maxLiveTradeCount=max_trades,
                            currentAggregateWorstCaseLoss=current_agg_loss,
                            proposedWorstCaseLoss=proposed_loss,
                            aggregateWorstCaseLossAfter=agg_loss_after,
                            remainingLossCapacity=remaining_capacity,
                            cycleId=cycle.cycleId,
                        )

                    if matching_cluster_trades > 0 and max_cluster_risk_amount > Decimal("0.00") and cluster_monetary_loss > max_cluster_risk_amount:
                        return CapitalGuardianDecision(
                            allowed=False,
                            reason=(
                                f"Currency cluster risk limit exceeded: Total {direction} exposure to {curr} "
                                f"would reach ${cluster_monetary_loss:.2f} (exceeding {cluster_risk_limit_pct}% "
                                f"limit of ${max_cluster_risk_amount:.2f})."
                            ),
                            state=GuardianState.NORMAL,
                            activeTradingCapital=active_capital,
                            protectedProfit=protected_profit,
                            currentLiveTradeCount=current_count,
                            maxLiveTradeCount=max_trades,
                            currentAggregateWorstCaseLoss=current_agg_loss,
                            proposedWorstCaseLoss=proposed_loss,
                            aggregateWorstCaseLossAfter=agg_loss_after,
                            remainingLossCapacity=remaining_capacity,
                            cycleId=cycle.cycleId,
                        )
            except Exception as ex:
                logger.warning(f"Error checking currency cluster exposure in Capital Guardian: {ex}")

        # Invariant 6D: High-Impact News Blackout Shield
        news_blackout_enabled = getattr(settings, "NEWS_BLACKOUT_ENABLED", True)
        if news_blackout_enabled:
            try:
                from app.core.services.economic_calendar_service import economic_calendar_service
                pre_m = getattr(settings, "NEWS_BLACKOUT_MINUTES_BEFORE", 15)
                post_m = getattr(settings, "NEWS_BLACKOUT_MINUTES_AFTER", 15)
                is_blk, n_title, n_curr, n_delta, n_phase = economic_calendar_service.check_blackout_status(
                    symbol=proposal.symbol,
                    blackout_pre_minutes=pre_m,
                    blackout_post_minutes=post_m,
                )
                if is_blk:
                    phase_str = f"in {n_delta}m" if n_phase == "UPCOMING" else f"{n_delta}m ago"
                    return CapitalGuardianDecision(
                        allowed=False,
                        reason=f"High-impact news blackout active: {n_curr} event '{n_title}' ({phase_str}). Trading shielded to prevent slippage.",
                        state=GuardianState.NORMAL,
                        activeTradingCapital=active_capital,
                        protectedProfit=protected_profit,
                        currentLiveTradeCount=current_count,
                        maxLiveTradeCount=max_trades,
                        currentAggregateWorstCaseLoss=current_agg_loss,
                        proposedWorstCaseLoss=proposed_loss,
                        aggregateWorstCaseLossAfter=agg_loss_after,
                        remainingLossCapacity=remaining_capacity,
                        cycleId=cycle.cycleId,
                    )
            except Exception as ex:
                logger.warning(f"Error checking news blackout in Capital Guardian: {ex}")

        # Invariant 6E: Friday Sunset Protocol & Weekend Gap Guard
        friday_sunset_enabled = getattr(settings, "FRIDAY_SUNSET_ENABLED", True)
        if friday_sunset_enabled:
            try:
                now_utc = datetime.now(timezone.utc)
                cutoff_hour = getattr(settings, "FRIDAY_SUNSET_CUTOFF_HOUR_UTC", 20)
                # Friday (weekday 4) after cutoff hour
                if now_utc.weekday() == 4 and now_utc.hour >= cutoff_hour:
                    return CapitalGuardianDecision(
                        allowed=False,
                        reason=f"Friday Sunset protocol active: Trading halted at {now_utc.strftime('%H:%M')} UTC (>= {cutoff_hour}:00 UTC) to prevent weekend gap risk.",
                        state=GuardianState.HALTED,
                        activeTradingCapital=active_capital,
                        protectedProfit=protected_profit,
                        currentLiveTradeCount=current_count,
                        maxLiveTradeCount=max_trades,
                        currentAggregateWorstCaseLoss=current_agg_loss,
                        proposedWorstCaseLoss=proposed_loss,
                        aggregateWorstCaseLossAfter=agg_loss_after,
                        remainingLossCapacity=remaining_capacity,
                        cycleId=cycle.cycleId,
                    )
                # Saturday (5) or Sunday (6) before 21:00 UTC Asian market open
                elif now_utc.weekday() == 5 or (now_utc.weekday() == 6 and now_utc.hour < 21):
                    return CapitalGuardianDecision(
                        allowed=False,
                        reason="Weekend market close: Markets are closed until Sunday 21:00 UTC Asian open.",
                        state=GuardianState.HALTED,
                        activeTradingCapital=active_capital,
                        protectedProfit=protected_profit,
                        currentLiveTradeCount=current_count,
                        maxLiveTradeCount=max_trades,
                        currentAggregateWorstCaseLoss=current_agg_loss,
                        proposedWorstCaseLoss=proposed_loss,
                        aggregateWorstCaseLossAfter=agg_loss_after,
                        remainingLossCapacity=remaining_capacity,
                        cycleId=cycle.cycleId,
                    )
            except Exception as ex:
                logger.warning(f"Error checking Friday sunset in Capital Guardian: {ex}")

        # Step 7: Authorization Granted
        new_remaining = active_capital - agg_loss_after
        return CapitalGuardianDecision(
            allowed=True,
            reason="Trade permitted under capital guardian rules",
            state=GuardianState.NORMAL,
            activeTradingCapital=active_capital,
            protectedProfit=protected_profit,
            currentLiveTradeCount=current_count,
            maxLiveTradeCount=max_trades,
            currentAggregateWorstCaseLoss=current_agg_loss,
            proposedWorstCaseLoss=proposed_loss,
            aggregateWorstCaseLossAfter=agg_loss_after,
            remainingLossCapacity=new_remaining,
            cycleId=cycle.cycleId,
        )

    def _fail_closed(
        self,
        reason: str,
        cycle: CapitalCycleItem,
        live_count: int,
        agg_loss: Decimal,
        rem_cap: Decimal,
    ) -> CapitalGuardianDecision:
        """Helper to construct a deterministic rejection decision."""
        return CapitalGuardianDecision(
            allowed=False,
            reason=reason,
            state=GuardianState.NORMAL,
            activeTradingCapital=cycle.activeTradingCapital,
            protectedProfit=cycle.protectedProfit,
            currentLiveTradeCount=live_count,
            maxLiveTradeCount=settings.MAX_SIMULTANEOUS_TRADES,
            currentAggregateWorstCaseLoss=agg_loss,
            proposedWorstCaseLoss=Decimal("0.00"),
            aggregateWorstCaseLossAfter=agg_loss,
            remainingLossCapacity=rem_cap,
            cycleId=cycle.cycleId,
        )


capital_guardian_service = CapitalGuardianService()
