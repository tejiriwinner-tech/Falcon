"""
Falcon V10 Phase 5G: Execution Divergence Service.

Authoritatively measures divergence between PAPER simulated trade expectations
and actual manually executed LIVE trades.

Key Invariants:
1. Pairing Identity: Matches strictly on signal_id between PAPER (executionMode="PAPER")
   and LIVE (executionMode="LIVE") records.
2. Historical Isolation: Historical untagged records (executionMode=None) are strictly
   excluded from the LIVE divergence population.
3. Actual Fill Authority: Uses actual fill prices (fillPrice) whenever available.
   Never silently substitutes requested/candidate entryPrice.
4. Actual Fill Time Authority: Uses actual fillTime for latency calculation. Missing
   actual fill time yields latency=None (never 0).
5. Deterministic Premature Exit: premature_exit is True ONLY when PAPER reaches TP
   and LIVE closed before TP with full authoritative evidence. Otherwise None.
   MFE difference alone never triggers True.
6. Zero Broker Automation: Purely analytical; no broker connections.
"""

from collections import defaultdict
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    parse_execution_mode,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.schemas.execution_divergence import (
    DivergenceClassification,
    ExecutionDivergenceResponse,
    TradePairDivergenceItem,
)
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.execution_divergence_service")


class ExecutionDivergenceService:
    """Canonical service for measuring execution divergence between PAPER and LIVE trades."""

    def __init__(self, journal_repo: Optional[TradeJournalRepository] = None):
        self._journal_repo = journal_repo or trade_journal_repository

    def get_execution_divergence(
        self,
        as_of: Optional[datetime] = None,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        session: Optional[object] = None,
    ) -> ExecutionDivergenceResponse:
        """
        Compute point-in-time safe execution divergence between PAPER and LIVE trades.
        """
        now = datetime.now(timezone.utc)
        as_of_utc = (
            as_of.astimezone(timezone.utc)
            if (as_of and as_of.tzinfo)
            else (as_of.replace(tzinfo=timezone.utc) if as_of else None)
        )

        all_trades = self._journal_repo.list_trades(session=session)

        # 1. Temporal eligibility filtering (Phase 5E lookahead protection)
        eligible_trades: List[TradeJournalItem] = []
        for t in all_trades:
            t_date = t.tradeDate if t.tradeDate.tzinfo else t.tradeDate.replace(tzinfo=timezone.utc)
            if as_of_utc is not None and t_date > as_of_utc:
                continue

            # If trade closed in the future relative to as_of, exclude closed outcome
            if as_of_utc is not None and t.closeDate is not None:
                c_date = t.closeDate if t.closeDate.tzinfo else t.closeDate.replace(tzinfo=timezone.utc)
                if c_date > as_of_utc:
                    continue

            # Optional filters
            if symbol and (t.symbol or "").upper() != symbol.strip().upper():
                continue
            if strategy_id and t.strategyId != strategy_id:
                continue

            eligible_trades.append(t)

        # 2. Population partitioning & Historical untagged isolation
        # Historical untagged records (executionMode is None) remain strictly excluded from LIVE divergence
        paper_by_signal: Dict[int, List[TradeJournalItem]] = defaultdict(list)
        live_by_signal: Dict[int, List[TradeJournalItem]] = defaultdict(list)

        for t in eligible_trades:
            if t.signalId is None:
                continue

            mode = getattr(t, "executionMode", None) or parse_execution_mode(t.notes)
            if mode == ExecutionMode.PAPER.value:
                paper_by_signal[t.signalId].append(t)
            elif mode == ExecutionMode.LIVE.value:
                live_by_signal[t.signalId].append(t)
            # Untagged records (mode is None) are ignored by design

        all_signal_ids = sorted(list(set(paper_by_signal.keys()) | set(live_by_signal.keys())), reverse=True)

        items: List[TradePairDivergenceItem] = []
        matched_slippages: List[float] = []
        matched_latencies: List[float] = []
        matched_r_divs: List[float] = []
        premature_count = 0

        for sig_id in all_signal_ids:
            p_list = paper_by_signal.get(sig_id, [])
            l_list = live_by_signal.get(sig_id, [])

            # Classification & Ambiguity handling
            if len(p_list) > 1 or len(l_list) > 1:
                ref_trade = p_list[0] if p_list else l_list[0]
                items.append(
                    TradePairDivergenceItem(
                        signalId=sig_id,
                        symbol=ref_trade.symbol,
                        direction=ref_trade.direction,
                        classification=DivergenceClassification.AMBIGUOUS.value,
                        strategyId=ref_trade.strategyId,
                        strategyVersion=ref_trade.strategyVersion,
                        adaptiveRuleVersion=ref_trade.adaptiveRuleVersion,
                    )
                )
                continue

            if p_list and not l_list:
                p_trade = p_list[0]
                items.append(
                    TradePairDivergenceItem(
                        signalId=sig_id,
                        symbol=p_trade.symbol,
                        direction=p_trade.direction,
                        classification=DivergenceClassification.MISSED_EXECUTION.value,
                        strategyId=p_trade.strategyId,
                        strategyVersion=p_trade.strategyVersion,
                        adaptiveRuleVersion=p_trade.adaptiveRuleVersion,
                        paperTradeId=p_trade.id,
                        paperFillPrice=p_trade.fillPrice,
                        paperSignalTime=p_trade.tradeDate,
                        paperSpread=p_trade.spreadAtEntry,
                        paperResult=p_trade.result,
                        paperRealizedR=p_trade.realizedRMultiple,
                        paperMfeR=p_trade.mfeR,
                        paperMaeR=p_trade.maeR,
                    )
                )
                continue

            if l_list and not p_list:
                l_trade = l_list[0]
                items.append(
                    TradePairDivergenceItem(
                        signalId=sig_id,
                        symbol=l_trade.symbol,
                        direction=l_trade.direction,
                        classification=DivergenceClassification.MANUAL_ONLY.value,
                        strategyId=l_trade.strategyId,
                        strategyVersion=l_trade.strategyVersion,
                        adaptiveRuleVersion=l_trade.adaptiveRuleVersion,
                        liveTradeId=l_trade.id,
                        liveFillPrice=l_trade.fillPrice,
                        liveFillTime=l_trade.fillTime,
                        liveSpread=l_trade.spreadAtEntry,
                        liveResult=l_trade.result,
                        liveRealizedR=l_trade.realizedRMultiple,
                        liveMfeR=l_trade.mfeR,
                        liveMaeR=l_trade.maeR,
                    )
                )
                continue

            # Matched Pair (1 PAPER and 1 LIVE)
            p_trade = p_list[0]
            l_trade = l_list[0]
            direction = (p_trade.direction or l_trade.direction).upper()

            # Entry & Slippage Authority: Actual fillPrice ONLY
            entry_delta: Optional[float] = None
            slippage_points: Optional[float] = None
            if p_trade.fillPrice is not None and l_trade.fillPrice is not None:
                entry_delta = round(float(l_trade.fillPrice) - float(p_trade.fillPrice), 5)
                if direction == "BUY":
                    # BUY: Paid more than paper = positive adverse slippage
                    slippage_points = round(float(l_trade.fillPrice) - float(p_trade.fillPrice), 5)
                elif direction == "SELL":
                    # SELL: Received less than paper = positive adverse slippage
                    slippage_points = round(float(p_trade.fillPrice) - float(l_trade.fillPrice), 5)

                if slippage_points is not None:
                    matched_slippages.append(slippage_points)

            # Timing & Latency Authority: Actual fillTime ONLY
            latency_sec: Optional[float] = None
            if l_trade.fillTime is not None and p_trade.tradeDate is not None:
                p_time = p_trade.tradeDate if p_trade.tradeDate.tzinfo else p_trade.tradeDate.replace(tzinfo=timezone.utc)
                l_time = l_trade.fillTime if l_trade.fillTime.tzinfo else l_trade.fillTime.replace(tzinfo=timezone.utc)
                latency_sec = round((l_time - p_time).total_seconds(), 2)
                matched_latencies.append(latency_sec)

            # Spread Delta
            spread_delta: Optional[float] = None
            if l_trade.spreadAtEntry is not None and p_trade.spreadAtEntry is not None:
                spread_delta = round(float(l_trade.spreadAtEntry) - float(p_trade.spreadAtEntry), 5)

            # Realized R Divergence
            r_div: Optional[float] = None
            if l_trade.realizedRMultiple is not None and p_trade.realizedRMultiple is not None:
                r_div = round(float(l_trade.realizedRMultiple) - float(p_trade.realizedRMultiple), 2)
                matched_r_divs.append(r_div)

            # Deterministic Premature Exit (Correction 1)
            premature_exit: Optional[bool] = None
            p_status = (p_trade.status or "").upper()
            l_status = (l_trade.status or "").upper()
            p_res = (p_trade.result or "").upper()

            if p_status == "CLOSED" and l_status == "CLOSED":
                # Evidence requirement: Both closed with exit prices and close dates
                if (
                    p_trade.exitPrice is not None
                    and l_trade.exitPrice is not None
                    and p_trade.closeDate is not None
                    and l_trade.closeDate is not None
                    and p_trade.takeProfit is not None
                    and l_trade.takeProfit is not None
                ):
                    # Condition 4: PAPER reached its defined Take Profit
                    paper_hit_tp = (
                        p_res in ("WIN", "WON")
                        and abs(float(p_trade.exitPrice) - float(p_trade.takeProfit)) <= 0.0002
                    )

                    # Condition 5: LIVE closed before reaching its Take Profit
                    live_tp_reached = abs(float(l_trade.exitPrice) - float(l_trade.takeProfit)) <= 0.0002
                    p_cdate = p_trade.closeDate if p_trade.closeDate.tzinfo else p_trade.closeDate.replace(tzinfo=timezone.utc)
                    l_cdate = l_trade.closeDate if l_trade.closeDate.tzinfo else l_trade.closeDate.replace(tzinfo=timezone.utc)

                    if paper_hit_tp and not live_tp_reached and l_cdate <= p_cdate:
                        premature_exit = True
                        premature_count += 1
                    else:
                        premature_exit = None

            item = TradePairDivergenceItem(
                signalId=sig_id,
                symbol=p_trade.symbol,
                direction=direction,
                classification=DivergenceClassification.MATCHED.value,
                strategyId=p_trade.strategyId or l_trade.strategyId,
                strategyVersion=p_trade.strategyVersion or l_trade.strategyVersion,
                adaptiveRuleVersion=p_trade.adaptiveRuleVersion or l_trade.adaptiveRuleVersion,
                paperTradeId=p_trade.id,
                liveTradeId=l_trade.id,
                paperFillPrice=p_trade.fillPrice,
                liveFillPrice=l_trade.fillPrice,
                entryPriceDelta=entry_delta,
                slippagePoints=slippage_points,
                paperSignalTime=p_trade.tradeDate,
                liveFillTime=l_trade.fillTime,
                executionLatencySeconds=latency_sec,
                paperSpread=p_trade.spreadAtEntry,
                liveSpread=l_trade.spreadAtEntry,
                spreadDelta=spread_delta,
                paperResult=p_trade.result,
                liveResult=l_trade.result,
                paperRealizedR=p_trade.realizedRMultiple,
                liveRealizedR=l_trade.realizedRMultiple,
                rDivergence=r_div,
                paperMfeR=p_trade.mfeR,
                liveMfeR=l_trade.mfeR,
                paperMaeR=p_trade.maeR,
                liveMaeR=l_trade.maeR,
                prematureExit=premature_exit,
            )
            items.append(item)

        avg_slippage = round(sum(matched_slippages) / len(matched_slippages), 5) if matched_slippages else None
        avg_latency = round(sum(matched_latencies) / len(matched_latencies), 2) if matched_latencies else None
        avg_r_div = round(sum(matched_r_divs) / len(matched_r_divs), 2) if matched_r_divs else None

        return ExecutionDivergenceResponse(
            matchedPairsCount=len(matched_slippages) if matched_slippages else len([i for i in items if i.classification == DivergenceClassification.MATCHED.value]),
            missedExecutionCount=len([i for i in items if i.classification == DivergenceClassification.MISSED_EXECUTION.value]),
            manualOnlyCount=len([i for i in items if i.classification == DivergenceClassification.MANUAL_ONLY.value]),
            ambiguousCount=len([i for i in items if i.classification == DivergenceClassification.AMBIGUOUS.value]),
            averageSlippagePoints=avg_slippage,
            averageLatencySeconds=avg_latency,
            averageRDivergence=avg_r_div,
            prematureExitCount=premature_count,
            items=items,
            asOf=as_of_utc or now,
            evaluatedAt=now,
        )


execution_divergence_service = ExecutionDivergenceService()
