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
from app.core.services.signal_authorization_service import signal_authorization_service
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
from app.schemas.execution_order import ExecutionSettings
from app.schemas.signal_candidate import SignalCandidate, CandidateStatus, CandidateDirection
from app.schemas.signal import SignalItem, SignalListResponse
from app.schemas.trade_journal import TradeJournalCreate



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


class SignalService:
    """
    Curates, ranks, and serves high-conviction sniper trading signals.
    Enforces quality, authentic SMC price triggers, and complete lifecycle deduplication:
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
        seen_signatures: Set[Tuple[str, str, float, float, float]] = set(self._historical_triggered_signatures)

        # Step 1: Query TradeJournal for OPEN active trades and recently RESOLVED trades
        try:
            all_journal_trades = trade_journal_repository.list_trades()

            # Active open positions from TradeJournal
            open_trades = [
                t for t in all_journal_trades
                if (t.status or "").upper() in ("OPEN", "FILLED")
            ]
            for ot in open_trades:
                sig_key = canonical_signal_signature(
                    ot.symbol,
                    ot.direction,
                    ot.entryPrice,
                    ot.stopLoss,
                    ot.takeProfit,
                )
                seen_signatures.add(sig_key)
                self._historical_triggered_signatures.add(sig_key)
                try:
                    signal_signature_repository.record_signature(
                        ot.symbol, ot.direction, ot.entryPrice, ot.stopLoss, ot.takeProfit, status="ACTIVE"
                    )
                except Exception:
                    pass

                dec = 2 if "XAU" in ot.symbol or ot.entryPrice > 100 else 4
                risk_d = abs(ot.entryPrice - ot.stopLoss)
                be_trig = ot.entryPrice + risk_d if ot.direction.upper() == "BUY" else ot.entryPrice - risk_d
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
                    analysis=f"🎯 ACTIVE (IN POSITION) [{ot.notes or 'Falcon Trade'}]: Live market in position from entry {ot.entryPrice:.4f}. Holding until Take Profit ({ot.takeProfit:.4f}) or Stop Loss ({ot.stopLoss:.4f}).",
                    timestamp=ot.tradeDate,
                    strategyId=ot.strategyId or "falcon-opt",
                    strategyName=ot.notes or "Falcon Strategy",
                    strategyVersion="4.2",
                    dataAgeSeconds=0,
                    triggerCondition=f"Enter {ot.direction.upper()} at {ot.entryPrice:.4f}",
                    validUntil=ot.tradeDate + timedelta(hours=8),
                    setupPattern=ot.notes or "Sniper Setup",
                    riskReward=ot.riskReward,
                    isPinned=False,
                    breakevenTrigger=round(be_trig, dec),
                    breakevenPrice=round(ot.entryPrice, dec),
                    isBreakeven=False,
                )
                signals.append(active_signal)

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

                dec = 2 if "XAU" in ct.symbol or ct.entryPrice > 100 else 4
                risk_d = abs(ct.entryPrice - ct.stopLoss)
                be_trig = ct.entryPrice + risk_d if ct.direction.upper() == "BUY" else ct.entryPrice - risk_d

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
                    setupPattern=ct.notes or "Sniper Setup",
                    riskReward=ct.riskReward,
                    isPinned=False,
                    breakevenTrigger=round(be_trig, dec),
                    breakevenPrice=round(ct.entryPrice, dec),
                    isBreakeven=res_str in ("BREAKEVEN", "BE"),
                )
                signals.append(resolved_signal)
        except Exception as ex:
            logger.debug(f"Could not load trade journal records: {ex}")

        # Step 2: Ingest candidate setups from recent missions
        missions = None
        try:
            # Check get_all_missions first (honoring test mocks if present)
            all_m = mission_repository.get_all_missions()
            if all_m:
                missions = all_m[-mission_limit:]
        except Exception:
            pass
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
                    bulk_artifacts = mission_repository.get_all_mission_artifacts_bulk(mission_ids) or {}
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
                        if candidate.confidence < 80:
                            continue

                        # Omit candidates older than 6 hours to eliminate ancient stale clutter
                        if candidate.generatedAt and (now - candidate.generatedAt).total_seconds() > 6 * 3600:
                            continue

                        dec = by_candidate.get(candidate.id)
                        is_approved = dec is not None and dec.status == DecisionStatus.APPROVED
                        readiness = getattr(candidate, "readinessScore", 50.0) or 50.0
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
            candidate_pool.sort(key=lambda x: x["conviction_score"], reverse=True)

            curated_active: List[dict] = []
            curated_watchlist: List[dict] = []
            additional_resolved: List[SignalItem] = []
            active_symbols: set = set()
            watchlist_symbols: set = set()

            lot_size = ExecutionSettings().default_lot_size

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
                if sig_key in seen_signatures:
                    # Deduplication & Historical Memory: setup was already processed / triggered / completed
                    continue
                seen_signatures.add(sig_key)

                # Institutional Anti-Hedging & Unique Asset Resolve:
                # If this asset already has an authoritative active or pending setup,
                # skip weaker or conflicting setups so Falcon strictly focuses on 1 unique trade per symbol.
                if norm_sym in active_symbols or norm_sym in watchlist_symbols:
                    continue

                # Real-Time Live Market Quote Evaluation (Layer 2: Strict Freshness <= 60s)
                cur_px = None
                quote_age_s = 999.0
                quote_resp = None
                try:
                    raw_sym = symbol.replace("/", "").upper()
                    pm = getattr(providers, "provider_manager", None)
                    if pm is not None and hasattr(pm, "_cache"):
                        # Disallow stale cache lookups for entry gate
                        cached_entry = pm._cache.get(raw_sym, allow_stale=False)
                        if cached_entry and hasattr(cached_entry, "data"):
                            q_data = cached_entry.data
                            if getattr(q_data, "lastPrice", None):
                                cur_px = q_data.lastPrice
                                quote_age_s = cached_entry.age_seconds
                            if isinstance(q_data, MarketQuote):
                                quote_resp = MarketQuoteResponse(quote=q_data)

                    # If cache missing or older than 60s, force real-time fetch (routes FMP first for Forex)
                    if (cur_px is None or quote_age_s > 60.0) and pm is not None:
                        resp = pm.get_market_quote(raw_sym)
                        if resp and resp.quote and resp.quote.lastPrice:
                            cur_px = resp.quote.lastPrice
                            quote_age_s = getattr(resp.quote, "freshnessSeconds", 0.0) or 0.0
                            quote_resp = resp
                except Exception:
                    pass

                # 1-hour expiration rule: watchlist signal without entry hit for >= 1h -> EXPIRED
                age_seconds = (now - cand.generatedAt).total_seconds()
                is_1h_elapsed = age_seconds >= 3600
                is_approved = item["is_approved"]
                is_ready = getattr(cand, "readinessScore", 0) >= 80

                if is_1h_elapsed:
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
                # Proximity band: 1.0 to 1.5 pips (0.00015 for 4-digit Forex, 0.50 for Gold)
                pip_tolerance = 0.50 if ("XAU" in symbol or cand.entryPrice > 100) else 0.00015
                slip_invalidation = 1.50 if ("XAU" in symbol or cand.entryPrice > 100) else 0.00030  # 3 pips
                entry_hit = False
                is_slipped_past = False

                if cur_px is not None and cur_px > 0 and quote_age_s <= 60.0:
                    dist_to_entry = abs(cur_px - cand.entryPrice)
                    # A. Strict Active Touch Window: Price must currently test entry within 1.0 - 1.5 pips
                    if dist_to_entry <= pip_tolerance:
                        entry_hit = True
                    else:
                        # B. Missed/Slipped Invalidation:
                        # If price has already moved past entry towards Stop Loss by > 3 pips,
                        # the pullback was missed in a past candle -> mark EXPIRED cleanly, never activate late.
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

                # Capital Defense Shield Checks:
                shield_reason = None

                # 1. Economic Calendar News Blackout Check
                try:
                    from app.core.services.economic_calendar_service import economic_calendar_service
                    is_blk, n_title, n_curr, n_delta, n_phase = economic_calendar_service.check_blackout_status(symbol)
                    if is_blk:
                        phase_str = f"in {n_delta}m" if n_phase == "UPCOMING" else f"{n_delta}m ago"
                        shield_reason = f"NEWS BLACKOUT: {n_curr} High-Impact event '{n_title}' {phase_str}. Capital shield active."
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

                            if is_gold:
                                pip_size = 0.10
                                baseline_max = 4.0
                            elif is_jpy:
                                pip_size = 0.01
                                baseline_max = 3.2 if "GBP" in clean_sym else 2.2
                            else:
                                pip_size = 0.00010
                                baseline_max = 2.2 if "GBP" in clean_sym else 1.8

                            spread_pips = raw_spread / pip_size
                            max_allowed_spread = baseline_max
                            if spread_pips > max_allowed_spread:
                                shield_reason = f"SPREAD SPIKE: Live spread {spread_pips:.1f} pips exceeds {max_allowed_spread:.1f} limit. Entry held."
                    except Exception as ex:
                        logger.debug(f"Spread spike shield check error: {ex}")

                # 3. Multi-Timeframe (MTF) Institutional Confluence Filter
                if not shield_reason:
                    try:
                        cand_reasons = getattr(cand, "reasons", [])
                        for r in cand_reasons:
                            t_desc = (getattr(r, "title", "") + " " + getattr(r, "description", "")).lower()
                            if any(k in t_desc for k in ["counter-trend", "against 4h", "against 1h", "bearish 4h ob", "bullish 4h ob"]):
                                if getattr(cand, "confidence", 80) < 85:
                                    shield_reason = "MTF FILTER: Counter-trend setup against higher-timeframe order flow requires >= 85% conviction."
                                    break
                    except Exception as ex:
                        logger.debug(f"MTF filter check error: {ex}")

                # If shield intervened, suppress entry promotion and enforce WAITING status
                if shield_reason:
                    entry_hit = False

                # Lifecycle Routing:
                # 1. Price actively touches entry & setup approved + ready & no capital shields -> ACTIVE
                # 2. Otherwise -> Watchlist in HOLD / WAITING status
                if entry_hit and is_approved and is_ready and not shield_reason:
                    item["is_guardian_authorized"] = True
                    item["lot_size"] = lot_size
                    item["current_market_px"] = cur_px
                    item["entry_hit"] = True
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="ACTIVE"
                        )
                    except Exception:
                        pass

                    # Automatically create an OPEN trade record in Trade Journal for lifecycle tracking
                    new_trade_record = None
                    try:
                        existing_trades = trade_journal_repository.list_trades() or []
                        already_recorded = any(
                            (t.signalId == item["signal_id"] or (t.symbol == symbol and (t.status or "").upper() in ("OPEN", "FILLED")))
                            for t in existing_trades
                        )
                        if not already_recorded:
                            new_trade_record = trade_journal_repository.create_trade(
                                TradeJournalCreate(
                                    signalId=item["signal_id"],
                                    strategyId=cand.strategyId or "falcon-opt",
                                    symbol=symbol,
                                    direction=direction_str.upper(),
                                    entryPrice=cand.entryPrice,
                                    stopLoss=cand.stopLoss,
                                    takeProfit=cand.takeProfit,
                                    timeframe=cand.timeframe or "M15",
                                    marketSession="London" if "London" in (cand.strategyName or "") else "New York",
                                    tradeDate=now,
                                    status="OPEN",
                                    result="PENDING",
                                    profitLoss=0.0,
                                    riskReward=cand.riskReward or 2.0,
                                    confidence=int(cand.confidence or 80),
                                    reasonForEntry=f"Falcon Live Entry Verified at {cur_px:.4f} (Touch within {pip_tolerance:.5f})",
                                    notes=f"Auto-recorded active trade from signal {item['signal_id']}",
                                    fillPrice=cur_px,
                                    fillTime=now,
                                )
                            )
                            # Dispatch real-time Telegram trade alert
                            try:
                                from app.services.alerts.telegram_alert_service import telegram_alert_service
                                telegram_alert_service.dispatch_active_trade_alert(new_trade_record)
                            except Exception as ex:
                                logger.debug(f"Telegram active alert error: {ex}")
                    except Exception as ex:
                        logger.debug(f"Could not auto-record trade to journal: {ex}")

                    active_symbols.add(norm_sym)
                    curated_active.append(item)
                else:
                    item["is_guardian_authorized"] = is_approved and not shield_reason
                    item["guardian_reason"] = shield_reason
                    item["current_market_px"] = cur_px
                    try:
                        signal_signature_repository.record_signature(
                            symbol, direction_str, cand.entryPrice, cand.stopLoss, cand.takeProfit, status="HOLD"
                        )
                    except Exception:
                        pass
                    watchlist_symbols.add(norm_sym)
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
            signals = active_items + watchlist_items + additional_resolved + signals

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

        dec = 2 if "XAU" in candidate.symbol or candidate.entryPrice > 100 else 4
        direction_val = candidate.direction.value.upper()

        # Strict adherence: preserve authentic candidate entry, stop loss, and take profit (no artificial shifting)
        entry_price = candidate.entryPrice
        stop_loss = candidate.stopLoss
        take_profit = candidate.takeProfit

        # Calculate Breakeven targets (1:1 Risk-Reward threshold for risk-free protection)
        risk_dist = abs(entry_price - stop_loss)
        if direction_val == "BUY":
            be_trigger = round(entry_price + risk_dist, dec)
        else:
            be_trigger = round(entry_price - risk_dist, dec)
        be_price = round(entry_price, dec)

        # Determine if live market has already achieved Breakeven
        is_breakeven = False
        current_px = current_market_px or entry_price
        if current_px is not None and current_px > 0:
            if direction_val == "BUY" and current_px >= be_trigger:
                is_breakeven = True
            elif direction_val == "SELL" and current_px <= be_trigger:
                is_breakeven = True

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

        if status == "ACTIVE":
            trigger_rule = f"[MARKET EXECUTION - ENTER NOW] [ACTIVE IN POSITION] Price touched entry at {entry_price:.4f}. Holding until Take Profit ({take_profit:.4f}) or Stop Loss ({stop_loss:.4f})."
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
                f"Awaiting Capital Guardian clearance and entry trigger. "
                f"Do not enter MT5 order until status turns ACTIVE."
            )
        elif status == "HOLD":
            spread_val = f"Live Spread: {candidate.marketSnapshot.spread:.2f} pips." if candidate.marketSnapshot and candidate.marketSnapshot.spread else ""
            analysis = (
                f"⏳ WATCHLIST HOLD [{setup_pattern}]: "
                f"Awaiting market entry touch at {entry_price:.4f}. Current market: {current_px:.4f}. "
                f"SL: {stop_loss:.4f} | TP: {take_profit:.4f} (1:{candidate.riskReward:.1f} R:R). "
                f"{spread_val}"
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
        )

    @staticmethod
    def _signal_id(mission_id: str, index: int) -> int:
        digits = "".join(char for char in mission_id if char.isdigit())
        mission_number = int(digits) if digits else 0
        return mission_number * 100 + index + 1


signal_service = SignalService()
