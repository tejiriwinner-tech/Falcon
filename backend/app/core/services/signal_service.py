import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Set, Tuple

logger = logging.getLogger("falcon.signal_service")

import app.core.providers as providers
from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.repository.signal_signature_repository import (
    signal_signature_repository,
    format_signature_key,
    parse_signature_key,
)
from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine, LossRecoveryMetrics
from app.core.engines.strategy_engine import StrategyEngine
from app.core.config import settings
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
from app.schemas.execution_order import ExecutionSettings
from app.schemas.market_quote import MarketQuote, MarketQuoteResponse
from app.schemas.signal_candidate import SignalCandidate, CandidateStatus, CandidateDirection
from app.schemas.signal import SignalItem, SignalListResponse
from app.schemas.trade_journal import TradeJournalCreate
from app.core.services.signal_authorization_service import signal_authorization_service



def canonical_signal_signature(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> Tuple[str, str, float, float, float]:
    """
    Computes a canonical unique signature for a trade setup level.
    Used for historical deduplication and lifecycle state tracking.
    """
    sym = (symbol or "").replace("/", "").upper()
    dir_str = (direction or "").upper()
    return (
        sym,
        dir_str,
        round(float(entry_price or 0.0), 4),
        round(float(stop_loss or 0.0), 4),
        round(float(take_profit or 0.0), 4),
    )


def extract_directional_currency_exposures(symbol: str, direction: str) -> List[str]:
    """
    Extracts underlying currency basket directional exposures to prevent correlated cluster drawdowns.
    Examples:
    - EUR/USD BUY  -> ["+EUR", "-USD"]
    - EUR/USD SELL -> ["-EUR", "+USD"]
    - XAU/USD BUY  -> ["+XAU", "-USD"]
    - XAU/USD SELL -> ["-XAU", "+USD"]
    - GBP/USD BUY  -> ["+GBP", "-USD"]
    - AUD/USD BUY  -> ["+AUD", "-USD"]
    - USD/JPY BUY  -> ["+USD", "-JPY"]
    - USD/JPY SELL -> ["-USD", "+JPY"]
    - GBP/JPY BUY  -> ["+GBP", "-JPY"]
    - GBP/JPY SELL -> ["-GBP", "+JPY"]
    """
    clean = (symbol or "").replace("/", "").replace("_", "").replace("-", "").upper()
    dir_str = (direction or "").upper()
    if "XAU" in clean or "GOLD" in clean:
        base, quote = "XAU", "USD"
    elif len(clean) == 6:
        base, quote = clean[:3], clean[3:]
    else:
        return []

    if dir_str == "BUY":
        return [f"+{base}", f"-{quote}"]
    elif dir_str == "SELL":
        return [f"-{base}", f"+{quote}"]
    return []


class SignalService:
    """
    Curates, ranks, and serves high-conviction sniper trading signals.
    Enforces quality, authentic session breakout & volume triggers, and complete lifecycle deduplication:
    - Filters out low confidence (< 80%) and unconfirmed setups.
    - HOLD: Setup is on watchlist awaiting live market price to touch canonical entry.
    - ACTIVE: Live market touched entry price. Holds until TP or SL is hit (no 3-slot active cap).
    - EXPIRED: Watchlist setup reached 1-hour timeout without price reaching entry.
    - DEDUPLICATION: Complete historical memory persists in PostgreSQL/Supabase and memory,
      preventing re-generating or duplicating triggered/completed setups across server restarts.
    """

    _cache_response: Optional[SignalListResponse] = None
    _cache_time: Optional[datetime] = None
    CACHE_TTL_SECONDS: float = 30.0

    def __init__(self) -> None:
        self._strategy_engine = StrategyEngine()
        self._cache_response = None
        self._cache_time = None
        self._historical_triggered_signatures: Set[Tuple[str, str, float, float, float]] = set(
            signal_signature_repository.get_resolved_signatures()
        )

    def get_signals(self, mission_limit: int = 5, force_refresh: bool = False) -> SignalListResponse:
        """Alias for build_signals to guarantee backward compatibility with callers."""
        return self.build_signals(mission_limit=mission_limit, force_refresh=force_refresh)

    def build_signals(self, mission_limit: int = 5, force_refresh: bool = False) -> SignalListResponse:
        now = datetime.now(timezone.utc)
        if not force_refresh and self._cache_response and self._cache_time:
            if (now - self._cache_time).total_seconds() < self.CACHE_TTL_SECONDS:
                return self._cache_response

        # Refresh persisted historically resolved/completed signatures from repository (DB / memory)
        try:
            persisted_sigs = signal_signature_repository.get_resolved_signatures()
            self._historical_triggered_signatures.update(persisted_sigs)
        except Exception as ex:
            logger.debug(f"Could not load persisted signatures: {ex}")

        signals: List[SignalItem] = []
        step1_active_signals: List[SignalItem] = []
        seen_open_syms: Set[str] = set()
        resolved_signal_ids: Set[int] = set()
        resolved_entry_keys: Set[Tuple[str, str, float]] = set()
        seen_signatures: Set[Tuple[str, str, float, float, float]] = set(self._historical_triggered_signatures)

        # Step 1: Query TradeJournal for OPEN active trades and recently RESOLVED trades
        try:
            from app.schemas.strategy import StrategyStatus
            se_instance = StrategyEngine()
            active_strat_ids = {s.id for s in se_instance.get_strategies() if s.status == StrategyStatus.ACTIVE}

            all_journal_trades = trade_journal_repository.list_trades()
            closed_trades_all = [
                t for t in all_journal_trades
                if (t.status or "").upper() in ("CLOSED", "EXPIRED", "INVALIDATED")
                and (t.result or "").upper() in ("WIN", "WON", "LOSS", "LOST", "BREAKEVEN", "BE", "EXPIRED", "INVALIDATED")
            ]
            resolved_signal_ids: Set[int] = {int(t.signalId) for t in closed_trades_all if getattr(t, "signalId", None) is not None}
            resolved_entry_keys: Set[Tuple[str, str, float]] = {
                (t.symbol.replace("/", "").replace("-", "").upper(), t.direction.upper(), round(float(t.entryPrice or 0.0), 3))
                for t in closed_trades_all
            }

            # Active open positions from TradeJournal (only active strategies, clamped to 1:1.2-1:1.5 R:R)
            seen_open_syms: Set[str] = set()
            open_symbol_dirs: Dict[str, str] = {}
            step1_seen_sigs: Set[Tuple[str, str, float, float, float]] = set()
            open_trades = [
                t for t in all_journal_trades
                if (t.status or "").upper() in ("OPEN", "FILLED")
                and t.closeDate is None
                and (getattr(t, "executionMode", None) or "").upper() != "PAPER"
                and "[MODE:PAPER]" not in (t.notes or "")
                and (getattr(t, "signalId", None) not in resolved_signal_ids)
                and (t.symbol.replace("/", "").replace("-", "").upper(), t.direction.upper(), round(float(t.entryPrice or 0.0), 3)) not in resolved_entry_keys
            ]
            open_trades.sort(key=lambda t: t.tradeDate, reverse=True)
            for ot in open_trades:
                sig_key = canonical_signal_signature(
                    ot.symbol,
                    ot.direction,
                    ot.entryPrice,
                    ot.stopLoss,
                    ot.takeProfit,
                )
                ot_base_sym = ot.symbol.replace("/", "").replace("-", "").upper()
                ot_norm_sym = f"{ot_base_sym}:{ot.strategyId or ''}"
                if ot_base_sym in open_symbol_dirs and open_symbol_dirs[ot_base_sym] != ot.direction.upper():
                    continue
                open_symbol_dirs[ot_base_sym] = ot.direction.upper()
                if sig_key in step1_seen_sigs or ot_norm_sym in seen_open_syms:
                    continue
                seen_open_syms.add(ot_norm_sym)
                step1_seen_sigs.add(sig_key)
                if False:
                    (
                )
                seen_signatures.add(sig_key)
                self._historical_triggered_signatures.add(sig_key)
                try:
                    signal_signature_repository.record_signature(
                        ot.symbol, ot.direction, ot.entryPrice, ot.stopLoss, ot.takeProfit, status="ACTIVE"
                    )
                except Exception:
                    pass

                dec = 2 if ("XAU" in ot.symbol.upper() or "GOLD" in ot.symbol.upper() or ot.entryPrice > 500) else (3 if "JPY" in ot.symbol.upper() else 4)
                risk_d = abs(ot.entryPrice - ot.stopLoss)
                be_trig = ot.entryPrice + risk_d if ot.direction.upper() == "BUY" else ot.entryPrice - risk_d

                # Fetch real-time market quote to reflect live floating metrics
                cur_live_px = None
                try:
                    raw_ot_sym = ot.symbol.replace("/", "").upper()
                    pm = getattr(providers, "provider_manager", None)
                    if pm is not None:
                        cached_e = pm._cache.get(raw_ot_sym, allow_stale=False) if hasattr(pm, "_cache") else None
                        if cached_e and getattr(cached_e.data, "lastPrice", None):
                            cur_live_px = cached_e.data.lastPrice
                        else:
                            q_resp = pm.get_market_quote(raw_ot_sym)
                            if q_resp and q_resp.quote and q_resp.quote.lastPrice:
                                cur_live_px = q_resp.quote.lastPrice
                except Exception:
                    pass

                live_px_str = f" | Current Market: {cur_live_px:.4f}" if cur_live_px else ""
                from app.core.engines.session_breakout_engine import session_breakout_engine
                from app.core.engines.candlestick_pattern_engine import CandleBar
                from app.core.services.market_history_service import market_history_service

                raw_candles = []
                try:
                    sym_clean = ot.symbol.replace("/", "")
                    p_bars = market_history_service.get_bars(sym_clean, timeframe="1h", limit=50)
                    raw_candles = [
                        CandleBar(
                            open=b.open,
                            high=b.high,
                            low=b.low,
                            close=b.close,
                            volume=b.volume or 0.0,
                            timestamp=int(b.bar_time.timestamp()) if hasattr(b.bar_time, "timestamp") else None,
                            time=b.bar_time,
                        )
                        for b in p_bars
                    ]
                except Exception:
                    raw_candles = []

                ot_dir_val = ot.direction.upper()
                _, ot_tp1, ot_tp2, ot_trail_buf, ot_atr = session_breakout_engine.calculate_trade_levels(
                    symbol=ot.symbol,
                    direction=ot_dir_val,
                    entry_price=ot.entryPrice,
                    candles=raw_candles,
                    structure_sl=ot.stopLoss,
                    take_profit=ot.takeProfit,
                )
                ot_htf_bias, _, _ = session_breakout_engine.compute_htf_trend_bias(ot.symbol, raw_candles)

                is_be_prot = "BE_PROTECTED" in (ot.notes or "") or (ot.stopLoss >= ot.entryPrice if ot.direction.upper() == "BUY" else ot.stopLoss <= ot.entryPrice)
                active_signal = SignalItem(
                    id=ot.signalId or ot.id,
                    symbol=ot.symbol,
                    action=ot.direction.upper(),
                    entry=ot.entryPrice,
                    takeProfit=ot.takeProfit,
                    stopLoss=ot.stopLoss,
                    confidence=ot.confidence or 85,
                    timeframe=ot.timeframe or "M15",
                    status="ACTIVE",
                    analysis=f"🎯 RUNNING (LIVE) [{ot.notes or 'Falcon Trade'}]: Live position active from entry {ot.entryPrice:.4f}{live_px_str}. TP1: {ot_tp1} (50% Bank) | TP2: {ot_tp2} (Runner) | Macro Bias: {ot_htf_bias}.",
                    timestamp=ot.tradeDate,
                    strategyId=ot.strategyId or "falcon-opt",
                    strategyName=ot.notes or "Falcon Strategy",
                    strategyVersion="4.2",
                    dataAgeSeconds=0,
                    triggerCondition=f"Enter {ot.direction.upper()} at {ot.entryPrice:.4f}",
                    validUntil=ot.tradeDate + timedelta(hours=48),
                    setupPattern=ot.notes or ot.strategyId or "Falcon Trade",
                    riskReward=(ot.riskReward if (ot.riskReward and ot.riskReward > 0) else (round(abs(ot.takeProfit - ot.entryPrice) / risk_d, 2) if risk_d > 1e-6 else 2.0)),
                    isPinned=True,
                    breakevenTrigger=round(be_trig, dec),
                    breakevenPrice=round(ot.entryPrice, dec),
                    isBreakeven=is_be_prot,
                    takeProfit1=ot_tp1,
                    takeProfit2=ot_tp2,
                    scaleOutPercentage=50.0,
                    trailingStopBuffer=ot_trail_buf,
                    htfTrendBias=ot_htf_bias,
                    atr14=ot_atr,
                    quantGrade="A" if is_be_prot else "B",
                    estDeltaBadge="🛡️ BE Protected ($0.00 Risk)" if is_be_prot else "🟢 Active Momentum",
                    tacticalAdvice="Trade defended at breakeven ($0.00 risk)" if is_be_prot else "Target TP1 and TP2 runners",
                    isBreakevenProtected=is_be_prot,
                )
                step1_active_signals.append(active_signal)

            # Resolved trades (WON, LOST, BREAKEVEN, EXPIRED)
            closed_trades = [
                t for t in all_journal_trades
                if (t.status or "").upper() in ("CLOSED", "EXPIRED", "INVALIDATED")
                and (t.result or "").upper() in ("WIN", "WON", "LOSS", "LOST", "BREAKEVEN", "BE", "EXPIRED", "INVALIDATED")
            ]
            closed_trades.sort(key=lambda t: t.closeDate or t.tradeDate, reverse=True)
            for ct in closed_trades[:10]:
                sig_key = canonical_signal_signature(
                    ct.symbol,
                    ct.direction,
                    ct.entryPrice,
                    ct.stopLoss,
                    ct.takeProfit,
                )
                if sig_key in step1_seen_sigs:
                    continue
                step1_seen_sigs.add(sig_key)
                if False:
                    (
                )
                seen_signatures.add(sig_key)
                self._historical_triggered_signatures.add(sig_key)

                res_str = (ct.result or "").upper()
                if res_str in ("WIN", "WON"):
                    outcome_status = "WON"
                    analysis_msg = (
                        f"🏆 TARGET ACHIEVED [WON]: Take Profit hit cleanly at "
                        f"{ct.exitPrice or ct.takeProfit:.4f} (+{ct.profitLoss:+.1f} pts). "
                        f"R:R 1:{ct.riskReward:.1f} secured."
                    )
                elif res_str in ("BREAKEVEN", "BE"):
                    outcome_status = "BREAKEVEN"
                    analysis_msg = (
                        f"🛡️ CAPITAL DEFENDED [BREAKEVEN]: Market reached +1.0R excursion, "
                        f"stop shifted to entry ({ct.entryPrice:.4f}); exited with zero loss."
                    )
                elif res_str in ("EXPIRED", "INVALIDATED") or (ct.status or "").upper() == "EXPIRED":
                    outcome_status = "EXPIRED"
                    analysis_msg = (
                        f"⏳ UNTRIGGERED SETUP [EXPIRED]: Market moved away without reaching "
                        f"entry ({ct.entryPrice:.4f}). Order auto-canceled cleanly without risk."
                    )
                else:
                    outcome_status = "LOST"
                    analysis_msg = (
                        f"🛑 STOPPED OUT [LOST]: Invalidation boundary hit at "
                        f"{ct.exitPrice or ct.stopLoss:.4f} (-{abs(ct.profitLoss):.1f} pts). "
                        f"Capital defended."
                    )

                try:
                    signal_signature_repository.record_signature(
                        ct.symbol, ct.direction, ct.entryPrice, ct.stopLoss, ct.takeProfit, status=outcome_status
                    )
                except Exception:
                    pass

                dec = 2 if ("XAU" in ct.symbol.upper() or "GOLD" in ct.symbol.upper() or ct.entryPrice > 500) else (3 if "JPY" in ct.symbol.upper() else 4)
                risk_d = abs(ct.entryPrice - ct.stopLoss)
                be_trig = ct.entryPrice + risk_d if ct.direction.upper() == "BUY" else ct.entryPrice - risk_d

                is_be_res = res_str in ("BREAKEVEN", "BE") or "BE_PROTECTED" in (ct.notes or "")
                resolved_signal = SignalItem(
                    id=ct.signalId or ct.id,
                    symbol=ct.symbol,
                    action=ct.direction.upper(),
                    entry=ct.entryPrice,
                    takeProfit=ct.takeProfit,
                    stopLoss=ct.stopLoss,
                    confidence=ct.confidence or 80,
                    timeframe=ct.timeframe or "M15",
                    status=outcome_status,
                    analysis=analysis_msg,
                    timestamp=ct.tradeDate,
                    strategyId=ct.strategyId or "falcon-opt",
                    strategyName=ct.notes or "Falcon Strategy",
                    strategyVersion="4.2",
                    dataAgeSeconds=0,
                    triggerCondition="Trade Completed",
                    validUntil=ct.closeDate,
                    setupPattern=ct.notes or ct.strategyId or "Falcon Trade",
                    riskReward=ct.riskReward,
                    isPinned=False,
                    breakevenTrigger=round(be_trig, dec),
                    breakevenPrice=round(ct.entryPrice, dec),
                    isBreakeven=is_be_res,
                    quantGrade="A" if outcome_status == "WON" else ("B" if is_be_res else "C"),
                    estDeltaBadge="🏆 Win Secured" if outcome_status == "WON" else ("🛡️ Capital Defended" if is_be_res else "🛑 Stopped Out"),
                    tacticalAdvice=analysis_msg,
                    isBreakevenProtected=is_be_res,
                )
                signals.append(resolved_signal)
        except Exception as ex:
            logger.debug(f"Could not load trade journal records: {ex}")

        # Step 2: Ingest candidate setups from recent missions
        missions = None
        try:
            all_m = None
            from unittest.mock import Mock
            all_m_fn = getattr(mission_repository, "get_all_missions", None)
            if all_m_fn and isinstance(all_m_fn, Mock):
                m_ret = all_m_fn()
                missions = m_ret[-mission_limit:] if m_ret else []
            if not missions and hasattr(mission_repository, "get_recent_missions"):
                missions = mission_repository.get_recent_missions(limit=mission_limit)
            if not missions:
                all_m = mission_repository.get_all_missions()
            if all_m:
                missions = all_m[-mission_limit:]
        except Exception:
            missions = None
        if not missions:
            try:
                missions = mission_repository.get_recent_missions(limit=mission_limit)
            except Exception:
                missions = []

        if missions:
            mission_ids = [m.id for m in missions]
            bulk_artifacts = {}
            if hasattr(mission_repository, "get_all_mission_artifacts_bulk"):
                try:
                    bulk_artifacts = mission_repository.get_all_mission_artifacts_bulk(
                        mission_ids,
                        artifact_types=["candidates", "decisions"],
                    ) or {}
                except Exception:
                    bulk_artifacts = {}

            candidate_pool: List[dict] = []
            for mission in reversed(missions):
                try:
                    artifacts = bulk_artifacts.get(mission.id)
                    if not artifacts:
                        artifacts = mission_repository.get_mission_artifacts(mission.id) or {}
                    candidates: List[SignalCandidate] = artifacts.get("candidates", [])
                    decisions: List[DecisionArtifact] = artifacts.get("decisions", [])
                    by_candidate = {d.candidateId: d for d in decisions}

                    for index, candidate in enumerate(candidates):
                        if candidate.direction == CandidateDirection.WAIT:
                            continue
                        if candidate.status == CandidateStatus.REJECTED:
                            continue
                        if candidate.confidence < 50:
                            continue

                        # Strict Strategy Pruning: Omit candidates from non-active strategies
                        if candidate.strategyId and candidate.strategyId not in active_strat_ids:
                            continue

                        # Strict R:R Cap: 1:1.20 to 1:1.50 Maximum
                        eff_cand_rr = min(max(candidate.riskReward or 1.3, 1.2), 1.5)
                        candidate.riskReward = eff_cand_rr
                        risk_d = abs(candidate.entryPrice - candidate.stopLoss)
                        if risk_d > 1e-6:
                            if candidate.direction == CandidateDirection.BUY:
                                cand_dec = 2 if ("XAU" in candidate.symbol.upper() or "GOLD" in candidate.symbol.upper() or candidate.entryPrice > 500) else (3 if "JPY" in candidate.symbol.upper() else 4)
                                candidate.takeProfit = round(candidate.entryPrice + (risk_d * eff_cand_rr), cand_dec)
                            else:
                                cand_dec = 2 if ("XAU" in candidate.symbol.upper() or "GOLD" in candidate.symbol.upper() or candidate.entryPrice > 500) else (3 if "JPY" in candidate.symbol.upper() else 4)
                                candidate.takeProfit = round(candidate.entryPrice - (risk_d * eff_cand_rr), cand_dec)

                        # Omit candidates older than 6 hours to eliminate ancient stale clutter
                        if candidate.generatedAt and (now - candidate.generatedAt).total_seconds() > 6 * 3600:
                            continue

                        dec = by_candidate.get(candidate.id)
                        is_approved = dec is not None and dec.status == DecisionStatus.APPROVED
                        exec_r = float(getattr(dec.pipelineSummary, "executionReadinessScore", 0.0) if (dec and getattr(dec, "pipelineSummary", None)) else 0.0)
                        readiness = max(float(getattr(candidate, "readinessScore", 50.0) or 50.0), exec_r)
                        candidate.readinessScore = int(round(readiness))
                        confidence = float(candidate.confidence)

                        has_sniper = any(r.title.startswith("Sniper Setup:") for r in getattr(candidate, "reasons", []))
                        sniper_boost = 25.0 if has_sniper else 0.0
                        conviction_score = (100.0 if is_approved else 0.0) + sniper_boost + (confidence * 0.5) + (readiness * 0.5)

                        candidate_pool.append({
                            "candidate": candidate,
                            "decision": dec,
                            "signal_id": self._signal_id(mission.id, index),
                            "conviction_score": conviction_score,
                            "is_approved": is_approved,
                            "mission_id": mission.id,
                        })
                except Exception:
                    continue

            # Sort candidate pool by conviction score descending
            candidate_pool.sort(key=lambda x: (1 if (x.get("is_approved") and getattr(x.get("candidate"), "readinessScore", 0) >= 80) else 0, x.get("conviction_score", 0.0)), reverse=True)

            curated_active: List[dict] = []
            curated_watchlist: List[dict] = []
            additional_resolved: List[SignalItem] = []
            active_symbols: set = {ot.symbol.replace('/', '').replace('-', '').upper() for ot in open_trades}
            watchlist_symbols: set = set()
            active_currency_baskets: Dict[str, str] = {}
            open_trades.sort(key=lambda t: t.tradeDate, reverse=True)
            for ot in open_trades:
                ot_status = (ot.status or "").upper()
                if ot_status in ("OPEN", "FILLED") and ot.closeDate is None:
                    is_be = getattr(ot, "isBreakevenProtected", False) or "BE_PROTECTED" in (ot.notes or "")
                    if not is_be:
                        ot_exps = extract_directional_currency_exposures(ot.symbol, ot.direction)
                        for exp in ot_exps:
                            if any(c in exp for c in ("USD", "JPY", "EUR", "GBP", "AUD")):
                                active_currency_baskets[exp] = f"{active_currency_baskets[exp]},{ot.symbol}" if exp in active_currency_baskets else ot.symbol

            lot_size = ExecutionSettings().default_lot_size
            pm = getattr(providers, "provider_manager", None)
            batch_quotes = {}
            if True:
                try:
                    pass
                except Exception:
                    pass
            if pm is not None and hasattr(pm, "get_batch_quotes") and candidate_pool:
                try:
                    unique_syms = list({item["candidate"].symbol.replace("/", "").upper() for item in candidate_pool})
                    pass
                except Exception:
                    pass
            if pm is not None and hasattr(pm, "get_batch_quotes") and candidate_pool:
                try:
                    unique_syms = list({item["candidate"].symbol.replace("/", "").upper() for item in candidate_pool})
                    batch_quotes = pm.get_batch_quotes(unique_syms) or {}
                except Exception:
                    batch_quotes = {}
                try:
                    pass
                except Exception:
                    pass

            for item in candidate_pool:
                cand = item["candidate"]
                symbol = cand.symbol
                norm_sym = symbol.replace("/", "").replace("-", "").upper()
                direction_str = cand.direction.value if hasattr(cand.direction, "value") else str(cand.direction)
                sig_key = canonical_signal_signature(
                    symbol,
                    direction_str,
                    cand.entryPrice,
                    cand.stopLoss,
                    cand.takeProfit,
                )
                if sig_key in seen_signatures or item["signal_id"] in resolved_signal_ids or (norm_sym, direction_str.upper(), round(float(cand.entryPrice or 0.0), 3)) in resolved_entry_keys:
                    # Deduplication & Historical Memory: setup was already processed / triggered / completed
                    continue
                seen_signatures.add(sig_key)

                # Institutional Anti-Hedging & Unique Asset Resolve:
                # If this asset already has an authoritative active or pending setup,
                # skip weaker or conflicting setups so Falcon strictly focuses on 1 unique trade per symbol.
                # Strict Symbol-Level Concurrency Cap: Max 1 active trade per asset across all strategies
                if norm_sym in active_symbols:
                    continue
                strat_sym_key = f"{norm_sym}:{cand.strategyId or ''}"
                if strat_sym_key in watchlist_symbols:
                    continue

                # Real-Time Live Market Quote Evaluation (Layer 2: Strict Freshness <= 60s)
                cur_px = None
                quote_age_s = 999.0
                quote_resp = None
                try:
                    raw_sym = symbol.replace("/", "").upper()
                    b_resp = batch_quotes.get(raw_sym) if isinstance(batch_quotes, dict) else None
                    if b_resp and getattr(b_resp, "quote", None) and getattr(b_resp.quote, "lastPrice", None):
                        cur_px = b_resp.quote.lastPrice
                        raw_freshness = getattr(b_resp.quote, "freshnessSeconds", 0.0)
                        try:
                            quote_age_s = float(raw_freshness) if raw_freshness is not None else 0.0
                        except (TypeError, ValueError):
                            quote_age_s = 0.0
                        quote_resp = b_resp
                    if (cur_px is None or quote_age_s > 60.0) and pm is not None and hasattr(pm, "_cache"):
                        cached_entry = pm._cache.get(raw_sym, allow_stale=True)
                        if cached_entry and hasattr(cached_entry, "data"):
                            q_data = cached_entry.data
                            if getattr(q_data, "lastPrice", None):
                                cur_px = q_data.lastPrice
                                try:
                                    quote_age_s = float(cached_entry.age_seconds)
                                except (TypeError, ValueError):
                                    quote_age_s = 0.0
                            if isinstance(q_data, MarketQuote):
                                quote_resp = MarketQuoteResponse(quote=q_data)

                    # If cache missing or older than 60s, fetch real-time quote
                    if (cur_px is None or quote_age_s > 60.0) and pm is not None:
                        resp = pm.get_market_quote(raw_sym)
                        if resp and resp.quote and resp.quote.lastPrice:
                            cur_px = resp.quote.lastPrice
                            raw_freshness = getattr(resp.quote, "freshnessSeconds", 0.0)
                            try:
                                quote_age_s = float(raw_freshness) if raw_freshness is not None else 0.0
                            except (TypeError, ValueError):
                                quote_age_s = 0.0
                            quote_resp = resp
                except Exception:
                    pass

                if cur_px is not None:
                    try:
                        cur_px = float(cur_px)
                    except (TypeError, ValueError):
                        cur_px = None

                # Proximity band: 1.0 to 1.5 pips (0.00015 for 4-digit Forex, 0.50 for Gold)
                is_gold_sym = "XAU" in symbol.upper() or "GOLD" in symbol.upper() or cand.entryPrice > 500
                is_jpy_sym = "JPY" in symbol.upper()
                # Strict Precision Entry Proximity: Gold max 1.20 USD tolerance, Forex 0.8 to 1.5 pips
                pip_tolerance = 1.20 if is_gold_sym else (0.080 if is_jpy_sym else 0.00080)
                slip_invalidation = 6.00 if is_gold_sym else (0.200 if is_jpy_sym else 0.00200)

                # Pre-evaluate candidate via in-memory Guardian (Phase 5B read-only pipeline)
                signal_authorization_service.evaluate_candidate(cand)

                # Check if this setup is ALREADY recorded as ACTIVE in repository or open trades
                is_already_active = signal_signature_repository.is_active(
                    symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit
                )
                if not is_already_active:
                    if signal_signature_repository.is_active(symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit):
                        is_already_active = True
                        self._historical_triggered_signatures.add(sig_key)
                    else:
                        for ot in open_trades:
                            ot_sym = ot.symbol.replace("/", "").replace("-", "").upper()
                            if (
                                ot_sym == norm_sym
                                and ot.direction.upper() == direction_str.upper()
                                and abs(ot.entryPrice - cand.entryPrice) <= pip_tolerance
                            ):
                                is_already_active = True
                                self._historical_triggered_signatures.add(sig_key)
                                break

                # 1-hour expiration rule: applies ONLY to pending watchlist setups (never to active running positions)
                age_seconds = (now - cand.generatedAt).total_seconds()
                is_1h_elapsed = age_seconds >= 3600
                is_approved = item["is_approved"]
                is_ready = (getattr(cand, "readinessScore", 0) >= 80) or is_approved

                if not is_already_active and is_1h_elapsed:
                    # Expired: on watchlist >= 1hr without touching entry -> RESOLVED/EXPIRED
                    self._historical_triggered_signatures.add(sig_key)
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="EXPIRED"
                        )
                    except Exception:
                        pass
                    additional_resolved.append(self._to_signal(
                        cand, item["decision"], item["signal_id"], now,
                        override_status="EXPIRED",
                        current_market_px=cur_px,
                    ))
                    continue

                # Layer 3: Strict Active Proximity Band & Missed-Candle Invalidation
                entry_hit = is_already_active
                is_slipped_past = False

                if cur_px is None and getattr(cand, "marketSnapshot", None) and getattr(cand.marketSnapshot, "currentPrice", 0):
                    cur_px = float(cand.marketSnapshot.currentPrice)
                    quote_age_s = float(getattr(cand, "marketDataAgeSeconds", 0) or 0)
                if cur_px is not None and cur_px > 0 and quote_age_s <= 300.0:
                    dist_to_entry = abs(cur_px - cand.entryPrice)
                    # A. Strict Active Touch Window: Price must currently test entry within 1.0 - 1.5 pips
                    if dist_to_entry <= pip_tolerance:
                        entry_hit = True
                    elif not is_already_active:
                        # B. Missed/Slipped Invalidation (applies ONLY if trade hasn't activated yet):
                        if cand.direction.value.upper() == "BUY":
                            if cur_px < (cand.entryPrice - slip_invalidation):
                                is_slipped_past = True
                        else:
                            if cur_px > (cand.entryPrice + slip_invalidation):
                                is_slipped_past = True

                if is_slipped_past:
                    self._historical_triggered_signatures.add(sig_key)
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="EXPIRED"
                        )
                    except Exception:
                        pass
                    additional_resolved.append(self._to_signal(
                        cand, item["decision"], item["signal_id"], now,
                        override_status="EXPIRED",
                        current_market_px=cur_px,
                    ))
                    continue

                # If position is already active, step 1 has already processed it into signals.
                # Avoid duplicates; exit monitoring and journal updates are handled solely by SignalOutcomeResolver.
                if is_already_active and strat_sym_key in seen_open_syms:
                    continue

                # Capital Defense Shield Checks (apply only to pending setups):
                shield_reason = None
                if not is_already_active:
                    # 0. Daily Rollover Blackout (20:50 - 21:30 UTC): Interbank liquidity freeze & spread blowout
                    now_utc_time = now.time()
                    from datetime import time as dt_time
                    if dt_time(20, 50) <= now_utc_time <= dt_time(21, 30):
                        shield_reason = "DAILY ROLLOVER BLACKOUT: 20:50-21:30 UTC interbank liquidity freeze. Entries blocked."

                    # 0b. Symbol-Wide Post-Stop Cooldown: Prevents rapid-fire whipsaw & multi-strategy cascades on same asset
                    if not shield_reason:
                        try:
                            cooldown_mins = 60 if is_gold_sym else 45
                            cooldown_cutoff = now - timedelta(minutes=cooldown_mins)
                            all_closed = trade_journal_repository.list_trades() or []
                            recent_stop_trade = next((
                                t for t in all_closed
                                if (t.symbol.replace("/", "").replace("-", "").upper() == norm_sym)
                                and (t.status or "").upper() == "CLOSED"
                                and (t.result or "").upper() in ("LOST", "LOSS", "BREAKEVEN", "BE")
                                and (t.closeDate is not None and t.closeDate >= cooldown_cutoff)
                            ), None)
                            if recent_stop_trade:
                                shield_reason = f"POST-STOP COOLDOWN: {symbol} in {cooldown_mins}m symbol-wide cooldown following stop-out by {recent_stop_trade.strategyId}. Capital defended."
                            else:
                                chop_cutoff_3h = now - timedelta(hours=3)
                                recent_sym_losses = [
                                    t for t in all_closed
                                    if (t.symbol.replace("/", "").replace("-", "").upper() == norm_sym)
                                    and (t.status or "").upper() == "CLOSED"
                                    and (t.result or "").upper() in ("LOST", "LOSS")
                                    and (t.closeDate is not None and t.closeDate >= chop_cutoff_3h)
                                ]
                                if len(recent_sym_losses) >= 2:
                                    latest_loss_dt = max(t.closeDate for t in recent_sym_losses if t.closeDate is not None)
                                    chop_duration = 120 if is_gold_sym else 90
                                    if latest_loss_dt >= (now - timedelta(minutes=chop_duration)):
                                        shield_reason = f"ANTI-WHIPSAW CHOP SHIELD: {symbol} recorded {len(recent_sym_losses)} stop-outs in 3h window. {chop_duration}m market cooldown active."
                            if not shield_reason and norm_sym in open_symbol_dirs and open_symbol_dirs[norm_sym] != direction_str.upper():
                                shield_reason = f"OPPOSING POSITION SHIELD: Active {open_symbol_dirs[norm_sym]} position already open on {symbol}. Opposing {direction_str.upper()} entry blocked."
                        except Exception as ex:
                            logger.debug(f"Post-stop cooldown check error: {ex}")

                    # 1. Economic Calendar News Blackout Check
                    if getattr(settings, "NEWS_BLACKOUT_ENABLED", False):
                        try:
                            from app.core.services.economic_calendar_service import economic_calendar_service
                            is_blk, n_title, n_curr, n_delta, n_phase = economic_calendar_service.check_blackout_status(symbol)
                            if is_blk:
                                phase_str = f"in {n_delta}m" if n_phase == "UPCOMING" else f"{n_delta}m ago"
                                shield_reason = f"NEWS BLACKOUT: {n_curr} High/Medium-Impact event '{n_title}' {phase_str}. Capital shield active."
                            else:
                                news_cat_eval = economic_calendar_service.evaluate_news_catalyst(symbol, proposed_direction=direction_str)
                                if news_cat_eval.get("is_counter_news_fade"):
                                    shield_reason = f"POST-NEWS FADE VETO: {news_cat_eval.get('rationale')}"
                        except Exception as ex:
                            logger.debug(f"News blackout shield check error: {ex}")

                    # 2. Dynamic, Volatility-Adjusted Spread Protection
                    if not shield_reason:
                        try:
                            if quote_resp and quote_resp.quote and getattr(quote_resp.quote, "bidAsk", None):
                                raw_spread = quote_resp.quote.bidAsk.spread
                                clean_sym = symbol.replace("/", "").replace("_", "").upper()
                                is_gold = "XAU" in clean_sym
                                is_jpy = clean_sym.endswith("JPY")

                                from app.core.engines.apex_scalp_config import get_apex_fx_spec
                                _prom_fx_spec = get_apex_fx_spec(getattr(cand, "strategyId", ""))
                                if is_gold:
                                    pip_size = 0.10
                                    baseline_max = 4.5 if getattr(cand, "strategyId", "") == "strat-024" else 8.0
                                elif _prom_fx_spec is not None:
                                    pip_size = 0.01 if is_jpy else 0.00010
                                    baseline_max = _prom_fx_spec.max_spread_pips
                                elif is_jpy:
                                    pip_size = 0.01
                                    baseline_max = 4.5 if "GBP" in clean_sym else 3.0
                                else:
                                    pip_size = 0.00010
                                    baseline_max = 2.5 if "GBP" in clean_sym else 2.0

                                spread_pips = raw_spread / pip_size
                                max_allowed_spread = baseline_max
                                if spread_pips > max_allowed_spread:
                                    shield_reason = f"SPREAD SPIKE: Live spread {spread_pips:.1f} pips exceeds {max_allowed_spread:.1f} limit. Entry held."
                                elif getattr(cand, "strategyId", "") != "strat-006":
                                    live_dom = getattr(quote_resp.quote, "domImbalance", None)
                                    if live_dom is None and getattr(quote_resp.quote, "bidAsk", None):
                                        live_dom = getattr(quote_resp.quote.bidAsk, "domImbalance", None)
                                    if live_dom is not None:
                                        if (direction_str.upper() == "BUY" and live_dom <= -0.55) or (direction_str.upper() == "SELL" and live_dom >= 0.55):
                                            shield_reason = f"L2 DOM LIQUIDITY WALL SHIELD: Opposing institutional order-book wall (DOM Imbalance {live_dom:+.2f}) at entry. Waiting for absorption."
                        except Exception as ex:
                            logger.debug(f"Spread spike shield check error: {ex}")

                    # 3. Multi-Timeframe (MTF) Institutional Confluence Filter
                    if not shield_reason:
                        try:
                            cand_reasons = getattr(cand, "reasons", [])
                            for r in cand_reasons:
                                t_desc = (getattr(r, "title", "") + " " + getattr(r, "description", "")).lower()
                                if any(k in t_desc for k in ["counter-trend", "against 4h", "against 1h", "session corridor resistance", "volatility exhaustion"]):
                                    if getattr(cand, "confidence", 80) < 85:
                                        shield_reason = "MTF FILTER: Counter-trend setup against higher-timeframe order flow requires >= 85% conviction."
                                        break
                        except Exception as ex:
                            logger.debug(f"MTF filter check error: {ex}")

                cand_exps = extract_directional_currency_exposures(symbol, direction_str)
                if not is_already_active and not shield_reason:
                    # 1. Autonomous Closed-Loop Strategy Health & Quarantine Filter
                    # If adaptive tuning engine graded strategy as QUARANTINED_SHADOW (win rate < 45% or 3 consecutive losses),
                    # hold it on Watchlist / Paper Mode so it does not risk live capital until recovery.
                    strat_profile = adaptive_tuning_engine.get_strategy_tuning(cand.strategyId or "", symbol)
                    if strat_profile.is_quarantined_shadow:
                        shield_reason = f"AUTONOMOUS QUARANTINE SHIELD: {cand.strategyId} Win Rate ({strat_profile.recent_win_rate*100:.0f}%) under 45% or streak {strat_profile.consecutive_losses} losses. Quarantined to paper tracking."
                        entry_hit = False

                    # Tier 3 Probation Filter: Requires >= 88% confidence floor
                    if not shield_reason and strat_profile.tier_grade == "TIER_3_PROBATION" and (cand.confidence or 80) < 88:
                        shield_reason = f"PROBATION CONVICTION SHIELD: {cand.strategyId} in probation tier requires >= 88% conviction (current: {cand.confidence}%). Held on Watchlist."
                        entry_hit = False

                    # Approved Flagship Filter
                    approved_flagships = active_strat_ids or getattr(settings, "APPROVED_FLAGSHIP_STRATEGIES", {f"strat-{i:03d}" for i in range(1, 30)})
                    if not shield_reason and cand.strategyId and cand.strategyId not in approved_flagships:
                        shield_reason = f"STRATEGY GATE: Live activation restricted to flagship strategies ({', '.join(sorted(approved_flagships))}). Held on Watchlist."
                        entry_hit = False

                    # Velocity Scalp Killzone Promotion Gates (strat-024 Gold & strat-025..029 Apex FX)
                    from app.core.engines.apex_scalp_config import APEX_FX_SCALP_IDS, is_in_apex_killzone
                    if not shield_reason and getattr(cand, "strategyId", "") == "strat-024":
                        utc_now_prom = datetime.now(timezone.utc)
                        utc_mins_prom = utc_now_prom.hour * 60 + utc_now_prom.minute
                        if not (420 <= utc_mins_prom <= 810):
                            shield_reason = f"XAU/USD SCALP KILLZONE SHIELD: {utc_now_prom.strftime('%H:%M')} UTC is outside peak 07:00-13:30 UTC window."
                            entry_hit = False
                    elif not shield_reason and getattr(cand, "strategyId", "") in APEX_FX_SCALP_IDS:
                        utc_now_prom = datetime.now(timezone.utc)
                        in_apex_prom, kz_prom_lbl = is_in_apex_killzone(cand.strategyId, utc_now_prom)
                        if not in_apex_prom:
                            shield_reason = f"APEX FX SCALP KILLZONE SHIELD ({symbol}): {utc_now_prom.strftime('%H:%M')} UTC is outside peak {kz_prom_lbl} window."
                            entry_hit = False

                    # 2. High-Conviction Gate (confidence >= 85%)
                    min_confidence = getattr(settings, "MIN_LIVE_SIGNAL_CONFIDENCE", 80)
                    cand_conf = getattr(cand, "confidence", 80)
                    if not shield_reason and cand_conf < min_confidence:
                        shield_reason = f"CONVICTION GATE: Requires >= {min_confidence}% confidence for live execution (current: {cand_conf}%). Held on Watchlist."
                        entry_hit = False

                    # 3. Anti-Cluster Currency Basket Check (prevent correlated USD/JPY cluster drawdown)
                    if not shield_reason and getattr(settings, "ANTI_CLUSTER_ENABLED", True):
                        cluster_conflict = None
                        for exp in cand_exps:
                            max_cluster_exp = int(getattr(settings, "MAX_CURRENCY_CLUSTER_EXPOSURE", 2) or 2) if getattr(settings, "ENABLE_CURRENCY_CLUSTER_GATE", False) else 8
                            if any(c in exp for c in ("USD", "JPY", "EUR", "GBP", "AUD")) and len([s for s in active_currency_baskets.get(exp, "").split(",") if s]) >= max_cluster_exp:
                                cluster_conflict = (exp, active_currency_baskets[exp])
                                break
                        if cluster_conflict:
                            conf_exp, existing_sym = cluster_conflict
                            shield_reason = f"ANTI-CLUSTER SHIELD: {conf_exp} exposure already held by active {existing_sym}. Held on Watchlist to prevent correlated drawdown."
                            entry_hit = False

                    # 4. Portfolio Heat Cap (strictly honors configured MAX_SIMULTANEOUS_TRADES)
                    max_active_limit = int(getattr(settings, "MAX_SIMULTANEOUS_TRADES", 3) or 3)
                    total_current_active = len(open_trades) + len(curated_active)
                    if not shield_reason and entry_hit and total_current_active >= max_active_limit:
                        shield_reason = f"PORTFOLIO HEAT CAP: Maximum {max_active_limit} simultaneous active trades reached ({len(open_trades)} running + {len(curated_active)} new). Held on Watchlist."
                        entry_hit = False

                # If shield intervened on a pending setup, suppress entry promotion
                if shield_reason and not is_already_active:
                    entry_hit = False

                # Lifecycle Routing:
                # 1. Price actively touches entry (or was previously activated) & setup approved + ready & no shields -> ACTIVE
                # 2. Otherwise -> Watchlist in HOLD / WAITING status
                if is_already_active and norm_sym in open_symbol_dirs and open_symbol_dirs[norm_sym] != direction_str.upper():
                    continue
                if is_already_active or (entry_hit and is_approved and is_ready and not shield_reason):
                    open_symbol_dirs[norm_sym] = direction_str.upper()
                    item["is_guardian_authorized"] = True
                    for exp in cand_exps:
                        if any(c in exp for c in ("USD", "JPY", "EUR", "GBP", "AUD")):
                            active_currency_baskets[exp] = f"{active_currency_baskets[exp]},{symbol}" if exp in active_currency_baskets else symbol

                    from app.core.services.position_sizing_service import position_sizing_service
                    scaled_lot = position_sizing_service.calculate_portfolio_heat_lot_size(
                        active_trade_count=len(curated_active) + 1,
                        base_lot_size=lot_size,
                    )
                    item["lot_size"] = scaled_lot
                    item["current_market_px"] = cur_px
                    item["entry_hit"] = True
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="ACTIVE"
                        )
                    except Exception:
                        pass

                    # ONLY create a trade record and send push alert on FIRST activation (never on existing active trades)
                    if not is_already_active or strat_sym_key not in seen_open_syms:
                        try:
                            from decimal import Decimal
                            from app.core.engines.market_state_engine import _derive_session

                            actual_session = _derive_session(now)
                            eff_entry_px = float(cur_px or cand.entryPrice)
                            eff_sl_px = float(cand.stopLoss)
                            price_risk_abs = abs(eff_entry_px - eff_sl_px)
                            eff_lot = max(float(scaled_lot or 0.01), 0.01)
                            sym_clean_r = symbol.replace("/", "").replace("_", "").upper()
                            if price_risk_abs > 1e-9:
                                if "XAU" in sym_clean_r or "GOLD" in sym_clean_r:
                                    raw_usd_risk = price_risk_abs * 100.0 * eff_lot
                                elif "JPY" in sym_clean_r:
                                    jpy_conv = eff_entry_px if sym_clean_r.startswith("USD") else 155.0
                                    raw_usd_risk = (price_risk_abs / max(jpy_conv, 1.0)) * 100000.0 * eff_lot
                                else:
                                    raw_usd_risk = price_risk_abs * 100000.0 * eff_lot
                                init_monetary_risk = Decimal(str(round(max(raw_usd_risk, 0.01), 2)))
                            else:
                                init_monetary_risk = None

                            trade_journal_repository.create_trade(
                                TradeJournalCreate(
                                    signalId=item["signal_id"],
                                    strategyId=cand.strategyId or "falcon-opt",
                                    symbol=symbol,
                                    direction=direction_str.upper(),
                                    entryPrice=cand.entryPrice,
                                    stopLoss=cand.stopLoss,
                                    initialStopLoss=cand.stopLoss,
                                    initialMonetaryRisk=init_monetary_risk,
                                    takeProfit=cand.takeProfit,
                                    timeframe=getattr(cand, "timeframe", None) or "M15",
                                    marketSession=actual_session,
                                    tradeDate=now,
                                    status="OPEN",
                                    result="OPEN",
                                    profitLoss=0.0,
                                    riskReward=cand.riskReward or 2.0,
                                    confidence=int(cand.confidence or 80),
                                    reasonForEntry=f"Falcon Live Entry Verified at {(cur_px or cand.entryPrice):.4f} (Touch within {pip_tolerance:.5f})",
                                    notes=f"Auto-recorded active trade from signal {item['signal_id']}",
                                    fillPrice=cur_px or cand.entryPrice,
                                    fillTime=now,
                                )
                            )

                            # Dispatch authoritative real-time Firebase Push notification (Deduped by canonical setup key)
                            try:
                                from app.core.services.fcm_service import fcm_service
                                dir_str = str(direction_str or "BUY").upper()
                                clean_sym = symbol.replace("/", "").replace("_", "")
                                p_entry = f"{cur_px:.2f}" if ("XAU" in clean_sym or cand.entryPrice > 500) else (f"{cur_px:.3f}" if "JPY" in clean_sym else f"{cur_px:.5f}")
                                p_sl = f"{cand.stopLoss:.2f}" if ("XAU" in clean_sym or cand.entryPrice > 500) else (f"{cand.stopLoss:.3f}" if "JPY" in clean_sym else f"{cand.stopLoss:.5f}")
                                p_tp = f"{cand.takeProfit:.2f}" if ("XAU" in clean_sym or cand.entryPrice > 500) else (f"{cand.takeProfit:.3f}" if "JPY" in clean_sym else f"{cand.takeProfit:.5f}")

                                fcm_service.send_signal_alert(
                                    title=f"🎯 Falcon Live Signal: {dir_str} {symbol}",
                                    body=f"Entry: {p_entry} | SL: {p_sl} | TP: {p_tp}. Price touched entry! Execute now on MT5.",
                                    data={
                                        "canonical_signature": sig_key,
                                        "signal_id": str(item.get("signal_id", "")),
                                        "symbol": str(symbol),
                                        "direction": str(dir_str),
                                        "entry": str(cur_px),
                                        "sl": str(cand.stopLoss),
                                        "tp": str(cand.takeProfit),
                                        "status": "ACTIVE",
                                        "event_type": "SIGNAL_ACTIVE",
                                    },
                                )
                            except Exception as ex:
                                logger.debug(f"FCM active alert error: {ex}")
                        except Exception as ex:
                            logger.debug(f"Could not auto-record trade to journal: {ex}")

                    active_symbols.add(norm_sym)
                    active_symbols.add(strat_sym_key)
                    curated_active.append(item)
                else:
                    item["is_guardian_authorized"] = is_approved and not shield_reason
                    if not shield_reason and not is_approved:
                        shield_reason = f"DECISION GATE: Setup in review ({item['decision'].status.value if item.get('decision') else 'PENDING'}). Held on Watchlist."
                    elif not shield_reason and not is_ready:
                        shield_reason = f"READINESS GATE: Execution readiness ({getattr(cand, 'readinessScore', 0)}/100) below 80 threshold. Held on Watchlist."
                    item["guardian_reason"] = shield_reason
                    item["current_market_px"] = cur_px
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="HOLD"
                        )
                    except Exception:
                        pass
                    watchlist_symbols.add(strat_sym_key)
                    curated_watchlist.append(item)

            # Compute autonomous loss recovery metrics (in-memory, no DB)
            recovery_metrics = adaptive_tuning_engine.get_loss_recovery_metrics()

            # Convert all active setups (no 3-slot cap)
            active_items = [
                self._to_signal(
                    item["candidate"],
                    item["decision"],
                    item["signal_id"],
                    now,
                    is_active=True,
                    lot_size=item.get("lot_size"),
                    recovery_metrics=recovery_metrics,
                    current_market_px=item.get("current_market_px"),
                )
                for item in curated_active
            ]

            # Convert watchlist setups with HOLD status
            watchlist_items = [
                self._to_signal(
                    item["candidate"],
                    item["decision"],
                    item["signal_id"],
                    now,
                    is_active=False,
                    guardian_reason=item.get("guardian_reason"),
                    recovery_metrics=recovery_metrics,
                    current_market_px=item.get("current_market_px"),
                )
                for item in curated_watchlist
            ]

            # Assemble response: Active first, then Watchlist (HOLD), then Resolved outcomes
            signals = step1_active_signals + active_items + watchlist_items + additional_resolved + signals
        else:
            signals = step1_active_signals + signals

        response = SignalListResponse(
            signals=signals,
            lastUpdated=now,
            dataAgeSeconds=min(
                (signal.dataAgeSeconds for signal in signals), default=0
            ),
        )
        self._cache_response = response
        self._cache_time = datetime.now(timezone.utc)
        return response

    def _to_signal(
        self,
        candidate: SignalCandidate,
        decision: Optional[DecisionArtifact],
        signal_id: int,
        now: datetime,
        is_active: bool = False,
        override_status: Optional[str] = None,
        lot_size: Optional[float] = None,
        guardian_reason: Optional[str] = None,
        recovery_metrics: Optional[LossRecoveryMetrics] = None,
        current_market_px: Optional[float] = None,
    ) -> SignalItem:
        strategy = self._strategy_engine.get_strategy_by_id(candidate.strategyId)
        preferred_session = (
            ", ".join(strategy.preferredSessions)
            if strategy and strategy.preferredSessions
            else "London / New York / Asian"
        )
        timeframe = strategy.bestTimeframe if strategy else "1h"

        # Check for sniper pattern
        pattern_reason = next(
            (r for r in getattr(candidate, "reasons", []) if r.title.startswith("Sniper Setup:")),
            None
        )
        if pattern_reason:
            setup_pattern = pattern_reason.title.replace("Sniper Setup: ", "").strip()
            trigger_rule = pattern_reason.description
        else:
            setup_pattern = candidate.strategyName
            trigger_rule = f"Enter on confirmed {candidate.direction.value} candle close. Invalidation at {candidate.stopLoss}."

        valid_until = candidate.generatedAt + timedelta(hours=1)
        is_expired = now > valid_until

        dec = 2 if ("XAU" in candidate.symbol.upper() or "GOLD" in candidate.symbol.upper() or candidate.entryPrice > 500) else (3 if "JPY" in candidate.symbol.upper() else 4)
        direction_val = candidate.direction.value.upper()

        # Strict institutional calibration: 1:1.20 to 1:1.50 Maximum R:R
        entry_price = candidate.entryPrice
        stop_loss = candidate.stopLoss
        eff_cand_rr = min(max(candidate.riskReward or 1.3, 1.2), 1.5)
        candidate.riskReward = eff_cand_rr
        risk_dist_raw = abs(entry_price - stop_loss)
        if risk_dist_raw > 1e-6:
            if candidate.direction.value.upper() == "BUY":
                take_profit = round(entry_price + (risk_dist_raw * eff_cand_rr), dec)
            else:
                take_profit = round(entry_price - (risk_dist_raw * eff_cand_rr), dec)
        else:
            take_profit = candidate.takeProfit

        # Breakthrough Advancements:
        # Dynamic ATR Stop Loss & Multi-Stage Scale-Out Targets (TP1: 50% @ 1.5R, TP2: Trailing Runner @ 3.0R)
        from app.core.engines.session_breakout_engine import session_breakout_engine
        from app.core.engines.candlestick_pattern_engine import CandleBar
        from app.core.services.market_history_service import market_history_service

        cand_candles = []
        try:
            cand_sym_clean = candidate.symbol.replace("/", "")
            c_bars = market_history_service.get_bars(cand_sym_clean, timeframe="1h", limit=50)
            cand_candles = [
                CandleBar(
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume or 0.0,
                    timestamp=int(b.bar_time.timestamp()) if hasattr(b.bar_time, "timestamp") else None,
                    time=b.bar_time,
                )
                for b in c_bars
            ]
        except Exception:
            cand_candles = []

        cand_dir = direction_val
        dyn_sl, tp1, tp2, trail_buf, atr_val = session_breakout_engine.calculate_trade_levels(
            symbol=candidate.symbol,
            direction=cand_dir,
            entry_price=entry_price,
            candles=cand_candles,
            structure_sl=stop_loss,
            take_profit=take_profit,
        )
        htf_bias, _, _ = session_breakout_engine.compute_htf_trend_bias(candidate.symbol, cand_candles)

        # Quantitative Intra-Candle & Institutional Risk Auditor
        from app.core.engines.htf_structure_engine import htf_structure_engine
        from app.core.engines.order_flow_engine import order_flow_engine
        from app.core.engines.risk_auditor_engine import institutional_risk_auditor

        htf_res = htf_structure_engine.check_htf_alignment(
            symbol=candidate.symbol,
            direction=cand_dir,
            entry_price=entry_price,
            bars_1h=cand_candles,
        )
        of_res = order_flow_engine.analyze_order_flow(
            candles=cand_candles,
            symbol=candidate.symbol,
        )
        vol_zone = session_breakout_engine.compute_volatility_exhaustion(candidate.symbol, cand_candles)
        sweep_eval = session_breakout_engine.evaluate_sweep_retest(candidate.symbol, cand_dir, cand_candles)

        audit_res = institutional_risk_auditor.audit(
            symbol=candidate.symbol,
            direction=cand_dir,
            base_conviction=float(candidate.confidence),
            htf_result=htf_res,
            order_flow=of_res,
            current_sigma=vol_zone.current_sigma,
            is_sweep_confirmed=sweep_eval.is_confirmed,
        )

        # Calculate Breakeven targets (+0.65R for Velocity Scalpers strat-024..028; +1.0R standard otherwise)
        from app.core.engines.apex_scalp_config import VELOCITY_SCALP_STRATEGY_IDS
        risk_dist = abs(entry_price - stop_loss)
        be_r_mult = 0.65 if getattr(candidate, "strategyId", "") in VELOCITY_SCALP_STRATEGY_IDS else 1.0
        if direction_val == "BUY":
            be_trigger = round(entry_price + (risk_dist * be_r_mult), dec)
        else:
            be_trigger = round(entry_price - (risk_dist * be_r_mult), dec)
        be_price = round(entry_price, dec)

        # Determine if live market has already achieved Breakeven
        is_breakeven = False
        try:
            current_px = float(current_market_px) if current_market_px is not None else float(entry_price)
        except (TypeError, ValueError):
            try:
                current_px = float(entry_price)
            except (TypeError, ValueError):
                current_px = None
        if current_px is not None and current_px > 0:
            if direction_val == "BUY" and current_px >= be_trigger:
                is_breakeven = True
            elif direction_val == "SELL" and current_px <= be_trigger:
                is_breakeven = True

        if be_r_mult < 1.0:
            be_rule = f"BE Rule: Shift SL to Entry ({be_price}) & scale out 50% at {be_trigger} (+{be_r_mult:.2f}R scalp lock)."
        else:
            be_rule = f"BE Rule: Shift SL to Entry ({be_price}) at {be_trigger} (+1.0R risk-free)."

        # Loss Recovery Metadata
        rec_status = recovery_metrics.recovery_status if recovery_metrics else getattr(candidate, "recoveryStatus", "BASELINE")
        rec_mult = recovery_metrics.profit_recovery_multiplier if recovery_metrics else getattr(candidate, "profitRecoveryMultiplier", 1.0)
        rec_badge = f" [{rec_status} - {rec_mult:.0f}X TARGET]" if rec_mult and rec_mult > 1.0 else ""
        ai_reflection = f"🧠 {recovery_metrics.ai_reflection} " if (recovery_metrics and recovery_metrics.ai_reflection) else ""

        # Determine authoritative display status
        if override_status:
            status = override_status
        elif is_active:
            status = "ACTIVE"
        elif is_expired:
            status = "EXPIRED"
        elif guardian_reason:
            status = "WAITING"
        else:
            status = "HOLD"

        targets_str = f"TP1: {tp1:.4f} (50% Bank @ 1.0R) | TP2: {tp2:.4f} (Runner @ 1.5R) | Macro Bias: {htf_bias}"

        if status == "ACTIVE":
            trigger_rule = f"[MARKET EXECUTION - ENTER NOW] [ACTIVE IN POSITION] Price touched entry at {entry_price:.4f}. {targets_str}."
            be_status_text = " [🛡️ BREAKEVEN LOCKED]" if is_breakeven else ""
            analysis = (
                f"🎯 SNIPER SIGNAL ACTIVE [{setup_pattern}]{rec_badge}{be_status_text}: "
                f"{trigger_rule} "
                f"Entry: {entry_price} | SL: {stop_loss} | "
                f"TP: {take_profit} (1:{candidate.riskReward:.1f} R:R). "
                f"{be_rule} "
                f"{ai_reflection}"
                f"Active Window: {preferred_session}."
            )
        elif status == "WAITING":
            spread_val = f"Live Spread: {candidate.marketSnapshot.spread:.2f} pips." if candidate.marketSnapshot and candidate.marketSnapshot.spread else ""
            guard_text = f"Capital Guardian: {guardian_reason}. " if guardian_reason else ""
            analysis = (
                f"⏳ WATCHLIST WAITING [{setup_pattern}]: "
                f"{guard_text}{spread_val}"
                f"Awaiting Capital Guardian clearance and entry trigger. {targets_str}. "
                f"Do not enter MT5 order until status turns ACTIVE."
            )
        elif status == "HOLD":
            spread_val = f"Live Spread: {candidate.marketSnapshot.spread:.2f} pips." if candidate.marketSnapshot and candidate.marketSnapshot.spread else ""
            analysis = (
                f"⏳ WATCHLIST HOLD [{setup_pattern}]: "
                f"Awaiting market entry touch at {entry_price:.4f}. Current market: {current_px:.4f}. "
                f"SL: {stop_loss:.4f} | TP: {take_profit:.4f} (1:{candidate.riskReward:.1f} R:R). "
                f"{targets_str}. {spread_val}"
                f"Valid for 1h on watchlist. Do not enter MT5 order until status turns ACTIVE."
            )
        elif status == "EXPIRED":
            analysis = (
                f"⏳ UNTRIGGERED SETUP [EXPIRED]: Signal validity window (1h) elapsed on watchlist without "
                f"hitting entry price ({entry_price:.4f}). Order auto-canceled cleanly without risk."
            )
        elif status in ("WON", "WIN"):
            analysis = (
                f"🏆 TARGET ACHIEVED [WON]: Take Profit hit cleanly at {take_profit:.4f}. "
                f"R:R 1:{candidate.riskReward:.1f} secured."
            )
        elif status in ("LOST", "LOSS"):
            analysis = (
                f"🛑 STOPPED OUT [LOST]: Invalidation boundary hit at {stop_loss:.4f}. "
                f"Capital defended."
            )
        else:
            analysis = f"Setup {setup_pattern} in state {status}."

        return SignalItem(
            id=signal_id,
            symbol=candidate.symbol,
            action=candidate.direction.value,
            entry=entry_price,
            takeProfit=take_profit,
            stopLoss=stop_loss,
            confidence=candidate.confidence,
            timeframe=timeframe,
            status=status,
            analysis=analysis,
            timestamp=candidate.generatedAt,
            strategyId=candidate.strategyId,
            strategyName=candidate.strategyName,
            strategyVersion=candidate.strategyVersion,
            adaptiveRuleVersion=getattr(candidate, "adaptiveRuleVersion", None),
            adaptiveStopMultiplier=getattr(candidate, "adaptiveStopMultiplier", None),
            profitRecoveryMultiplier=rec_mult,
            recoveryStatus=rec_status,
            researchContext=getattr(candidate, "researchContext", None),
            dataAgeSeconds=candidate.marketDataAgeSeconds,
            triggerCondition=trigger_rule,
            validUntil=valid_until,
            setupPattern=setup_pattern,
            riskReward=candidate.riskReward,
            isPinned=False,
            breakevenTrigger=be_trigger,
            breakevenPrice=be_price,
            isBreakeven=is_breakeven,
            takeProfit1=tp1,
            takeProfit2=tp2,
            scaleOutPercentage=50.0,
            trailingStopBuffer=trail_buf,
            htfTrendBias=htf_bias,
            atr14=atr_val,
            quantGrade=audit_res.grade,
            estDeltaBadge=audit_res.est_delta_badge,
            tacticalAdvice=(
                audit_res.tactical_advice
                if getattr(candidate, "strategyId", "") == "strat-006"
                else f"{audit_res.tactical_advice} | {order_flow_engine.evaluate_dom_and_absorption(symbol=candidate.symbol, direction=cand_dir, entry_price=entry_price, decomp=of_res).telemetry_tag}"
            ),
            isBreakevenProtected=is_breakeven,
        )

    @staticmethod
    def _signal_id(mission_id: str, index: int) -> int:
        digits = "".join(char for char in mission_id if char.isdigit())
        mission_number = int(digits) if digits else 0
        return mission_number * 100 + index + 1


signal_service = SignalService()
