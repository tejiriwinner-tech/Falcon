"""
Falcon V10 Phase 5G: Strategy Attribution & Drift Diagnostics Service.

Groups performance across (Strategy ID, Strategy Version, Adaptive Rule Version, Execution Mode)
and provides statistical drift diagnostics comparing LIVE execution against PAPER benchmarks.

Key Invariants:
1. Version Provenance: Historical provenance is immutable (Phase 5D snapshot preserved).
2. Descriptive Metrics: Attribution is strictly descriptive. No strategy rankings, no automatic
   selection, no disabling.
3. Win-Rate Drift: Exact formula SE = sqrt(p_paper * (1 - p_paper) / N_live), z = (p_live - p_paper) / SE.
   Warning emitted ONLY when z < -2.0.
4. Statistical Safety: Insufficient sample (N_live < 10 or N_paper < 10), N_live == 0, SE == 0,
   NaN, or infinite inputs strictly return NOT_EVALUABLE.
5. Profit Factor Drift: Strictly returns zScoreProfitFactor = None and profitFactorDrift = "NOT_EVALUABLE" (Option A).
6. Point-in-Time Safety: Respects as_of (Phase 5E lookahead protection).
7. Zero Broker Automation: Purely analytical.
"""

from collections import defaultdict
from datetime import datetime, timezone
import logging
import math
from typing import Dict, List, Optional, Tuple

from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    parse_execution_mode,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.schemas.strategy_attribution import (
    DriftStatus,
    StrategyAttributionItem,
    StrategyAttributionMetrics,
    StrategyAttributionResponse,
    StrategyAttributionTuple,
    StrategyDriftDiagnostic,
)
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.strategy_attribution_service")

MIN_SAMPLE_SIZE = 10


class StrategyAttributionService:
    """Canonical service for multi-version strategy attribution and drift diagnostics."""

    def __init__(self, journal_repo: Optional[TradeJournalRepository] = None):
        self._journal_repo = journal_repo or trade_journal_repository

    def get_strategy_attribution(
        self,
        as_of: Optional[datetime] = None,
        strategy_id: Optional[str] = None,
        session: Optional[object] = None,
    ) -> StrategyAttributionResponse:
        """
        Compute point-in-time safe strategy attribution and drift diagnostics.
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

            # If trade closed in future relative to as_of, exclude
            if as_of_utc is not None and t.closeDate is not None:
                c_date = t.closeDate if t.closeDate.tzinfo else t.closeDate.replace(tzinfo=timezone.utc)
                if c_date > as_of_utc:
                    continue

            if strategy_id and t.strategyId != strategy_id:
                continue

            eligible_trades.append(t)

        # 2. Group trades across 4-tuple: (strategyId, strategyVersion, adaptiveRuleVersion, executionMode)
        grouped_trades: Dict[Tuple[str, Optional[str], Optional[str], str], List[TradeJournalItem]] = defaultdict(list)

        for t in eligible_trades:
            strat_id = t.strategyId or "unknown"
            strat_ver = getattr(t, "strategyVersion", None)
            rule_ver = getattr(t, "adaptiveRuleVersion", None)
            mode = getattr(t, "executionMode", None) or parse_execution_mode(t.notes) or "UNKNOWN"

            grouped_trades[(strat_id, strat_ver, rule_ver, mode)].append(t)

        attributions: List[StrategyAttributionItem] = []
        for (sid, sver, rver, mode), trades in grouped_trades.items():
            trade_count = len(trades)
            closed_trades = [t for t in trades if (t.status or "").upper() == "CLOSED" and t.closeDate is not None]
            closed_count = len(closed_trades)

            wins = 0
            losses = 0
            breakevens = 0
            gross_profit = 0.0
            gross_loss = 0.0
            r_multiples: List[float] = []
            mfe_list: List[float] = []
            mae_list: List[float] = []
            latency_list: List[float] = []
            slippage_list: List[float] = []

            for ct in closed_trades:
                res = (ct.result or "").upper()
                if res in ("WIN", "WON"):
                    wins += 1
                elif res in ("LOSS", "LOST"):
                    losses += 1
                elif res in ("BREAKEVEN", "BE"):
                    breakevens += 1

                pnl = float(ct.profitLoss or 0.0)
                if pnl > 0:
                    gross_profit += pnl
                elif pnl < 0:
                    gross_loss += abs(pnl)

                if ct.realizedRMultiple is not None:
                    r_multiples.append(float(ct.realizedRMultiple))

                if ct.mfeR is not None:
                    mfe_list.append(float(ct.mfeR))
                if ct.maeR is not None:
                    mae_list.append(float(ct.maeR))

                if ct.fillTime is not None and ct.tradeDate is not None:
                    c_td = ct.tradeDate if ct.tradeDate.tzinfo else ct.tradeDate.replace(tzinfo=timezone.utc)
                    c_ft = ct.fillTime if ct.fillTime.tzinfo else ct.fillTime.replace(tzinfo=timezone.utc)
                    latency_list.append((c_ft - c_td).total_seconds())

                if ct.fillPrice is not None and ct.entryPrice is not None:
                    direction = (ct.direction or "BUY").upper()
                    if direction == "BUY":
                        slippage_list.append(float(ct.fillPrice) - float(ct.entryPrice))
                    else:
                        slippage_list.append(float(ct.entryPrice) - float(ct.fillPrice))

            evaluated_outcomes = wins + losses
            win_rate = round(wins / evaluated_outcomes, 4) if evaluated_outcomes > 0 else 0.0
            profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None
            total_r = round(sum(r_multiples), 2)
            avg_r = round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else None
            avg_mfe = round(sum(mfe_list) / len(mfe_list), 4) if mfe_list else None
            avg_mae = round(sum(mae_list) / len(mae_list), 4) if mae_list else None
            avg_latency = round(sum(latency_list) / len(latency_list), 2) if latency_list else None
            avg_slippage = round(sum(slippage_list) / len(slippage_list), 5) if slippage_list else None

            item_key = StrategyAttributionTuple(
                strategyId=sid,
                strategyVersion=sver,
                adaptiveRuleVersion=rver,
                executionMode=mode,
            )
            item_metrics = StrategyAttributionMetrics(
                tradeCount=trade_count,
                closedCount=closed_count,
                wins=wins,
                losses=losses,
                breakevens=breakevens,
                winRate=win_rate,
                profitFactor=profit_factor,
                totalRealizedR=total_r,
                averageRealizedR=avg_r,
                averageMfeR=avg_mfe,
                averageMaeR=avg_mae,
                averageLatencySeconds=avg_latency,
                averageSlippagePoints=avg_slippage,
            )
            attributions.append(StrategyAttributionItem(key=item_key, metrics=item_metrics))

        # 3. Drift Diagnostics across (strategyId, strategyVersion, adaptiveRuleVersion)
        drift_diagnostics: List[StrategyDriftDiagnostic] = []
        strategy_triplets = set((k[0], k[1], k[2]) for k in grouped_trades.keys())

        for sid, sver, rver in sorted(strategy_triplets, key=lambda t: (t[0] or "", t[1] or "", t[2] or "")):
            paper_trades = grouped_trades.get((sid, sver, rver, ExecutionMode.PAPER.value), [])
            live_trades = grouped_trades.get((sid, sver, rver, ExecutionMode.LIVE.value), [])

            paper_closed = [t for t in paper_trades if (t.status or "").upper() == "CLOSED" and t.closeDate is not None]
            live_closed = [t for t in live_trades if (t.status or "").upper() == "CLOSED" and t.closeDate is not None]

            n_paper = len(paper_closed)
            n_live = len(live_closed)

            # Minimum sample size protection
            if n_live < MIN_SAMPLE_SIZE or n_paper < MIN_SAMPLE_SIZE or n_live == 0:
                diag = StrategyDriftDiagnostic(
                    strategyId=sid,
                    strategyVersion=sver,
                    adaptiveRuleVersion=rver,
                    status=DriftStatus.NOT_EVALUABLE.value,
                    warning=False,
                    sampleSizeLive=n_live,
                    sampleSizePaper=n_paper,
                    liveWinRate=None,
                    paperWinRate=None,
                    standardError=None,
                    zScoreWinRate=None,
                    zScoreProfitFactor=None,
                    profitFactorDrift="NOT_EVALUABLE",
                    diagnosticOnly=True,
                    message=f"Insufficient closed-trade sample size for statistical drift evaluation (Live: {n_live}/{MIN_SAMPLE_SIZE}, Paper: {n_paper}/{MIN_SAMPLE_SIZE}).",
                )
                drift_diagnostics.append(diag)
                continue

            # Calculate win rates
            p_wins = len([t for t in paper_closed if (t.result or "").upper() in ("WIN", "WON")])
            p_losses = len([t for t in paper_closed if (t.result or "").upper() in ("LOSS", "LOST")])
            p_denom = p_wins + p_losses
            p_paper = (p_wins / p_denom) if p_denom > 0 else 0.0

            l_wins = len([t for t in live_closed if (t.result or "").upper() in ("WIN", "WON")])
            l_losses = len([t for t in live_closed if (t.result or "").upper() in ("LOSS", "LOST")])
            l_denom = l_wins + l_losses
            p_live = (l_wins / l_denom) if l_denom > 0 else 0.0

            # Exact SE formula: SE = sqrt(p_paper * (1 - p_paper) / N_live)
            se_variance = (p_paper * (1.0 - p_paper)) / float(n_live)
            if se_variance <= 0.0 or math.isnan(se_variance):
                # SE is 0 (e.g. p_paper == 1.0 or 0.0) -> NOT_EVALUABLE
                diag = StrategyDriftDiagnostic(
                    strategyId=sid,
                    strategyVersion=sver,
                    adaptiveRuleVersion=rver,
                    status=DriftStatus.NOT_EVALUABLE.value,
                    warning=False,
                    sampleSizeLive=n_live,
                    sampleSizePaper=n_paper,
                    liveWinRate=round(p_live, 4),
                    paperWinRate=round(p_paper, 4),
                    standardError=0.0,
                    zScoreWinRate=None,
                    zScoreProfitFactor=None,
                    profitFactorDrift="NOT_EVALUABLE",
                    diagnosticOnly=True,
                    message="Degenerate standard error (p_paper is 0.0 or 1.0); drift is NOT_EVALUABLE.",
                )
                drift_diagnostics.append(diag)
                continue

            se = math.sqrt(se_variance)
            if se == 0.0:
                diag = StrategyDriftDiagnostic(
                    strategyId=sid,
                    strategyVersion=sver,
                    adaptiveRuleVersion=rver,
                    status=DriftStatus.NOT_EVALUABLE.value,
                    warning=False,
                    sampleSizeLive=n_live,
                    sampleSizePaper=n_paper,
                    liveWinRate=round(p_live, 4),
                    paperWinRate=round(p_paper, 4),
                    standardError=0.0,
                    zScoreWinRate=None,
                    zScoreProfitFactor=None,
                    profitFactorDrift="NOT_EVALUABLE",
                    diagnosticOnly=True,
                    message="Zero standard error; drift is NOT_EVALUABLE.",
                )
                drift_diagnostics.append(diag)
                continue

            # Exact z-score: z = (p_live - p_paper) / se
            z_score = (p_live - p_paper) / se
            if math.isnan(z_score) or math.isinf(z_score):
                diag = StrategyDriftDiagnostic(
                    strategyId=sid,
                    strategyVersion=sver,
                    adaptiveRuleVersion=rver,
                    status=DriftStatus.NOT_EVALUABLE.value,
                    warning=False,
                    sampleSizeLive=n_live,
                    sampleSizePaper=n_paper,
                    liveWinRate=round(p_live, 4),
                    paperWinRate=round(p_paper, 4),
                    standardError=round(se, 4),
                    zScoreWinRate=None,
                    zScoreProfitFactor=None,
                    profitFactorDrift="NOT_EVALUABLE",
                    diagnosticOnly=True,
                    message="Mathematically undefined z-score; drift is NOT_EVALUABLE.",
                )
                drift_diagnostics.append(diag)
                continue

            z_round = round(z_score, 2)
            if z_round < -2.0:
                status = DriftStatus.WIN_RATE_DRIFT_DETECTED.value
                warning = True
                msg = f"Diagnostic Warning: Live win rate ({p_live*100:.1f}%) is >2σ below paper benchmark ({p_paper*100:.1f}%), z = {z_round}."
            else:
                status = DriftStatus.NORMAL.value
                warning = False
                msg = f"Normal variation: Live win rate ({p_live*100:.1f}%) vs paper benchmark ({p_paper*100:.1f}%), z = {z_round}."

            diag = StrategyDriftDiagnostic(
                strategyId=sid,
                strategyVersion=sver,
                adaptiveRuleVersion=rver,
                status=status,
                warning=warning,
                sampleSizeLive=n_live,
                sampleSizePaper=n_paper,
                liveWinRate=round(p_live, 4),
                paperWinRate=round(p_paper, 4),
                standardError=round(se, 4),
                zScoreWinRate=z_round,
                zScoreProfitFactor=None,  # Strictly Option A
                profitFactorDrift="NOT_EVALUABLE",  # Strictly Option A
                diagnosticOnly=True,
                message=msg,
            )
            drift_diagnostics.append(diag)

        return StrategyAttributionResponse(
            attributions=attributions,
            driftDiagnostics=drift_diagnostics,
            asOf=as_of_utc or now,
            evaluatedAt=now,
        )


strategy_attribution_service = StrategyAttributionService()
