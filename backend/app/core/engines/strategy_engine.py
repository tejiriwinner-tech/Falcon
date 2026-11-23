import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.schemas.strategy import (
    StrategyItem, StrategyType, StrategyCategory, StrategyStatus,
    StrategyHealth, RiskLevel, StrategyPerformance, StrategyScore,
    MarketSnapshot, StrategyValidationCheck, StrategyValidation
)
from app.core.strategy_metrics import (
    EMPTY_PERFORMANCE,
    latest_validation_by_strategy,
    last_used_by_strategy,
    performance_by_strategy,
)


def _empty_score() -> StrategyScore:
    return StrategyScore(
        historicalScore=0,
        currentMarketScore=0,
        overallScore=0,
        historicalPerformance=0,
        currentMarketFit=0,
        currentNewsScore=0,
        sessionMatch=0,
        riskRating=RiskLevel.MEDIUM,
    )


def _empty_validation() -> StrategyValidation:
    return StrategyValidation(
        score=0,
        aiConfidence=0,
        validationDurationSeconds=0.0,
        failedChecks=[],
        checks=[],
        marketSnapshot=MarketSnapshot(
            trend="unknown",
            volatility="unknown",
            liquidity="unknown",
            news="unknown",
            session="unknown",
            spread=0.0,
            atr=0.0,
            rsi=0.0,
            ema200="unknown",
            adx=0.0,
        ),
    )


logger = logging.getLogger("falcon.strategy_engine")

STRATEGY_STATUS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "strategy_status.json")
)

EXPANSION_STRATEGY_IDS: Set[str] = {
    "strat-013",
    "strat-014",
    "strat-015",
    "strat-016",
    "strat-017",
    "strat-018",
}


class StrategyEngine:
    # Shared process-wide runtime pause controls (controllable via REST API and Falcon AI Co-Pilot)
    _paused_strategy_ids: Set[str] = set()
    _paused_symbols: Set[str] = set()
    _expansion_paused: bool = False
    _status_overrides: Dict[str, StrategyStatus] = {}
    _loaded_persisted: bool = False
    _cached_strategies: Optional[List[StrategyItem]] = None
    _cached_strategies_at: float = 0.0

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cached_strategies = None
        cls._cached_strategies_at = 0.0
        try:
            from app.core.services.signal_service import signal_service
            signal_service._cache_response = None
            signal_service._cache_time = None
        except Exception:
            pass

    @classmethod
    def _load_persisted_status(cls):
        if cls._loaded_persisted:
            return
        cls._loaded_persisted = True
        try:
            if os.path.exists(STRATEGY_STATUS_FILE):
                with open(STRATEGY_STATUS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for sid, stat_str in data.items():
                            try:
                                cls._status_overrides[sid.lower()] = StrategyStatus(stat_str)
                            except ValueError:
                                pass
        except Exception as ex:
            logger.debug(f"Failed to load persisted strategy status: {ex}")
        try:
            from app.core.database.session import database_enabled, get_engine, get_session
            from app.core.database.models import Base, StrategyStatusRecord
            from sqlalchemy import select
            if database_enabled():
                engine = get_engine()
                Base.metadata.create_all(bind=engine, tables=[StrategyStatusRecord.__table__], checkfirst=True)
                session = get_session()
                try:
                    rows = session.execute(select(StrategyStatusRecord)).scalars().all()
                    for row in rows:
                        try:
                            cls._status_overrides[row.strategy_id.lower()] = StrategyStatus(row.status)
                        except ValueError:
                            pass
                finally:
                    session.close()
        except Exception as ex:
            logger.debug(f"Failed to load persisted strategy status from DB: {ex}")

    @classmethod
    def _save_persisted_status(cls):
        try:
            os.makedirs(os.path.dirname(STRATEGY_STATUS_FILE), exist_ok=True)
            data = {sid: stat.value for sid, stat in cls._status_overrides.items()}
            with open(STRATEGY_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as ex:
            logger.debug(f"Failed to save persisted strategy status: {ex}")
        try:
            from app.core.database.session import database_enabled, get_engine, get_session
            from app.core.database.models import Base, StrategyStatusRecord
            if database_enabled():
                engine = get_engine()
                Base.metadata.create_all(bind=engine, tables=[StrategyStatusRecord.__table__], checkfirst=True)
                now = datetime.now(timezone.utc)
                session = get_session()
                try:
                    for sid, stat in cls._status_overrides.items():
                        rec = session.get(StrategyStatusRecord, sid.lower())
                        if rec is None:
                            session.add(StrategyStatusRecord(strategy_id=sid.lower(), status=stat.value, updated_at=now))
                        else:
                            rec.status = stat.value
                            rec.updated_at = now
                    session.commit()
                except Exception as ex:
                    session.rollback()
                    logger.debug(f"Failed to persist strategy status to DB: {ex}")
                finally:
                    session.close()
        except Exception as ex:
            logger.debug(f"Failed to save persisted strategy status to DB: {ex}")

    def __init__(self):
        self.version = "2.1.0"
        self._load_persisted_status()
        self._strategies = self._init_strategies()

    @classmethod
    def _is_strategy_paused(cls, strategy: StrategyItem) -> bool:
        if strategy.id in cls._paused_strategy_ids:
            return True
        norm_sym = (strategy.symbol or "").replace("/", "").replace("_", "").upper()
        if norm_sym in cls._paused_symbols:
            return True
        if cls._expansion_paused and strategy.id in EXPANSION_STRATEGY_IDS:
            return True
        return False

    def pause_strategy(self, strategy_id: str) -> Optional[StrategyItem]:
        """Pause a specific strategy by ID (e.g. 'strat-013')."""
        sid = (strategy_id or "").strip().lower()
        for s in self._strategies:
            if s.id.lower() == sid or s.name.lower() == sid:
                self.__class__._paused_strategy_ids.add(s.id)
                self.__class__._status_overrides[s.id.lower()] = StrategyStatus.PAUSED
                self._save_persisted_status()
                self.invalidate_cache()
                out = s.model_copy(deep=True)
                out.status = StrategyStatus.PAUSED
                out.readyForExecution = False
                return out
        return None

    def resume_strategy(self, strategy_id: str) -> Optional[StrategyItem]:
        """Resume a specific strategy by ID."""
        sid = (strategy_id or "").strip().lower()
        for s in self._strategies:
            if s.id.lower() == sid or s.name.lower() == sid:
                self.__class__._paused_strategy_ids.discard(s.id)
                self.__class__._status_overrides[s.id.lower()] = StrategyStatus.ACTIVE
                self._save_persisted_status()
                self.invalidate_cache()
                norm_sym = (s.symbol or "").replace("/", "").replace("_", "").upper()
                self.__class__._paused_symbols.discard(norm_sym)
                if s.id in EXPANSION_STRATEGY_IDS and self.__class__._expansion_paused:
                    # Keep other expansion strategies paused while unpausing this specific one
                    self.__class__._expansion_paused = False
                    for exp_id in EXPANSION_STRATEGY_IDS:
                        if exp_id != s.id:
                            self.__class__._paused_strategy_ids.add(exp_id)
                out = s.model_copy(deep=True)
                out.status = StrategyStatus.ACTIVE
                out.readyForExecution = True
                return out
        return None

    def pause_symbol(self, symbol: str) -> List[str]:
        """Pause all strategies trading a specific symbol (e.g. 'GBP/JPY', 'AUD/USD', 'USD/JPY')."""
        norm_sym = (symbol or "").replace("/", "").replace("_", "").upper()
        if not norm_sym:
            return []
        self.__class__._paused_symbols.add(norm_sym)
        affected = [
            s.id for s in self._strategies
            if (s.symbol or "").replace("/", "").replace("_", "").upper() == norm_sym
        ]
        for sid in affected:
            self.__class__._paused_strategy_ids.add(sid)
            self.__class__._status_overrides[sid.lower()] = StrategyStatus.PAUSED
        self._save_persisted_status()
        self.invalidate_cache()
        return affected

    def resume_symbol(self, symbol: str) -> List[str]:
        """Resume all strategies trading a specific symbol."""
        norm_sym = (symbol or "").replace("/", "").replace("_", "").upper()
        if not norm_sym:
            return []
        self.__class__._paused_symbols.discard(norm_sym)
        affected = [
            s.id for s in self._strategies
            if (s.symbol or "").replace("/", "").replace("_", "").upper() == norm_sym
        ]
        for sid in affected:
            self.__class__._paused_strategy_ids.discard(sid)
            self.__class__._status_overrides[sid.lower()] = StrategyStatus.ACTIVE
        self._save_persisted_status()
        self.invalidate_cache()
        return affected

    def pause_expansion_strategies(self) -> List[str]:
        """Pause the 6 multi-pair expansion strategies (strat-013 through strat-018)."""
        self.__class__._expansion_paused = True
        for sid in EXPANSION_STRATEGY_IDS:
            self.__class__._paused_strategy_ids.add(sid)
            self.__class__._status_overrides[sid.lower()] = StrategyStatus.PAUSED
        self._save_persisted_status()
        self.invalidate_cache()
        return sorted(EXPANSION_STRATEGY_IDS)

    def resume_expansion_strategies(self) -> List[str]:
        """Resume the 6 multi-pair expansion strategies (strat-013 through strat-018)."""
        self.__class__._expansion_paused = False
        for sid in EXPANSION_STRATEGY_IDS:
            self.__class__._paused_strategy_ids.discard(sid)
            self.__class__._status_overrides[sid.lower()] = StrategyStatus.ACTIVE
        for sym in ("USDJPY", "GBPJPY", "AUDUSD"):
            self.__class__._paused_symbols.discard(sym)
        self._save_persisted_status()
        self.invalidate_cache()
        return sorted(EXPANSION_STRATEGY_IDS)

    def toggle_strategy_status(self, strategy_id: str) -> Optional[StrategyItem]:
        """Toggle strategy between ACTIVE and INCUBATION."""
        sid = (strategy_id or "").strip().lower()
        strategies = self.get_strategies()
        target = None
        for s in strategies:
            if s.id.lower() == sid or s.name.lower() == sid:
                target = s
                break
        if not target:
            return None

        new_status = StrategyStatus.INCUBATION if target.status == StrategyStatus.ACTIVE else StrategyStatus.ACTIVE
        self.__class__._status_overrides[target.id.lower()] = new_status
        if new_status == StrategyStatus.ACTIVE:
            self.__class__._paused_strategy_ids.discard(target.id)
            norm_sym = (target.symbol or "").replace("/", "").replace("_", "").upper()
            self.__class__._paused_symbols.discard(norm_sym)
        self._save_persisted_status()
        self.invalidate_cache()
        return self.get_enriched_strategy(target.id)

    def set_strategy_status(self, strategy_id: str, new_status: StrategyStatus) -> Optional[StrategyItem]:
        """Explicitly set strategy status to ACTIVE or INCUBATION."""
        sid = (strategy_id or "").strip().lower()
        strategies = self.get_strategies()
        target = None
        for s in strategies:
            if s.id.lower() == sid or s.name.lower() == sid:
                target = s
                break
        if not target:
            return None

        self.__class__._status_overrides[target.id.lower()] = new_status
        if new_status == StrategyStatus.ACTIVE:
            self.__class__._paused_strategy_ids.discard(target.id)
            norm_sym = (target.symbol or "").replace("/", "").replace("_", "").upper()
            self.__class__._paused_symbols.discard(norm_sym)
        self._save_persisted_status()
        self.invalidate_cache()
        return self.get_enriched_strategy(target.id)

    def get_pause_state(self) -> Dict[str, Any]:
        """Return structured telemetry on active vs paused strategies and symbols (zero DB I/O)."""
        active_list: List[str] = []
        paused_list: List[str] = []
        for s in self._strategies:
            if self._is_strategy_paused(s):
                paused_list.append(s.id)
            else:
                active_list.append(s.id)
        return {
            "total_strategies": len(self._strategies),
            "active_count": len(active_list),
            "paused_count": len(paused_list),
            "active_strategy_ids": active_list,
            "paused_strategy_ids": paused_list,
            "paused_symbols": sorted(self.__class__._paused_symbols),
            "expansion_paused": self.__class__._expansion_paused,
        }

    def get_strategies(self) -> List[StrategyItem]:
        """Strategy definitions with performance and validation from stored data."""
        import time as _t
        now_mono = _t.monotonic()
        if self.__class__._cached_strategies is not None and (now_mono - self.__class__._cached_strategies_at) < 60.0:
            return [s.model_copy(deep=True) for s in self.__class__._cached_strategies]

        performance = performance_by_strategy()
        validations = latest_validation_by_strategy()
        last_used = last_used_by_strategy()

        strategies: List[StrategyItem] = []
        for definition in self._strategies:
            strategy = definition.model_copy(deep=True)
            sid_lower = strategy.id.lower()
            if sid_lower in self._status_overrides:
                strategy.status = self._status_overrides[sid_lower]
                strategy.readyForExecution = (strategy.status == StrategyStatus.ACTIVE)
            if strategy.minimumRiskReward and strategy.minimumRiskReward > 1.5:
                strategy.minimumRiskReward = 1.5

            if self._is_strategy_paused(strategy):
                strategy.status = StrategyStatus.PAUSED
                strategy.readyForExecution = False
            strategy.performance = performance.get(
                strategy.id, EMPTY_PERFORMANCE.model_copy()
            )
            validation = validations.get(strategy.id)
            if validation is not None:
                strategy.latestValidation = validation
            strategy.lastUsed = last_used.get(strategy.id, strategy.lastUsed)
            if strategy.id != "strat-006":
                try:
                    from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
                    learned_info = adaptive_tuning_engine.synthesize_artifact_learning(strategy.id)
                    l_note = learned_info.get("learned_upgrade_note")
                    if l_note and l_note not in (strategy.reviewNotes or ""):
                        strategy.reviewNotes = f"{strategy.reviewNotes} [{l_note}]"
                except Exception:
                    pass
            strategy.strategyScore = self._score(strategy)
            strategies.append(strategy)
        self.__class__._cached_strategies = strategies
        self.__class__._cached_strategies_at = _t.monotonic()
        return [s.model_copy(deep=True) for s in strategies]

    def _score(self, strategy: StrategyItem) -> StrategyScore:
        historical = round(strategy.performance.winRate)
        current = strategy.latestValidation.score
        return StrategyScore(
            historicalScore=historical,
            currentMarketScore=current,
            overallScore=round((historical + current) / 2),
            historicalPerformance=historical,
            currentMarketFit=current,
            currentNewsScore=strategy.latestValidation.aiConfidence,
            sessionMatch=current,
            riskRating=strategy.riskLevel,
        )

    def get_strategy_by_id(self, strategy_id: str) -> Optional[StrategyItem]:
        """Definition only; use :meth:`get_strategies` for stored metrics."""
        for s in self._strategies:
            if s.id == strategy_id:
                return s
        return None

    def get_enriched_strategy(self, strategy_id: str) -> Optional[StrategyItem]:
        sid = (strategy_id or "").strip().lower()
        for s in self.get_strategies():
            if s.id.lower() == sid or s.name.lower() == sid:
                return s
        return None

    def _init_strategies(self) -> List[StrategyItem]:
        now = datetime.now(timezone.utc)
        
        # 1. London Breakout
        s1 = StrategyItem(
            id="strat-001",
            name="London Breakout",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Captures large volatility expansions during the London market open.",
            marketCondition="High Volatility Trending",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["High momentum", "Strong trend confirmation", "High historical accuracy"],
            weaknesses=["Poor during ranging markets", "Avoid before major news"],
            entryChecklist=["Trend confirmed", "Breakout candle closed", "Volume increasing", "News clear"],
            exitChecklist=["TP reached", "Structure broken", "Momentum fading"],
            idealVolatility="High",
            avoidDuring=["FOMC", "NFP", "CPI"],
            confirmationIndicators=["RSI", "EMA 50", "Volume"],
            successConditions=["London Session", "Trend Direction Confirmed", "Above EMA 200", "Volume Increasing"],
            minimumConfidence=85,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["High Impact News", "Low Liquidity", "Friday Afternoon", "Holiday Markets"],
            requiredConfirmations=["EMA 200 Trend", "RSI > 50", "Volume Above Average"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile", "High Liquidity"],
            estimatedHoldingTime="20-40 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 10, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-001-v2.3",
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Pre-London Asian Range Compression breakout surge + Opposite corridor structural SL & early +1.0R Breakeven lock.",
            dependencies=["Trend Bias", "Market Session Engine", "News Filter", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 2. Gold Trend Continuation
        s2 = StrategyItem(
            id="strat-002",
            name="Gold Trend Continuation",
            type=StrategyType.TREND_CONTINUATION,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Rides strong impulse waves in structural trends.",
            marketCondition="Bullish/Bearish Trending",
            bestSession="London",
            bestTimeframe="H1",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Rides major moves", "Clear stop loss placement"],
            weaknesses=["Drawdown during consolidation"],
            entryChecklist=["Structural pullbacks complete", "Engulfing candle formed"],
            exitChecklist=["Opposite structure breaks"],
            idealVolatility="Medium",
            avoidDuring=["FOMC", "NFP"],
            confirmationIndicators=["EMA 20", "RSI"],
            successConditions=["Trend Alignment", "Above EMA 50"],
            minimumConfidence=80,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York"],
            avoidConditions=["Ranging Markets", "Extreme Volatility"],
            requiredConfirmations=["RSI > 50", "EMA 20 / 50 aligned"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Trending", "High Liquidity"],
            estimatedHoldingTime="2-6 hours",
            maxConsecutiveLosses=4,
            createdAt=datetime(2026, 2, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 5, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-002-v1.1",
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Intra-bar volume delta absorption on 20 EMA pullback + Opposite structural corridor SL.",
            dependencies=["Trend Bias", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 3. Support & Resistance Bounce
        s3 = StrategyItem(
            id="strat-003",
            name="Support & Resistance Bounce",
            type=StrategyType.SUPPORT_RESISTANCE,
            category=StrategyCategory.SWING,
            symbol="XAU/USD",
            description="Traded off key horizontal levels.",
            marketCondition="Ranging",
            bestSession="Asian",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["High reliability during slow markets"],
            weaknesses=["Fails during breakouts"],
            entryChecklist=["Level rejection candle", "Oversold/Overbought RSI"],
            exitChecklist=["Opposite key level"],
            idealVolatility="Low",
            avoidDuring=["US Open", "CPI"],
            confirmationIndicators=["Stochastic", "RSI"],
            successConditions=["Low Volatility", "Ranging Structure"],
            minimumConfidence=75,
            minimumRiskReward=2.0,
            preferredSessions=["Asian"],
            avoidConditions=["Trend Breakouts", "High Impact News"],
            requiredConfirmations=["Rejection Pinbar", "RSI Divergence"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Ranging", "Low Volatility"],
            estimatedHoldingTime="1-3 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 3, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 5, 20, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-003-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + S/R multi-touch exhaustion decay filter + 40% rejection wick with RVol >= 1.5x.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 4. London Momentum
        s4 = StrategyItem(
            id="strat-004",
            name="London Momentum",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/USD",
            description="Scalps quick runs in GBP/USD pairs.",
            marketCondition="High Volatility Trend",
            bestSession="London",
            bestTimeframe="M5",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Quick returns", "High volume"],
            weaknesses=["High commission costs", "Slippage risks"],
            entryChecklist=["High volume candle", "MACD bullish crossover"],
            exitChecklist=["Opposite signal crossover"],
            idealVolatility="High",
            avoidDuring=["BOE Rate Decision"],
            confirmationIndicators=["MACD", "Volume"],
            successConditions=["High Volume", "Trend Confirmed"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "London-NY Overlap", "New York"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 1, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-004-v2.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + London 08:00 UTC institutional volume surge (RVol >= 2.0x) + Early +1.0R Breakeven lock.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 5. GBP/USD Pullback Entry
        s5 = StrategyItem(
            id="strat-005",
            name="GBP/USD Pullback Entry",
            type=StrategyType.PULLBACK,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/USD",
            description="Buy pullbacks on structural zones.",
            marketCondition="Medium Trend",
            bestSession="London",
            bestTimeframe="M30",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Low risk exposure", "High precision pullback entries"],
            weaknesses=["Requires clean trending market structure"],
            entryChecklist=["Price touches support level", "Stochastic cross"],
            exitChecklist=["TP hit"],
            idealVolatility="Medium",
            avoidDuring=["BOE news"],
            confirmationIndicators=["Stochastic", "EMA 20"],
            successConditions=["Bullish Structure"],
            minimumConfidence=78,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York"],
            avoidConditions=["High News Impact"],
            requiredConfirmations=["Support bounce", "Bullish engulfing"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Trending"],
            estimatedHoldingTime="2-4 hours",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 4, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 20, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-005-v1.2",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Golden 50-61.8% Fibonacci retracement confluence with M15/H1 trend alignment.",
            dependencies=["Trend Bias"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 6. European Breakout
        s6 = StrategyItem(
            id="strat-006",
            name="European Breakout",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="EUR/USD",
            description="Breakouts of early Frankfurt ranges.",
            marketCondition="Trending",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Definite zones", "Objective entry rules"],
            weaknesses=["False breakouts"],
            entryChecklist=["Frankfurt high/low breakout", "Volume confirmation"],
            exitChecklist=["TP or Trailing SL hit"],
            idealVolatility="High",
            avoidDuring=["ECB news"],
            confirmationIndicators=["Volume"],
            successConditions=["Volatile Sessions"],
            minimumConfidence=80,
            minimumRiskReward=2.0,
            preferredSessions=["London", "Frankfurt", "London-NY Overlap"],
            avoidConditions=["Ranging Markets"],
            requiredConfirmations=["Breakout candle close", "High volume"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile"],
            estimatedHoldingTime="20-60 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 5, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.1",
            parentStrategyId="strat-006-v3.0",
            createdBy="Imported",
            readyForExecution=False,
            reviewNotes="Upgraded logic to ignore initial wick breakouts.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 7. EUR/USD Trend Continuation
        s7 = StrategyItem(
            id="strat-007",
            name="EUR/USD Trend Continuation",
            type=StrategyType.TREND_CONTINUATION,
            category=StrategyCategory.POSITION,
            symbol="EUR/USD",
            description="Long-term trend following.",
            marketCondition="Strong Trend",
            bestSession="London",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.GOOD,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Highly profitable", "Low screen time required"],
            weaknesses=["Requires patient holding"],
            entryChecklist=["Higher Highs / Lower Lows on Daily", "Pullback to 20 EMA"],
            exitChecklist=["EMA cross in opposite direction"],
            idealVolatility="Low",
            avoidDuring=["NFP"],
            confirmationIndicators=["EMA 20"],
            successConditions=["Daily Trends"],
            minimumConfidence=80,
            minimumRiskReward=1.3,
            preferredSessions=["London", "New York"],
            avoidConditions=["Ranging Markets"],
            requiredConfirmations=["20 EMA support", "Daily trend confirm"],
            grade="B",
            lastUsed=now,
            marketCompatibility=["Trending"],
            estimatedHoldingTime="1-3 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 5, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 6, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-007-v1.5",
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Macro US Dollar Index (DXY) inverse market structure break alignment.",
            dependencies=["Trend Bias"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 8. Session Momentum & Volume Expansion Breakout
        s8 = StrategyItem(
            id="strat-008",
            name="Session Momentum & Volume Expansion Breakout",
            type=StrategyType.SESSION_BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Institutional session breakout execution. Identifies directional corridor breaks of Asian and London Open ranges confirmed by Relative Volume surges (RVol >= 1.8x) and candle spread expansion.",
            marketCondition="Session Open Expansion or High Volume Breakout",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Exploits institutional session liquidity influx", "Tight invalidation against session boundary", "High risk-to-reward ratio"],
            weaknesses=["Avoid during low volume consolidation", "Requires clean session range formation"],
            entryChecklist=["Session range boundary breached", "Relative Volume (RVol) >= 1.8x confirmed", "Candle body >= 60% of total range", "News clean"],
            exitChecklist=["1.5x - 2.0x session range expansion reached", "Opposing volume reversal detected"],
            idealVolatility="High",
            avoidDuring=["FOMC", "NFP", "CPI"],
            confirmationIndicators=["Session Corridors", "Relative Volume Surge (RVol >= 1.8x)", "Candle Spread Expansion"],
            successConditions=["Session Breakout Close", "Volume Spike Confirmation", "Multi-Timeframe Trend Confluence"],
            minimumConfidence=85,
            minimumRiskReward=2.5,
            preferredSessions=["London", "New York"],
            avoidConditions=["High Impact News Blackout", "Low Volume Range"],
            requiredConfirmations=["Session Boundary Breakout", "RVol >= 1.8x Spike", "Clean Candle Spread"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["High Volatility", "Trending", "Institutional Flow"],
            estimatedHoldingTime="30-90 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 7, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-008-v2.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Single-sided session corridor expansion with 2-bar consecutive volume surge.",
            dependencies=["Market Session Engine", "Volume Expansion Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 9. Asian Mean Reversion Range
        s9 = StrategyItem(
            id="strat-009",
            name="Asian Mean Reversion Range",
            type=StrategyType.MEAN_REVERSION,
            category=StrategyCategory.INTRADAY,
            symbol="USD/JPY",
            description="Exploits quiet overnight Asian ranges (Tokyo/Sydney). Enters when price touches outer Bollinger Bands with RSI extreme exhaustion (< 30 or > 70) for rapid snap-backs.",
            marketCondition="Ranging Low Volatility",
            bestSession="Asian",
            bestTimeframe="M15",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Consistent overnight win-rate", "Low drawdown", "Safe during quiet markets"],
            weaknesses=["Must exit before London pre-market momentum"],
            entryChecklist=["Price at Bollinger Band outer edge", "RSI overbought (>70) or oversold (<30)", "Key S/R boundary hold"],
            exitChecklist=["Mean / 20 SMA reached", "Opposite band touched"],
            idealVolatility="Low",
            avoidDuring=["BOJ Rate Decision", "Asian High Impact News"],
            confirmationIndicators=["RSI 14", "Bollinger Bands (20, 2)", "Horizontal Support/Resistance"],
            successConditions=["Asian Session Active", "RSI Extreme Reached", "Low Spread Environment"],
            minimumConfidence=80,
            minimumRiskReward=2.0,
            preferredSessions=["Asian", "Sydney", "Tokyo"],
            avoidConditions=["London Open Impending", "High Spread Spikes"],
            requiredConfirmations=["RSI Divergence or Extreme", "Reversal Candlestick at Band"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Ranging", "Low Volatility", "Consolidation"],
            estimatedHoldingTime="1-3 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 8, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-009-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Asian range extreme fade on sub-1.0x RVol with mean-reversion boundary targets.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 10. Macro Trend Swing Wave
        s10 = StrategyItem(
            id="strat-010",
            name="Macro Trend Swing Wave",
            type=StrategyType.SWING_STRUCTURE,
            category=StrategyCategory.SWING,
            symbol="XAU/USD",
            description="Multi-day institutional swing trading. Rides major directional waves (150-350 pips) across Gold and major currencies based on H4 Higher-High/Higher-Low market structure and EMA 50 pullbacks.",
            marketCondition="Strong Macro Trend",
            bestSession="London",
            bestTimeframe="H4",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Captures massive profit runs", "Low maintenance / zero screen stress", "Immune to short-term intraday noise"],
            weaknesses=["Wider stop loss required", "Low trade frequency (1-3 setups per week)"],
            entryChecklist=["H4 structural break of structure (BOS)", "Pullback to 50 EMA dynamic zone", "Daily bias aligned"],
            exitChecklist=["Opposite H4 structure break", "Trailing stop-loss triggered"],
            idealVolatility="Medium",
            avoidDuring=["Emergency Central Bank Announcements"],
            confirmationIndicators=["EMA 50 / 200", "Market Structure BOS", "Higher Timeframe ATR"],
            successConditions=["Daily Bullish/Bearish Bias", "H4 Pullback Complete", "Risk/Reward >= 2.5"],
            minimumConfidence=88,
            minimumRiskReward=2.8,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Ranging Consolidation", "Unresolved Major Geopolitics"],
            requiredConfirmations=["H4 Market Structure Trend Alignment", "Daily EMA Slope Direction"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Macro Expansion", "Institutional Flows"],
            estimatedHoldingTime="2-5 days",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 8, 20, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 2, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-010-v1.0",
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Multi-day swing wave confirmation aligned with CFTC COT hedge-fund positioning.",
            dependencies=["Trend Bias", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 11. Institutional Price Action & Candlestick Confluence
        s11 = StrategyItem(
            id="strat-011",
            name="Institutional Candlestick & Price Action Confluence",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Executes high-conviction trades when institutional candlestick triggers (Engulfing, Morning/Evening Star, Three White Soldiers, Hammers, Three Line Strike, Double Tops/Bottoms) align precisely with Key Support/Resistance and Supply/Demand zones.",
            marketCondition="Key S/R Reversals & Trend Continuations",
            bestSession="London / New York",
            bestTimeframe="H1",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Pinpoint low-drawdown entries", "Clear structural invalidation stop loss", "High win-rate across all asset classes"],
            weaknesses=["Requires patience for pattern close at key levels"],
            entryChecklist=["Candlestick pattern confirmed at close", "Occurs at Institutional Support/Demand or Resistance/Supply", "Risk/Reward >= 2.0"],
            exitChecklist=["Opposite structure target reached", "Trailing stop-loss after 1.5R"],
            idealVolatility="Medium to High",
            avoidDuring=["Low Liquidity Holidays"],
            confirmationIndicators=["Candlestick Pattern Engine", "Support/Demand Zones", "ATR Sizing"],
            successConditions=["Pattern Confirmation", "Key Zone Confluence", "SMC Order Flow Alignment"],
            minimumConfidence=85,
            minimumRiskReward=2.0,
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Choppy Middle-of-Range Noise"],
            requiredConfirmations=["Confirmed Candle Close", "Structure Level Tap"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Reversals", "Breakouts"],
            estimatedHoldingTime="2-8 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 3, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 3, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-011-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Inversion FVG liquidity trap displacement back into value zone.",
            dependencies=["Candlestick Pattern Engine", "Structure Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 12. Institutional Liquidity Sweep & Fair Value Gap (SMC Sniper)
        s12 = StrategyItem(
            id="strat-012",
            name="Institutional Liquidity Sweep & FVG",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Hunts institutional stop-loss sweeps above Previous Day/Session Highs (PDH/ASH) or below Lows (PDL/ASL) paired with Fair Value Gap (FVG) / Inversion FVG (IFVG). Enters on rejection with tight wick-anchored stops for disciplined 1:1.2 to 1:1.5 R:R.",
            marketCondition="Liquidity Sweeps & Displacement Reversals",
            bestSession="London / New York",
            bestTimeframe="H1",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Exploits retail stop hunts before institutional reversal",
                "Ultra-tight stop loss anchored beyond sweep wick (10-18 pips)",
                "Disciplined 1:1.5 to 1:2.0 risk-to-reward profile"
            ],
            weaknesses=["Selective sniper frequency (waits for key pool sweep)"],
            entryChecklist=[
                "Wick sweep of PDH/PDL or Asian High/Low with body close back inside range",
                "3-candle Fair Value Gap (FVG) or Inversion FVG (IFVG) confirmed",
                "Cross-Asset DXY Macro Gate aligned",
                "Risk/Reward between 1.5 and 2.0"
            ],
            exitChecklist=[
                "Disciplined target reached (1:1.2 to 1:1.5 R:R)",
                "Breakeven + 2 pips locked at +1.0R",
                "Structural Higher-Low / Lower-High trailing stop"
            ],
            idealVolatility="Medium to High",
            avoidDuring=["Unscheduled Flash Crashes", "DXY Macro Bull/Bear Trap"],
            confirmationIndicators=["Smart Money Sweep Engine", "Inversion FVG (IFVG)", "Synthetic DXY Macro Gate"],
            successConditions=["Liquidity Pool Pierced & Rejected", "FVG / IFVG Created", "Macro DXY Aligned"],
            minimumConfidence=85,
            minimumRiskReward=1.35,
            preferredSessions=["London", "New York", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Macro DXY Contradiction", "Wide Rollover Spreads"],
            requiredConfirmations=["Liquidity Sweep Rejection Close", "Fair Value Gap Displacement"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Reversals", "Breakouts", "Trending", "Volatile"],
            estimatedHoldingTime="1-6 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 10, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 10, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-012-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + OANDA OrderBook retail stop cluster sweep & FVG displacement.",
            dependencies=["Smart Money Engine", "Macro Cross-Asset Gate", "Structure Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 13. Tokyo Fix & Asian Range Liquidity Sweep (USD/JPY — Paired with strat-009)
        s13 = StrategyItem(
            id="strat-013",
            name="Tokyo Fix & Asian Range Liquidity Sweep",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="USD/JPY",
            description="Pairs with Asian Mean Reversion Range (strat-009) on USD/JPY. Captures the institutional stop hunt when Tokyo Fix or early London liquidity pierces the overnight Asian High/Low by 5-15 pips and snaps back with a 3-candle Fair Value Gap (FVG) displacement.",
            marketCondition="Asian Boundary Liquidity Sweeps & Reversals",
            bestSession="Asian / London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Directly turns strat-009 Asian range boundary stop-hunts into high-R:R entries",
                "Tight stop loss anchored 2 pips beyond the sweep wick",
                "High 1:2.8+ risk-to-reward profile"
            ],
            weaknesses=["Requires established Asian session high/low pool"],
            entryChecklist=[
                "Wick sweep of Asian High/Low or Previous Day High/Low on USD/JPY",
                "Immediate candle body rejection close back inside range",
                "3-candle FVG displacement or reversal candlestick confirmed",
                "DXY / US Yield Macro Gate aligned"
            ],
            exitChecklist=[
                "Asian range opposite boundary or 1:2.8+ R:R reached",
                "Breakeven + 1.5 pips locked at +1.5R"
            ],
            idealVolatility="Low to Medium",
            avoidDuring=["BOJ Unscheduled Intervention", "US NFP / CPI Release Minute"],
            confirmationIndicators=["Smart Money Sweep Engine", "3-Candle FVG Imbalance", "RSI 14"],
            successConditions=["Asian Boundary Swept & Rejected", "FVG Imbalance Confirmed", "Spread <= 1.5 pips"],
            minimumConfidence=82,
            minimumRiskReward=1.3,
            preferredSessions=["Asian", "Tokyo", "London", "London-NY Overlap"],
            avoidConditions=["BOJ Emergency Press Conference", "Wide Rollover Spreads"],
            requiredConfirmations=["Liquidity Sweep Rejection Close", "FVG or Reversal Candle"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Reversals", "Ranging", "Liquidity Sweeps"],
            estimatedHoldingTime="1-4 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-013-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Commercial Tokyo Fixing liquidity sweep fade with tight boundary stops.",
            dependencies=["Smart Money Engine", "Market Session Engine", "Macro Cross-Asset Gate"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 14. US Yield & NY Momentum Breakout (USD/JPY — Paired with strat-009)
        s14 = StrategyItem(
            id="strat-014",
            name="US Yield & NY Momentum Breakout",
            type=StrategyType.SESSION_BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="USD/JPY",
            description="Complements Asian Mean Reversion Range (strat-009) by switching USD/JPY from range-fading to directional momentum expansion during London and New York sessions when US 10Y Yields and Synthetic DXY break out with Relative Volume >= 1.8x.",
            marketCondition="London / NY Yield-Driven Trend Expansion",
            bestSession="New York",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Captures explosive 60-120 pip USD/JPY waves during US Treasury Yield moves",
                "Eliminates Asian-only blindspot on USD/JPY during London & NY hours",
                "Confirmed by Synthetic DXY + RISING/FALLING_YIELDS macro gate"
            ],
            weaknesses=["Avoid during dead Asian consolidation (handled by strat-009)"],
            entryChecklist=[
                "Asian or London session corridor broken cleanly on USD/JPY",
                "Relative Volume surge (RVol >= 1.8x) confirmed",
                "Synthetic DXY & US Yield Proxy aligned with breakout direction"
            ],
            exitChecklist=[
                "TP1 partial scale-out at +1.5R, TP2 runner at +2.5R+",
                "Structural swing trailing stop engaged at +2.0R"
            ],
            idealVolatility="Medium to High",
            avoidDuring=["Low Volume Asian Range", "Pre-FOMC Blackout"],
            confirmationIndicators=["Session Breakout Corridors", "RVol >= 1.8x", "Synthetic DXY & Yield Proxy"],
            successConditions=["Corridor Breakout Close", "Volume Expansion", "Macro Yield Alignment"],
            minimumConfidence=84,
            minimumRiskReward=2.5,
            preferredSessions=["London", "New York", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Asian Low-Volume Chop", "Macro DXY Contradiction"],
            requiredConfirmations=["Session Boundary Breakout", "RVol >= 1.8x Surge", "DXY/Yield Alignment"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "High Volatility", "Macro Expansion"],
            estimatedHoldingTime="45-180 minutes",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-014-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + US 10Y Yield inverse momentum divergence at 13:30 UTC NY open.",
            dependencies=["Session Breakout Engine", "Macro Cross-Asset Gate", "Volume Expansion Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 15. Dragon London Open Volatility Breakout (GBP/JPY)
        s15 = StrategyItem(
            id="strat-015",
            name="Dragon London Open Volatility Breakout",
            type=StrategyType.SESSION_BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/JPY",
            description="Captures high-beta 'Dragon' (GBP/JPY) volatility expansions at the London Open and London-NY Overlap. Waits for the Tokyo consolidation box to break with RVol >= 1.8x and enters on the structural retest.",
            marketCondition="High-Beta Session Volatility Expansion",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Exploits the highest average daily range (120-180 pips) among FX crosses",
                "Filters out London Open Judas fakeouts via sweep-retest validation",
                "Asymmetric 1:2.8+ risk-to-reward profile"
            ],
            weaknesses=["Requires strict 3.2-pip spread shield protection"],
            entryChecklist=[
                "Tokyo session range high/low broken with candle body >= 60% of range",
                "Relative Volume (RVol) >= 1.8x surge confirmed",
                "GBP/USD and USD/JPY cross-pair flows aligned (no divergence)"
            ],
            exitChecklist=[
                "1.5R TP1 partial bank + breakeven lock",
                "2.8R+ TP2 runner with structural swing trail"
            ],
            idealVolatility="High",
            avoidDuring=["BOE / BOJ Rate Decisions", "Rollover Spread Widening"],
            confirmationIndicators=["Session Breakout Corridors", "RVol >= 1.8x", "Yen-Cross Alignment Filter"],
            successConditions=["London/Overlap Active", "Corridor Breakout + Retest", "Spread <= 3.2 pips"],
            minimumConfidence=85,
            minimumRiskReward=2.8,
            preferredSessions=["London", "New York", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > 3.2 Pips", "GBP/USD vs USD/JPY Opposing Whipsaw"],
            requiredConfirmations=["Tokyo Corridor Breakout", "RVol >= 1.8x Confirmation", "HTF EMA Bias Alignment"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "Trending", "Session Breakouts"],
            estimatedHoldingTime="30-120 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-015-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Dual Yen-cross synchronization gate preventing synthetic whipsaw.",
            dependencies=["Session Breakout Engine", "Smart Money Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 16. Dragon Institutional FVG & Trend Pullback (GBP/JPY)
        s16 = StrategyItem(
            id="strat-016",
            name="Dragon Institutional FVG & Trend Pullback",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/JPY",
            description="Trades GBP/JPY institutional liquidity sweeps and 3-candle Fair Value Gap (FVG) pullbacks aligned with H1 EMA 20/50 trend structure. Avoids chasing extended breakouts by entering on discount/premium imbalance fills.",
            marketCondition="Trending Impulses & SMC Imbalance Pullbacks",
            bestSession="London / New York",
            bestTimeframe="H1",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Eliminates FOMO chasing on GBP/JPY by demanding FVG/sweep pullback",
                "High-precision invalidation anchored below structural swing low/high",
                "Superior 1:3.0+ risk-to-reward ratio"
            ],
            weaknesses=["Selective entry frequency; waits for clean imbalance retest"],
            entryChecklist=[
                "Liquidity sweep of session/previous-day high/low OR 3-candle FVG created",
                "H1 EMA 20 / EMA 50 trend structure aligned",
                "Confirmation candle close at key zone"
            ],
            exitChecklist=[
                "Opposite structural liquidity pool reached (1:3.0 R:R)",
                "Automated breakeven at +1.5R and structural trail at +2.0R"
            ],
            idealVolatility="Medium to High",
            avoidDuring=["Low Liquidity Rollover", "High Impact GBP/JPY News"],
            confirmationIndicators=["Smart Money Sweep & FVG Engine", "Candlestick Pattern Engine", "EMA 20 / 50"],
            successConditions=["SMC Sweep or FVG Retest", "HTF Structure Aligned", "Risk/Reward >= 3.0"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "New York", "Asian", "London-NY Overlap"],
            avoidConditions=["Middle-of-Range Chop", "Wide Spreads"],
            requiredConfirmations=["Liquidity Sweep or FVG Fill", "Candlestick Confirmation Close"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Reversals", "Institutional Flow"],
            estimatedHoldingTime="1-6 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-016-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Shadow quarantine defense + Strict 2.5 pip spread cap & FVG retest.",
            dependencies=["Smart Money Engine", "Candlestick Pattern Engine", "Structure Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 17. Pacific Liquidity Sweep & Gold-Macro Confluence (AUD/USD)
        s17 = StrategyItem(
            id="strat-017",
            name="Pacific Liquidity Sweep & Gold-Macro Confluence",
            type=StrategyType.PRICE_ACTION,
            category=StrategyCategory.INTRADAY,
            symbol="AUD/USD",
            description="Exploits Sydney/Tokyo and London Open liquidity sweeps on AUD/USD confirmed by 3-candle Fair Value Gaps (FVG) and positive commodity correlation with Gold (XAU/USD) and inverse Synthetic DXY flows.",
            marketCondition="Session Liquidity Sweeps & Commodity-FX Alignment",
            bestSession="Asian / London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Active during Sydney/Tokyo Asian hours as well as London/NY transitions",
                "Cross-asset Gold (XAU/USD) + DXY confirmation filters out false AUD breakouts",
                "Tight 12-18 pip structural stops with 1:2.8+ R:R"
            ],
            weaknesses=["Avoid during RBA rate statements"],
            entryChecklist=[
                "Wick sweep of Asian/Previous-Day High or Low on AUD/USD",
                "3-candle FVG displacement or institutional reversal candle close",
                "XAU/USD (Gold) and Synthetic DXY macro gate aligned"
            ],
            exitChecklist=[
                "1.35R-1.5R target pool reached",
                "Breakeven stop locked at +1.0R"
            ],
            idealVolatility="Medium",
            avoidDuring=["RBA Rate Decision", "US CPI / NFP"],
            confirmationIndicators=["Smart Money Sweep Engine", "Synthetic DXY & Gold Confluence", "3-Candle FVG", "OrderFlowEngine v3.0"],
            successConditions=["Liquidity Sweep Confirmed", "Macro DXY & Gold Aligned", "RVol >= 1.8x & Body >= 45%", "Spread <= 1.2 pips"],
            minimumConfidence=85,
            minimumRiskReward=1.35,
            preferredSessions=["Asian", "Sydney", "Tokyo", "London", "New York", "London-NY Overlap"],
            avoidConditions=["Macro DXY Bull/Bear Trap", "Gold Divergence"],
            requiredConfirmations=["Sweep Rejection Close", "FVG or Candlestick Confirmation", "Macro Gate Pass"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Reversals", "Trending", "Commodity-FX Flow"],
            estimatedHoldingTime="1-5 hours",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-017-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Medium-risk AUD/USD configuration with European Breakout v3.1 Anti-Fakeout DNA (Body >= 45%, RVol >= 1.8x, no wick probes) + Real-time Gold (XAU/USD) macro lockstep & OrderFlowEngine v3.0 trap defense.",
            dependencies=["Smart Money Engine", "Macro Cross-Asset Gate", "Candlestick Pattern Engine", "OrderFlowEngine v3.0"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 18. AUD/USD Structural Trend & EMA Pullback (AUD/USD)
        s18 = StrategyItem(
            id="strat-018",
            name="AUD/USD Structural Trend & EMA Pullback",
            type=StrategyType.TREND_CONTINUATION,
            category=StrategyCategory.INTRADAY,
            symbol="AUD/USD",
            description="Rides clean, low-whipsaw intraday and multi-session trends on AUD/USD. Enters on structural pullbacks to the H1 20/50 EMA dynamic zone confirmed by institutional candlestick patterns and DXY macro alignment.",
            marketCondition="Steady Directional Trend & Pullback Continuation",
            bestSession="London / New York",
            bestTimeframe="H1",
            riskLevel=RiskLevel.LOW,
            status=StrategyStatus.INCUBATION,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "AUD/USD respects EMA 20/50 trend structure with minimal retail stop-hunting noise",
                "Low drawdown and high consistency across London and NY sessions",
                "1:2.5+ asymmetric risk-to-reward with structural trailing stops"
            ],
            weaknesses=["Lower frequency during tight horizontal consolidation"],
            entryChecklist=[
                "H1 trend aligned with EMA 20 & EMA 50 slope",
                "Pullback to dynamic EMA support/resistance completed",
                "Bullish/Bearish Engulfing, Pinbar, or Morning/Evening Star confirmation",
                "DXY Macro Gate aligned"
            ],
            exitChecklist=[
                "1:2.5+ R:R structural target reached",
                "Swing trailing stop ratcheted at +2.0R"
            ],
            idealVolatility="Low to Medium",
            avoidDuring=["RBA Rate Statement", "US FOMC"],
            confirmationIndicators=["EMA 20 / 50", "Candlestick Pattern Engine", "Synthetic DXY Macro Gate"],
            successConditions=["Trend Alignment", "Candlestick Pullback Trigger", "Macro DXY Aligned"],
            minimumConfidence=82,
            minimumRiskReward=2.5,
            preferredSessions=["Asian", "London", "New York", "London-NY Overlap"],
            avoidConditions=["Choppy Range Consolidation", "Macro DXY Contradiction"],
            requiredConfirmations=["EMA 20/50 Trend Alignment", "Candlestick Pattern Close", "DXY Gate Pass"],
            grade="A",
            lastUsed=now,
            marketCompatibility=["Trending", "Low Volatility", "High Liquidity"],
            estimatedHoldingTime="2-6 hours",
            maxConsecutiveLosses=3,
            createdAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 9, 15, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-018-v1.0",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Commodity flow trend validation + Dynamic EMA 50 pullback support.",
            dependencies=["Trend Bias", "Candlestick Pattern Engine", "Macro Cross-Asset Gate"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 19. London Momentum (XAU/USD)
        s19 = StrategyItem(
            id="strat-019",
            name="London Momentum (XAU/USD)",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="XAU/USD",
            description="Scalps quick high-momentum runs in Gold (XAU/USD) during active session flow.",
            marketCondition="High Volatility Trend",
            bestSession="London",
            bestTimeframe="M5",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Quick returns", "High volume", "Strong Gold impulse capture"],
            weaknesses=["High commission costs", "Slippage risks"],
            entryChecklist=["High volume candle", "MACD bullish/bearish crossover"],
            exitChecklist=["Opposite signal crossover"],
            idealVolatility="High",
            avoidDuring=["FOMC", "NFP", "CPI"],
            confirmationIndicators=["MACD", "Volume"],
            successConditions=["High Volume", "Trend Confirmed"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "London-NY Overlap", "New York"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-019-v2.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + London 08:00 UTC Gold corridor body break with positive CVD absorption.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 20. London Momentum (EUR/USD)
        s20 = StrategyItem(
            id="strat-020",
            name="London Momentum (EUR/USD)",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="EUR/USD",
            description="Scalps quick high-momentum runs in EUR/USD pairs during active session flow.",
            marketCondition="High Volatility Trend",
            bestSession="London",
            bestTimeframe="M5",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=["Quick returns", "High volume", "Tight Euro spread execution"],
            weaknesses=["High commission costs", "Slippage risks"],
            entryChecklist=["High volume candle", "MACD bullish/bearish crossover"],
            exitChecklist=["Opposite signal crossover"],
            idealVolatility="High",
            avoidDuring=["ECB Rate Decision", "NFP"],
            confirmationIndicators=["MACD", "Volume"],
            successConditions=["High Volume", "Trend Confirmed"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "London-NY Overlap", "New York"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-020-v2.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Frankfurt 07:00 to London 08:00 UTC continuous momentum expansion.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 21. London Open Liquidity Sweep + Momentum Displacement (GBP/JPY)
        s21 = StrategyItem(
            id="strat-021",
            name="London Open Liquidity Sweep + Momentum Displacement",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/JPY",
            description="Marks the Asian Session High and Low (00:00-06:45 UTC), waits for London Open (07:00-10:00 UTC) or London/NY Overlap (12:00-15:00 UTC) to sweep one side of the Asian range by 10-25 pips (triggering retail stops), and enters on the displacement candle with Break of Structure (BOS) and Fair Value Gap (FVG) pullback in the direction of the H1 trend.",
            marketCondition="Asian Range Liquidity Sweep & London Momentum Displacement",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Exploits GBP/JPY's notorious end-of-Tokyo/London-open fakeouts",
                "High win rate: post-sweep London displacement routinely carries 40-80+ pips in a single impulse leg",
                "Combines M15 Asian liquidity sweep + BOS/FVG displacement with H1 trend alignment"
            ],
            weaknesses=["Requires high-volatility session displacement", "Avoid during BOE/BOJ rate announcements"],
            entryChecklist=[
                "Mark Asian Session High and Low (00:00 - 06:45 UTC)",
                "London Open / Overlap sweeps one side of Asian range by 10-25 pips",
                "Displacement candle back inside with Break of Structure (BOS) and Fair Value Gap (FVG)",
                "Enter on FVG / Order Block pullback aligned with H1 trend"
            ],
            exitChecklist=[
                "40-80+ pip London momentum impulse leg target reached",
                "Automated breakeven lock at +1.0R"
            ],
            idealVolatility="High",
            avoidDuring=["BOE / BOJ Rate Decisions", "Rollover Spread Widening"],
            confirmationIndicators=["Asian Range Corridor", "Smart Money Sweep & FVG Engine", "BOS Displacement", "H1 Trend Alignment"],
            successConditions=["Asian High/Low Swept (10-25 pips)", "BOS + FVG Displacement", "H1 Trend Aligned"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "New York", "London-NY Overlap", "NY Overlap", "Asian"],
            avoidConditions=["Low Volume Chop", "Spread > 3.5 Pips"],
            requiredConfirmations=["Asian Liquidity Sweep", "BOS + FVG Displacement Candle", "H1 Trend Direction"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "Trending", "Institutional Flow", "High Liquidity"],
            estimatedHoldingTime="15-90 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-021-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Asian range false break snap-back with 2.0x volume surge.",
            dependencies=["Smart Money Engine", "Session Breakout Engine", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 22. NY Open Yield-Driven Liquidity Sweep + Momentum Displacement (USD/JPY)
        s22 = StrategyItem(
            id="strat-022",
            name="NY Open Yield-Driven Liquidity Sweep + Momentum Displacement",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="USD/JPY",
            description="Marks the Tokyo or Pre-NY Session High and Low, waits for London/NY Overlap (12:00-16:00 UTC) or Tokyo Open (00:00-03:00 UTC) to either sweep one side of the session range by 10-20 pips and print a displacement candle back inside with BOS + 3-Candle FVG, or break & retest the Tokyo corridor with RVol >= 1.8x in the direction of the H1 EMA 20/50 trend and Synthetic DXY / US Yield bias. Targets a 1.3R-1.5R (25-45 pip) impulse leg with an immediate +1.0R breakeven stop lock.",
            marketCondition="US Yield-Driven Session Liquidity Sweep & Momentum Displacement",
            bestSession="London-NY Overlap",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "USD/JPY moves in clean one-way algorithmic waves when driven by US Treasury yields (DXY + Yen-cross flow)",
                "Combines 10-20 pip Pre-NY/Tokyo liquidity sweep + BOS/FVG displacement with RVol >= 1.8x corridor break & retest",
                "Targets high-probability 1.3R-1.5R (25-45 pip) impulse legs with immediate +1.0R breakeven lock"
            ],
            weaknesses=["Avoid during BOJ unscheduled intervention or FOMC/NFP release minute"],
            entryChecklist=[
                "Mark Tokyo or Pre-NY Session High and Low",
                "Sweep session range by 10-20 pips + BOS & 3-Candle FVG displacement OR Tokyo corridor Break & Retest with RVol >= 1.8x",
                "H1 EMA 20/50 trend and Synthetic DXY / US Yield bias aligned",
                "Target 1.3R-1.5R (25-45 pips) with +1.0R breakeven stop lock"
            ],
            exitChecklist=[
                "1.3R-1.5R (25-45 pip) impulse leg target reached",
                "Immediate +1.0R breakeven stop lock activated"
            ],
            idealVolatility="High",
            avoidDuring=["FOMC / NFP / US CPI Release Minute", "BOJ Rate Decision"],
            confirmationIndicators=["Smart Money Sweep & 3-Candle FVG Engine", "Tokyo Corridor + RVol >= 1.8x", "Synthetic DXY & US Yield Proxy", "H1 EMA 20/50"],
            successConditions=["Pre-NY/Tokyo Sweep (10-20 pips) + BOS/FVG OR RVol >= 1.8x Break-Retest", "DXY & US Yield Aligned", "H1 Trend Aligned"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London-NY Overlap", "NY Overlap", "New York", "London", "Asian", "Tokyo"],
            avoidConditions=["DXY / Yield Divergence", "Spread > 2.0 Pips"],
            requiredConfirmations=["Session Sweep + BOS/FVG or RVol >= 1.8x Break-Retest", "DXY & Yield Alignment", "H1 EMA Trend"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile", "Yield-Driven Flow", "High Liquidity"],
            estimatedHoldingTime="15-90 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-022-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + US-Japan sovereign yield differential momentum expansion.",
            dependencies=["Smart Money Engine", "Session Breakout Engine", "Macro Cross-Asset Gate"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 23. Liquidity Sweep + Gold & DXY Macro Displacement (AUD/USD)
        s23 = StrategyItem(
            id="strat-023",
            name="Liquidity Sweep + Gold & DXY Macro Displacement",
            type=StrategyType.MOMENTUM,
            category=StrategyCategory.INTRADAY,
            symbol="AUD/USD",
            description="Marks the Asian or Previous-Day High and Low on AUD/USD, waits for price to sweep the liquidity pool by 8-15 pips and immediately close back inside with a BOS + 3-Candle FVG displacement candle, and filters entries with the Gold (XAU/USD) + Synthetic DXY Macro Confluence gate (Gold pushing in the same direction as AUD/USD and DXY moving opposite). Targets a fast 1.3R-1.5R (18-30 pip) momentum impulse leg with an automatic +1.0R breakeven lock.",
            marketCondition="Liquidity Sweep + Gold (XAU/USD) & DXY Macro Displacement",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Secret Weapon Filter: Gold (XAU/USD) + Synthetic DXY macro confluence eliminates false AUD/USD breakouts",
                "High-precision 8-15 pip Asian/Previous-Day liquidity sweep + BOS & 3-Candle FVG displacement",
                "Fast 1.3R-1.5R (18-30 pip) momentum impulse leg with automatic +1.0R breakeven lock"
            ],
            weaknesses=["Avoid during RBA rate announcements or Gold/DXY divergence"],
            entryChecklist=[
                "Mark Asian or Previous-Day High and Low on AUD/USD",
                "Liquidity pool swept by 8-15 pips with immediate BOS + 3-Candle FVG displacement close back inside",
                "Gold (XAU/USD) aligned with AUD/USD direction and Synthetic DXY moving opposite",
                "Target 1.3R-1.5R (18-30 pip) impulse leg with +1.0R breakeven lock"
            ],
            exitChecklist=[
                "1.3R-1.5R (18-30 pip) momentum impulse leg target reached",
                "Automatic +1.0R breakeven lock activated"
            ],
            idealVolatility="Medium to High",
            avoidDuring=["RBA Rate Decision", "US CPI / NFP"],
            confirmationIndicators=["Smart Money Sweep & 3-Candle FVG Engine", "Gold (XAU/USD) Confluence", "Synthetic DXY Macro Gate", "BOS Displacement"],
            successConditions=["8-15 Pip Liquidity Sweep + BOS/FVG", "Gold (XAU/USD) & DXY Aligned", "Spread <= 1.5 Pips"],
            minimumConfidence=85,
            minimumRiskReward=1.3,
            preferredSessions=["London", "London-NY Overlap", "NY Overlap", "New York", "Asian", "Sydney", "Tokyo"],
            avoidConditions=["Gold / DXY Divergence", "Macro Bull/Bear Trap"],
            requiredConfirmations=["Liquidity Sweep + 3-Candle FVG Displacement", "Gold (XAU/USD) Alignment", "DXY Inverse Confirmation"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Trending", "Volatile", "Commodity-FX Flow", "Reversals"],
            estimatedHoldingTime="15-90 minutes",
            maxConsecutiveLosses=2,
            createdAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="3.2",
            parentStrategyId="strat-023-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Upgraded to v3.2: Transplanted European Breakout v3.1 Anti-Fakeout DNA (candle close required, no wick probes) + Triple macro anchor (Pacific sweep + Gold surge + DXY inverse break).",
            dependencies=["Smart Money Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 24. XAU/USD London-NY Velocity Scalp (Learns from strat-006 EUR/USD 0-loss DNA + OrderFlow v3.0 Hedge Fund Trap Defense)
        s24 = StrategyItem(
            id="strat-024",
            name="XAU/USD London-NY Velocity Scalp",
            type=StrategyType.SCALPING,
            category=StrategyCategory.SCALPING,
            symbol="XAU/USD",
            description="High-precision Gold scalping engine modeled on European Breakout (strat-006) zero-loss anti-fakeout DNA and OrderFlowEngine v3.0 hedge-fund trap detection. Operates strictly in the 07:00-13:30 UTC London/NY-open killzone with tight $3.50-$7.00 stops, 1.2R quick targets, and +0.65R fast breakeven scale-out.",
            marketCondition="High-Liquidity London/NY Velocity + Anti-Spoof Order Flow",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict 07:00-13:30 UTC Killzone Gate (83.3% historical XAU/USD win-rate window; blocks 14:00-21:00 UTC dead zone)",
                "True Scalp Risk Geometry: $3.50-$7.00 volatility-scaled stop with quick 1.2R ($4.80-$8.40) take-profit",
                "Fast +0.65R Breakeven Lock & 50% Scale-Out prevents winning scalps from reversing into stop-outs",
                "Transplanted strat-006 Anti-Wick Fakeout Filter (SWEEP_PROBE veto + >=45% body displacement + RVol >= 1.8x)",
                "OrderFlowEngine v3.0 Hedge Fund Trap Shield (blocks L2 DOM spoofing & passive dark-pool distribution)"
            ],
            weaknesses=["Strictly inactive outside 07:00-13:30 UTC or when Gold spread exceeds $0.45"],
            entryChecklist=[
                "Time within 07:00-13:30 UTC peak London/NY-open liquidity killzone",
                "XAU/USD live spread <= $0.45 USD (4.5 pips)",
                "H1 EMA 50/200 & Inverse DXY macro direction aligned",
                "No SWEEP_PROBE wick fakeout; M5/M15 candle body >= 45% with RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof wall or opposing institutional passive absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R",
                "Close remaining 50% at 1.2R quick scalp target ($4.80-$8.40)"
            ],
            idealVolatility="Moderate to High (London / NY Open)",
            avoidDuring=["US CPI / NFP Release", "14:00-21:00 UTC Low-Volume Stall", "Asian Pre-London Chop", "Spread > $0.45"],
            confirmationIndicators=["strat-006 Anti-Wick Filter", "OrderFlowEngine v3.0", "H1 EMA 50/200 + DXY Inverse", "M15 ATR Scalp Bounds"],
            successConditions=["07:00-13:30 UTC Killzone", "Spread <= $0.45", "RVol >= 1.8x & Body >= 45%", "No Hedge Fund Spoof/Absorption Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.2,
            preferredSessions=["London", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > $0.45", "Outside 07:00-13:30 UTC", "Hedge Fund Spoof/Absorption Trap", "Counter-DXY Move"],
            requiredConfirmations=["Killzone 07:00-13:30 UTC", "Spread <= $0.45", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 Hedge Fund Trap Check"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["London Breakout", "NY Open Velocity", "High-Liquidity Scalping"],
            estimatedHoldingTime="5-45 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-006-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="New XAU/USD Scalping Engine: Learns from EUR/USD strat-006 zero-loss anti-fakeout DNA + OrderFlowEngine v3.0 Hedge Fund Trap defense, with strict 07:00-13:30 UTC killzone, $3.50-$7.00 SL, 1.2R TP, and +0.65R fast breakeven.",
            dependencies=["OrderFlowEngine v3.0", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 25. GBP/USD Cable London-NY Velocity Scalp (Anti-Manipulation IFVG + OrderFlow v3.0 + EUR/USD Sync)
        s25 = StrategyItem(
            id="strat-025",
            name="GBP/USD Cable London-NY Velocity Scalp",
            type=StrategyType.SCALPING,
            category=StrategyCategory.SCALPING,
            symbol="GBP/USD",
            description="Apex institutional GBP/USD scalping engine engineered to outsmart London/NY Cable stop-hunts. Pairs Inversion FVG (IFVG) retail-trap reversals and SMC liquidity sweeps with strat-006 anti-wick DNA, OrderFlowEngine v3.0 spoof/iceberg radar, and mandatory EUR/USD + Inverse DXY cross-asset sync. Operates strictly in 07:00-11:00 & 12:30-15:30 UTC killzones with 8-18 pip stops, 1.25R targets, and +0.65R fast breakeven scale-out.",
            marketCondition="London/NY Institutional Liquidity Sweeps & Anti-Spoof Velocity",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict 07:00-11:00 & 12:30-15:30 UTC Killzones isolate peak Cable institutional velocity",
                "EUR/USD European Flow Sync + Inverse DXY vetoes isolated bank stop-hunts on GBP/USD",
                "Inversion FVG (IFVG) & Liquidity Sweep trap engine flips retail stop-outs into institutional entries",
                "Tight 8-18 pip scalp risk geometry with quick 1.25R (10-22.5p) TP & +0.65R fast BE + 50% scale-out",
                "OrderFlowEngine v3.0 blocks L2 DOM spoof walls & opposing dark-pool passive distribution"
            ],
            weaknesses=["Strictly inactive outside 07:00-11:00 / 12:30-15:30 UTC or when spread exceeds 1.4 pips"],
            entryChecklist=[
                "Time within 07:00-11:00 UTC or 12:30-15:30 UTC Cable killzones",
                "GBP/USD live spread <= 1.4 pips",
                "Authentic H1 EMA 50/200 trend + Inverse DXY + EUR/USD European sync aligned",
                "IFVG retail trap flip, SMC sweep reclaim, or corridor retest with >= 45% body & RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof trap or opposing institutional iceberg absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R (+0.33R banked on BE reversals)",
                "Close remaining 50% at 1.25R quick scalp target (10-22.5 pips)"
            ],
            idealVolatility="Moderate to High (London Open / NY Overlap)",
            avoidDuring=["BOE Rate Decision", "UK CPI", "US NFP / CPI", "Spread > 1.4 pips"],
            confirmationIndicators=["Inversion FVG (IFVG) Engine", "OrderFlowEngine v3.0", "EUR/USD Sync + Inverse DXY", "H1 EMA 50/200"],
            successConditions=["Cable Killzone Active", "Spread <= 1.4 pips", "Body >= 45% & RVol >= 1.8x", "No Spoof/Divergence Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["London", "London-NY Overlap", "NY Overlap", "New York"],
            avoidConditions=["Spread > 1.4 pips", "EUR/USD Divergence > 0.15%", "Double-Sweep Whipsaw Day", "Hedge Fund Spoof Trap"],
            requiredConfirmations=["Cable Killzone (07:00-11:00 / 12:30-15:30 UTC)", "Spread <= 1.4 pips", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 & EUR/USD Sync"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["London Open Velocity", "NY Overlap", "Anti-Trap Scalping"],
            estimatedHoldingTime="5-45 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-024-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Velocity Scalp (GBP/USD): IFVG anti-retail trap engine + OrderFlow v3.0 + EUR/USD flow sync + 07:00-11:00 & 12:30-15:30 UTC killzones, 8-18p SL, 1.25R TP, +0.65R fast BE scale-out.",
            dependencies=["OrderFlowEngine v3.0", "Smart Money IFVG Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 26. GBP/JPY Dragon Anti-Trap Velocity Retest (Dual Yen-Cross Sync + IFVG + OrderFlow v3.0)
        s26 = StrategyItem(
            id="strat-026",
            name="GBP/JPY Dragon Anti-Trap Velocity Retest",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="GBP/JPY",
            description="Apex institutional GBP/JPY ('Dragon') anti-manipulation intraday engine. Eliminates synthetic Yen-cross stop-hunts using mandatory Dual Yen-Cross Sync (GBP/USD + USD/JPY), Inversion FVG (IFVG) trap flips, SMC Tokyo/London liquidity sweeps, and OrderFlowEngine v3.0 spoof/iceberg detection. Operates strictly in 00:00-03:30, 07:00-11:00 & 12:30-15:00 UTC killzones with 14-28 pip stops, 1.25R targets, and +0.65R fast breakeven scale-out.",
            marketCondition="Tokyo Fix / London Open / Overlap High-Beta Dragon Velocity",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Tokyo Fix (00:00-03:30), London (07:00-11:00) & Overlap (12:30-15:00 UTC) Killzones",
                "Mandatory Dual Yen-Cross Sync (GBP/USD & USD/JPY) blocks synthetic Dragon whipsaw stop-hunts",
                "Inversion FVG (IFVG) & Liquidity Sweep engine harvests trapped Dragon breakout traders",
                "Calibrated 14-28 pip scalp stop with fast 1.25R (17.5-35p) target & +0.65R fast BE + 50% scale-out",
                "OrderFlowEngine v3.0 blocks L2 DOM spoof walls & opposing passive iceberg absorption"
            ],
            weaknesses=["Strictly inactive outside Tokyo/London/Overlap killzones or when spread exceeds 2.4 pips"],
            entryChecklist=[
                "Time within 00:00-03:30, 07:00-11:00, or 12:30-15:00 UTC Dragon killzones",
                "GBP/JPY live spread <= 2.4 pips",
                "Authentic H1 EMA 50/200 trend + Dual Yen-Cross Sync (GBP/USD & USD/JPY aligned)",
                "IFVG retail trap flip, SMC sweep reclaim, or corridor retest with >= 45% body & RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof trap or opposing institutional iceberg absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R (+0.33R banked on BE reversals)",
                "Close remaining 50% at 1.25R quick Dragon scalp target (17.5-35 pips)"
            ],
            idealVolatility="High (Tokyo Fix / London Open / Overlap)",
            avoidDuring=["BOJ / BOE Rate Decisions", "Unscheduled BOJ Intervention", "Spread > 2.4 pips"],
            confirmationIndicators=["Inversion FVG (IFVG) Engine", "OrderFlowEngine v3.0", "Dual Yen-Cross Sync (GU+UJ)", "H1 EMA 50/200"],
            successConditions=["Dragon Killzone Active", "Spread <= 2.4 pips", "Body >= 45% & RVol >= 1.8x", "No Yen-Cross Divergence or Spoof Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["Asian", "Tokyo", "London", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > 2.4 pips", "GBP/USD vs USD/JPY Divergence > 0.15%", "Double-Sweep Whipsaw Day", "Hedge Fund Spoof Trap"],
            requiredConfirmations=["Dragon Killzone (Tokyo/London/Overlap)", "Spread <= 2.4 pips", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 & Dual Yen-Cross Sync"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Tokyo Fix", "London Open Volatility", "Anti-Trap Dragon Scalping"],
            estimatedHoldingTime="5-40 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-024-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Velocity Scalp (GBP/JPY): IFVG anti-retail trap engine + OrderFlow v3.0 + Dual Yen-Cross Sync (GU+UJ) + Tokyo/London/Overlap killzones, 14-28p SL, 1.25R TP, +0.65R fast BE scale-out.",
            dependencies=["OrderFlowEngine v3.0", "Smart Money IFVG Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 27. USD/JPY Ninja Yield-Lock Velocity Scalp (US 10Y Yield + Direct DXY + IFVG + OrderFlow v3.0)
        s27 = StrategyItem(
            id="strat-027",
            name="USD/JPY Ninja Yield-Lock Velocity Scalp",
            type=StrategyType.SCALPING,
            category=StrategyCategory.SCALPING,
            symbol="USD/JPY",
            description="Apex institutional USD/JPY ('Ninja') yield-driven scalping engine. Exploits Tokyo Gotobi Fix sweeps and NY Open US Treasury Yield waves using Inversion FVG (IFVG) trap flips, SMC sweeps, OrderFlowEngine v3.0 spoof/iceberg radar, and mandatory Direct Synthetic DXY + US 10Y Yield lock. Operates strictly in 00:00-03:30 & 12:30-16:00 UTC killzones with 10-20 pip stops, 1.25R targets, and +0.65R fast breakeven scale-out.",
            marketCondition="Tokyo Fix & NY Bond-Yield Institutional Velocity",
            bestSession="London-NY Overlap",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Tokyo Fix (00:00-03:30 UTC) & NY Bond-Yield Open (12:30-16:00 UTC) Killzones",
                "Mandatory Direct Synthetic DXY + US 10Y Yield Proxy lock prevents counter-yield traps",
                "Inversion FVG (IFVG) & Liquidity Sweep engine rides sovereign institutional waves",
                "Tight 10-20 pip scalp stop with quick 1.25R (12.5-25p) target & +0.65R fast BE + 50% scale-out",
                "OrderFlowEngine v3.0 blocks L2 DOM spoof walls & opposing passive iceberg absorption"
            ],
            weaknesses=["Strictly inactive outside 00:00-03:30 / 12:30-16:00 UTC or when spread exceeds 1.3 pips"],
            entryChecklist=[
                "Time within 00:00-03:30 UTC or 12:30-16:00 UTC Ninja killzones",
                "USD/JPY live spread <= 1.3 pips",
                "Authentic H1 EMA 50/200 trend + Direct DXY & US 10Y Yield proxy aligned",
                "IFVG retail trap flip, SMC sweep reclaim, or corridor retest with >= 45% body & RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof trap or opposing institutional iceberg absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R (+0.33R banked on BE reversals)",
                "Close remaining 50% at 1.25R quick Ninja scalp target (12.5-25 pips)"
            ],
            idealVolatility="Moderate to High (Tokyo Fix / NY Bond Open)",
            avoidDuring=["FOMC / NFP / US CPI", "BOJ Rate Decision / Intervention", "Spread > 1.3 pips"],
            confirmationIndicators=["Inversion FVG (IFVG) Engine", "OrderFlowEngine v3.0", "US 10Y Yield + Direct DXY Lock", "H1 EMA 50/200"],
            successConditions=["Ninja Killzone Active", "Spread <= 1.3 pips", "Body >= 45% & RVol >= 1.8x", "No DXY/Yield Divergence or Spoof Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["Asian", "Tokyo", "London-NY Overlap", "NY Overlap", "New York"],
            avoidConditions=["Spread > 1.3 pips", "Counter-Yield / Counter-DXY Trap", "Double-Sweep Whipsaw Day", "Hedge Fund Spoof Trap"],
            requiredConfirmations=["Ninja Killzone (00:00-03:30 / 12:30-16:00 UTC)", "Spread <= 1.3 pips", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 & US Yield/DXY Lock"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Tokyo Gotobi Fix", "NY Yield Waves", "Anti-Trap Scalping"],
            estimatedHoldingTime="5-45 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-024-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Velocity Scalp (USD/JPY): IFVG anti-retail trap engine + OrderFlow v3.0 + US 10Y Yield/DXY lock + Tokyo Fix & NY Open killzones, 10-20p SL, 1.25R TP, +0.65R fast BE scale-out.",
            dependencies=["OrderFlowEngine v3.0", "Smart Money IFVG Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 28. AUD/USD Aussie Gold-Locked Velocity Scalp (Gold Lockstep + Inverse DXY + IFVG + OrderFlow v3.0)
        s28 = StrategyItem(
            id="strat-028",
            name="AUD/USD Aussie Gold-Locked Velocity Scalp",
            type=StrategyType.SCALPING,
            category=StrategyCategory.SCALPING,
            symbol="AUD/USD",
            description="Apex institutional AUD/USD ('Aussie') commodity-locked scalping engine. Exploits Sydney/Tokyo, London Open, and NY Open stop-hunts using Inversion FVG (IFVG) trap flips, SMC liquidity sweeps, OrderFlowEngine v3.0 spoof/iceberg radar, and mandatory Gold (XAU/USD) Commodity Lockstep + Inverse Synthetic DXY confirmation. Operates strictly in 00:00-04:00, 07:00-11:00 & 12:30-15:00 UTC killzones with 7-15 pip stops, 1.25R targets, and +0.65R fast breakeven scale-out.",
            marketCondition="Pacific / London / NY Commodity-FX Liquidity Velocity",
            bestSession="Asian",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Pacific (00:00-04:00), London (07:00-11:00) & NY Open (12:30-15:00 UTC) Killzones",
                "Secret Weapon Gold (XAU/USD) Lockstep + Inverse DXY blocks fake AUD/USD breakouts",
                "Inversion FVG (IFVG) & Liquidity Sweep engine flips retail traps into high-WR scalps",
                "Ultra-tight 7-15 pip scalp stop with fast 1.25R (8.75-18.75p) target & +0.65R fast BE + 50% scale-out",
                "OrderFlowEngine v3.0 blocks L2 DOM spoof walls & opposing passive iceberg absorption"
            ],
            weaknesses=["Strictly inactive outside Pacific/London/NY killzones or when spread exceeds 1.2 pips"],
            entryChecklist=[
                "Time within 00:00-04:00, 07:00-11:00, or 12:30-15:00 UTC Aussie killzones",
                "AUD/USD live spread <= 1.2 pips",
                "Authentic H1 EMA 50/200 trend + Gold (XAU/USD) Lockstep + Inverse DXY aligned",
                "IFVG retail trap flip, SMC sweep reclaim, or corridor retest with >= 45% body & RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof trap or opposing institutional iceberg absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R (+0.33R banked on BE reversals)",
                "Close remaining 50% at 1.25R quick Aussie scalp target (8.75-18.75 pips)"
            ],
            idealVolatility="Moderate (Sydney/Tokyo Peak, London Open & NY Open)",
            avoidDuring=["RBA Rate Statement", "AU Employment / CPI", "US NFP / CPI", "Spread > 1.2 pips"],
            confirmationIndicators=["Inversion FVG (IFVG) Engine", "OrderFlowEngine v3.0", "Gold (XAU/USD) Lockstep + Inverse DXY", "H1 EMA 50/200"],
            successConditions=["Aussie Killzone Active", "Spread <= 1.2 pips", "Body >= 45% & RVol >= 1.8x", "No Gold/DXY Divergence or Spoof Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["Asian", "Sydney", "Tokyo", "London", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > 1.2 pips", "Gold (XAU/USD) Divergence > 0.15%", "Double-Sweep Whipsaw Day", "Hedge Fund Spoof Trap"],
            requiredConfirmations=["Aussie Killzone (Pacific/London/NY)", "Spread <= 1.2 pips", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 & Gold/DXY Lock"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Sydney/Tokyo Liquidity", "London Open", "Commodity-FX Anti-Trap Scalping"],
            estimatedHoldingTime="5-45 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-024-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Velocity Scalp (AUD/USD): IFVG anti-retail trap engine + OrderFlow v3.0 + Gold (XAU/USD) Lockstep & Inverse DXY + Pacific/London/NY killzones, 7-15p SL, 1.25R TP, +0.65R fast BE scale-out.",
            dependencies=["OrderFlowEngine v3.0", "Smart Money IFVG Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 29. EUR/USD Fiber Frankfurt-NY Velocity Scalp (Dual SMT GBP/USD + Inverse USD/JPY Lock + IFVG + OrderFlow v3.0)
        s29 = StrategyItem(
            id="strat-029",
            name="EUR/USD Fiber Frankfurt-NY Velocity Scalp",
            type=StrategyType.SCALPING,
            category=StrategyCategory.SCALPING,
            symbol="EUR/USD",
            description="Apex institutional EUR/USD ('Fiber') anti-manipulation scalping engine complementing European Breakout (strat-006). Pairs Inversion FVG (IFVG) retail-trap flips and SMC Frankfurt/London Judas-swing sweeps with OrderFlowEngine v3.0 spoof/iceberg radar and a Dual Fiber SMT & Broad-USD Lock (GBP/USD alignment + Inverse USD/JPY verification). Operates strictly in 06:45-10:30 & 12:30-15:30 UTC killzones with <= 1.0p spread, 7-14p stops, 1.25R targets, and +0.65R fast breakeven scale-out.",
            marketCondition="Frankfurt/London Open Judas Swing & NY Overlap Fiber Velocity",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Frankfurt/London (06:45-10:30 UTC) & NY Overlap (12:30-15:30 UTC) Killzones block late-day drift traps",
                "Dual Fiber SMT & Broad-USD Shield (GBP/USD sync + Inverse USD/JPY) eliminates circular DXY stop-hunts",
                "Inversion FVG (IFVG) & Liquidity Sweep trap engine flips retail breakout stop-outs into institutional entries",
                "Ultra-tight 7-14 pip Fiber scalp risk geometry with quick 1.25R (8.75-17.5p) TP & +0.65R fast BE + 50% scale-out",
                "Ultra-tight <= 1.0 pip spread guard + OrderFlowEngine v3.0 L2 spoof & passive iceberg absorption radar"
            ],
            weaknesses=["Strictly inactive outside 06:45-10:30 / 12:30-15:30 UTC or when EUR/USD spread exceeds 1.0 pip"],
            entryChecklist=[
                "Time within 06:45-10:30 UTC or 12:30-15:30 UTC Fiber institutional killzones",
                "EUR/USD live spread <= 1.0 pip",
                "Authentic H1 EMA 50/200 trend + GBP/USD SMT sync + Inverse USD/JPY broad-USD lock aligned",
                "IFVG retail trap flip, SMC sweep reclaim, or corridor retest with >= 45% body & RVol >= 1.8x",
                "OrderFlowEngine v3.0 confirms no L2 spoof trap or opposing institutional iceberg absorption"
            ],
            exitChecklist=[
                "Lock Breakeven & bank 50% partial at +0.65R (+0.33R banked on BE reversals)",
                "Close remaining 50% at 1.25R quick Fiber scalp target (8.75-17.5 pips)"
            ],
            idealVolatility="Moderate to High (Frankfurt / London Open / NY Overlap)",
            avoidDuring=["ECB Rate Decision", "Eurozone CPI", "US NFP / CPI / FOMC", "Spread > 1.0 pip"],
            confirmationIndicators=["Inversion FVG (IFVG) Engine", "OrderFlowEngine v3.0", "GBP/USD SMT + Inverse USD/JPY Lock", "H1 EMA 50/200"],
            successConditions=["Fiber Killzone Active", "Spread <= 1.0 pip", "Body >= 45% & RVol >= 1.8x", "No SMT/Broad-USD Divergence or Spoof Veto"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["Frankfurt", "London", "London-NY Overlap", "NY Overlap", "New York"],
            avoidConditions=["Spread > 1.0 pip", "GBP/USD SMT Divergence > 0.15%", "USD/JPY Broad-USD Contradiction > 0.20%", "Double-Sweep Whipsaw Day"],
            requiredConfirmations=["Fiber Killzone (06:45-10:30 / 12:30-15:30 UTC)", "Spread <= 1.0 pip", "Anti-Wick Fakeout Filter (v3.2)", "OrderFlow v3.0 & Dual Fiber SMT/USD Lock"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Frankfurt Open", "London Judas Swing", "NY Overlap Anti-Trap Scalping"],
            estimatedHoldingTime="5-45 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-024-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Velocity Scalp (EUR/USD): IFVG anti-retail trap engine + OrderFlow v3.0 + Dual Fiber SMT (GBP/USD) & Inverse USD/JPY Lock + Frankfurt/London & NY Overlap killzones, <= 1.0p spread, 7-14p SL, 1.25R TP, +0.65R fast BE scale-out.",
            dependencies=["OrderFlowEngine v3.0", "Smart Money IFVG Engine", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 30. NZD/USD Pacific Range Sweep & Sister-SMT Momentum
        s30 = StrategyItem(
            id="strat-030",
            name="NZD/USD Pacific Range Sweep & Sister-SMT Momentum",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="NZD/USD",
            description="Institutional NZD/USD ('Kiwi') Pacific liquidity sweep and sister-SMT momentum engine. Harvests liquidity traps formed during the tight Asian Pacific consolidation range (06:00-10:30 & 12:30-15:30 UTC killzones). Enforces mandatory Sister-Currency (AUD/USD) SMT divergence verification, inverse DXY macro lock, 3-candle FVG displacement, 8-16 pip stops, 1.25R-1.35R targets, and universal +0.65R fast breakeven protection.",
            marketCondition="Asian Pacific Range Sweep / European Transition & NY Overlap",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Asian-to-London (06:00-10:30 UTC) & NY Overlap (12:30-15:30 UTC) Killzones",
                "AUD/USD Sister-Currency SMT Divergence Gate eliminates isolated Kiwi traps",
                "Inversion FVG & Pacific Range Reclaim with >= 45% body displacement & RVol >= 1.5x",
                "Calibrated 8-16 pip stop with +1.8 pip retail buffer, 1.25R-1.35R target & +0.65R breakeven lock",
                "Inverse DXY Macro Alignment prevents counter-dollar liquidity traps"
            ],
            weaknesses=["Strictly inactive outside 06:00-10:30 & 12:30-15:30 UTC, Monday Asian open, or when spread > 2.0 pips"],
            entryChecklist=[
                "Time within 06:00-10:30 UTC or 12:30-15:30 UTC Kiwi killzones",
                "NZD/USD live spread <= 2.0 pips",
                "Sweep of Asian/PDH/PDL range followed by confirmed M15 candle close back inside range",
                "Displacement with >= 45% body ratio and RVol >= 1.5x printing 3-candle FVG",
                "AUD/USD Sister-SMT alignment confirms commodity-currency institutional flow",
                "Inverse DXY alignment confirms broad US Dollar trend consistency"
            ],
            exitChecklist=[
                "Universal Fast Breakeven Lock at +0.65R excursion",
                "Take Profit at 1.25R - 1.35R (12-22 pips)"
            ],
            idealVolatility="Moderate to High (Asian Close / European Open / NY Overlap)",
            avoidDuring=["RBNZ Rate Decisions", "US NFP / FOMC / CPI", "Spread > 2.0 pips", "Monday Asian Open (<07:30 UTC)"],
            confirmationIndicators=["Pacific Range Sweep Engine", "AUD/USD SMT Gate", "Inverse DXY Lock", "H1 EMA 50/200"],
            successConditions=["Kiwi Killzone Active", "Spread <= 2.0 pips", "Body >= 45% & RVol >= 1.5x", "AUD/USD SMT Alignment Pass"],
            minimumConfidence=85,
            minimumRiskReward=1.25,
            preferredSessions=["London", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > 2.0 pips", "AUD/USD SMT Divergence > 0.15%", "Monday Asian Open", "Double-Sweep Whipsaw"],
            requiredConfirmations=["Kiwi Killzone (06:00-10:30 / 12:30-15:30 UTC)", "Spread <= 2.0 pips", "Anti-Wick Fakeout Filter (v3.2)", "AUD/USD SMT & DXY Lock"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Pacific Range Sweep", "European Transition", "Anti-Trap Momentum"],
            estimatedHoldingTime="10-60 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-006-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Pacific Sweep (NZD/USD): Asian range sweep + AUD/USD SMT gate + Inverse DXY lock + 06:00-10:30 & 12:30-15:30 UTC killzones, 8-16p SL, 1.25R-1.35R TP, +0.65R fast BE scale-out.",
            dependencies=["Smart Money Sweep Engine", "Sister SMT Gate", "Macro Cross-Asset Gate", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 31. EUR/JPY Frankfurt Judas Sweep & Dual-Cross Momentum
        s31 = StrategyItem(
            id="strat-031",
            name="EUR/JPY Frankfurt Judas Sweep & Dual-Cross Momentum",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.INTRADAY,
            symbol="EUR/JPY",
            description="Institutional EUR/JPY ('Eura-Yen') session breakout and dual-cross momentum engine. Exploits the London open Judas swing fakeout against the early Frankfurt 06:00 UTC corridor (06:45-11:30 & 12:30-16:00 UTC killzones). Enforces mandatory Dual Cross-Asset Sync (EUR/USD + USD/JPY net flow), Inversion FVG retest, anti-wick candle close verification, 12-22 pip stops, 1.30R-1.50R targets, and universal +0.65R fast breakeven protection.",
            marketCondition="Frankfurt Judas Swing Reversal & London-NY Overlap Yen Momentum",
            bestSession="London",
            bestTimeframe="M15",
            riskLevel=RiskLevel.MEDIUM,
            status=StrategyStatus.ACTIVE,
            health=StrategyHealth.EXCELLENT,
            performance=EMPTY_PERFORMANCE.model_copy(),
            strengths=[
                "Strict Frankfurt/London Open (06:45-11:30 UTC) & NY Overlap (12:30-16:00 UTC) Killzones",
                "Frankfurt Judas Swing (8-18 pip fakeout) reversal harvests trapped early breakout retail traders",
                "Mandatory Dual Cross-Asset Sync (EUR/USD + USD/JPY) ensures true institutional net flow without cross-currency drag",
                "Inversion FVG boundary retest with >= 45% candle body & RVol >= 1.8x",
                "Calibrated 12-22 pip stop with +2.5 pip retail buffer, 1.30R-1.50R target & +0.65R breakeven lock"
            ],
            weaknesses=["Strictly inactive outside Frankfurt/London/NY killzones, post-16:00 UTC, or when spread > 2.0 pips"],
            entryChecklist=[
                "Time within 06:45-11:30 UTC or 12:30-16:00 UTC Eura-Yen killzones",
                "EUR/JPY live spread <= 2.0 pips",
                "Frankfurt Judas swing (8-18p) rejected with confirmed M15 candle close back inside corridor",
                "Displacement with >= 45% body ratio and RVol >= 1.8x retesting IFVG boundary",
                "Dual Cross-Asset Sync: EUR/USD and USD/JPY both confirm aligned net directional flow"
            ],
            exitChecklist=[
                "Universal Fast Breakeven Lock at +0.65R excursion",
                "Take Profit at 1.30R - 1.50R (18-35 pips)"
            ],
            idealVolatility="High (Frankfurt / London Open / Overlap)",
            avoidDuring=["ECB / BOJ Rate Decisions", "Unscheduled BOJ Intervention", "Spread > 2.0 pips", "Post-16:00 UTC"],
            confirmationIndicators=["Frankfurt Judas Sweep Engine", "Dual Cross-Asset Sync (EU+UJ)", "IFVG Retest Engine", "H1 EMA 20/50"],
            successConditions=["Eura-Yen Killzone Active", "Spread <= 2.0 pips", "Body >= 45% & RVol >= 1.8x", "Dual Cross-Asset Sync Pass"],
            minimumConfidence=85,
            minimumRiskReward=1.30,
            preferredSessions=["Frankfurt", "London", "London-NY Overlap", "NY Overlap"],
            avoidConditions=["Spread > 2.0 pips", "EUR/USD vs USD/JPY Divergence > 0.15%", "Double-Sweep Whipsaw Day"],
            requiredConfirmations=["Eura-Yen Killzone (06:45-11:30 / 12:30-16:00 UTC)", "Spread <= 2.0 pips", "Anti-Wick Fakeout Filter (v3.2)", "Dual Cross Sync (EUR/USD + USD/JPY)"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Frankfurt Open", "London Judas Swing", "Anti-Trap Yen Momentum"],
            estimatedHoldingTime="10-60 minutes",
            maxConsecutiveLosses=2,
            createdAt=now,
            updatedAt=now,
            lastReviewedAt=now,
            strategyVersion="1.0",
            parentStrategyId="strat-006-dna",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Apex FX Judas Reversal (EUR/JPY): Frankfurt Judas swing + Dual Cross Sync (EU+UJ) + IFVG retest + Frankfurt/London & Overlap killzones, 12-22p SL, 1.30R-1.50R TP, +0.65R fast BE scale-out.",
            dependencies=["Frankfurt Judas Engine", "Dual Cross-Asset Gate", "Smart Money IFVG Engine", "Market Session Engine"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # Pure Intraday + Gold Multi-Engine Roster: Strictly 9 active strategies
        strategies = [s4, s6, s12, s13, s23, s24, s26, s30, s31]
        default_active_ids = {
            "strat-004",  # GBP/USD London Momentum (Intraday)
            "strat-006",  # EUR/USD European Breakout (Intraday Flagship)
            "strat-012",  # XAU/USD Institutional Liquidity Sweep & FVG (Intraday)
            "strat-013",  # USD/JPY Tokyo Fix & Asian Range Sweep (Intraday)
            "strat-023",  # AUD/USD Liquidity Sweep + Gold/DXY Displacement (Intraday)
            "strat-024",  # XAU/USD London-NY Velocity Scalp (Scalp - Gold Only)
            "strat-026",  # GBP/JPY Dragon Anti-Trap Velocity Retest (Intraday)
            "strat-030",  # NZD/USD Pacific Range Sweep & Sister-SMT Momentum (Intraday)
            "strat-031",  # EUR/JPY Frankfurt Judas Sweep & Dual-Cross Momentum (Intraday)
        }
        for strategy in strategies:
            strategy.status = StrategyStatus.ACTIVE if strategy.id in default_active_ids else StrategyStatus.DEPRECATED
            strategy.readyForExecution = (strategy.status == StrategyStatus.ACTIVE)
            if strategy.minimumRiskReward and strategy.minimumRiskReward > 1.5:
                strategy.minimumRiskReward = 1.5
            strategy.strategyScore.riskRating = strategy.riskLevel
            if strategy.id != "strat-006":
                v32_upgrade_notes = {
                    "strat-001": "v3.2 Upgrade: Ignores initial wick fakeouts (SWEEP_PROBE veto) + requires RVol >= 1.8x London range expansion & EMA 200 alignment.",
                    "strat-002": "v3.2 Upgrade: Ignores initial wick fakeouts + enforces H1 EMA 20/50 structural pullback & $14+ Gold volatility stop floor.",
                    "strat-003": "v3.2 Upgrade: Ignores initial wick breakouts at H4 S/R zones + demands confirmed pinbar/engulfing rejection close & RSI divergence.",
                    "strat-004": "v3.2 Upgrade: Ignores initial wick fakeouts (SWEEP_PROBE filter) + requires >= 45% momentum candle body displacement, RVol surge & H1 EMA 20/50 alignment.",
                    "strat-005": "v3.2 Upgrade: Ignores initial wick fakeouts + requires M30 structural support bounce, bullish/bearish engulfing close & DXY alignment.",
                    "strat-007": "v3.2 Upgrade: Ignores initial wick fakeouts (SWEEP_PROBE veto) + enforces H4/Daily EMA 20/50 trend continuation & inverse DXY confirmation.",
                    "strat-008": "v3.2 Upgrade: Ignores initial wick breakouts + requires single-sided session corridor break, RVol >= 1.8x surge & candle spread >= 60%.",
                    "strat-009": "v3.2 Upgrade: Ignores initial wick breakouts + enforces Bollinger Band (20,2) outer exhaustion with RSI <35/>65 & 20-SMA mean reversion.",
                    "strat-010": "v3.2 Upgrade: Ignores initial wick fakeouts + enforces H4 BOS, 50/200 EMA dynamic pullback & macro DXY alignment.",
                    "strat-011": "v3.2 Upgrade: Ignores initial wick fakeouts + pairs 30+ institutional candlestick patterns with key S/R zones & $14+ Gold structural stops.",
                    "strat-012": "v3.2 Upgrade: Ignores initial wick fakeouts + pairs PDH/PDL/Asian liquidity sweep + 3-Candle FVG with inverse DXY & $14+ Gold stop floor.",
                    "strat-013": "v3.2 Upgrade: Ignores initial wick fakeouts + harvests Tokyo Fix & Asian range sweeps with 3-Candle FVG & US Yield/DXY alignment.",
                    "strat-014": "v3.2 Upgrade: Ignores initial wick breakouts (SWEEP_PROBE veto) + requires single-sided corridor break, RVol >= 1.8x & US Yield/DXY lock.",
                    "strat-015": "v3.2 Upgrade: Ignores initial wick breakouts + requires Tokyo corridor break & retest, RVol >= 1.8x & GBP/USD + USD/JPY Yen-cross sync.",
                    "strat-016": "v3.2 Upgrade: Ignores initial wick fakeouts + enforces 3-Candle FVG pullback, H1 EMA 20/50 trend, 32p+ stop floor & Yen-cross sync.",
                    "strat-017": "v3.2 Upgrade: Ignores initial wick fakeouts + enforces AUD/USD Asian/PDH sweep + 3-Candle FVG with mandatory Gold (XAU/USD) & inverse DXY lock.",
                    "strat-018": "v3.2 Upgrade: Ignores initial wick fakeouts + enforces AUD/USD H1 EMA 20/50 pullback with mandatory Gold (XAU/USD) & inverse DXY confluence.",
                    "strat-019": "v3.2 Upgrade: Ignores initial wick fakeouts (SWEEP_PROBE filter) + requires >= 45% Gold momentum candle body displacement, RVol surge & $14+ stop floor.",
                    "strat-020": "v3.2 Upgrade: Ignores initial wick fakeouts (SWEEP_PROBE filter) + requires >= 45% Euro momentum candle body displacement, RVol surge & inverse DXY lock.",
                    "strat-021": "v3.2 Upgrade: Ignores initial wick fakeouts + requires 10-25p Asian liquidity sweep, BOS/FVG displacement, 32p+ stop floor & GBP/USD + USD/JPY Yen-cross sync.",
                    "strat-022": "v3.2 Upgrade: Ignores initial wick fakeouts + requires 10-20p Pre-NY/Tokyo sweep + BOS/FVG or RVol >= 1.8x break-retest aligned with US Yield & DXY.",
                    "strat-023": "v3.2 Upgrade: Ignores initial wick fakeouts + requires 8-15p AUD/USD liquidity sweep + BOS/FVG with mandatory Gold (XAU/USD) & inverse DXY macro lock.",
                    "strat-024": "v3.2 Scalp Standard: Transplanted EUR/USD strat-006 zero-loss anti-fakeout DNA + OrderFlowEngine v3.0 Hedge Fund Trap Shield. Strict 07:00-13:30 UTC Killzone, <= $0.45 spread, $3.50-$7.00 SL, 1.2R quick TP, and +0.65R fast breakeven lock.",
                    "strat-025": "v3.2 Apex Cable Scalp: IFVG anti-retail trap flip + OrderFlowEngine v3.0 + EUR/USD flow sync. Strict 07:00-11:00 & 12:30-15:30 UTC Killzones, <= 1.4p spread, 8-18p SL, 1.25R TP, +0.65R fast BE scale-out.",
                    "strat-026": "v3.2 Apex Dragon Scalp: IFVG anti-retail trap flip + OrderFlowEngine v3.0 + Dual Yen-Cross Sync (GU+UJ). Strict Tokyo/London/Overlap Killzones, <= 2.4p spread, 14-28p SL, 1.25R TP, +0.65R fast BE scale-out.",
                    "strat-027": "v3.2 Apex Ninja Scalp: IFVG anti-retail trap flip + OrderFlowEngine v3.0 + US 10Y Yield/DXY Lock. Strict 00:00-03:30 & 12:30-16:00 UTC Killzones, <= 1.3p spread, 10-20p SL, 1.25R TP, +0.65R fast BE scale-out.",
                    "strat-028": "v3.2 Apex Aussie Scalp: IFVG anti-retail trap flip + OrderFlowEngine v3.0 + Gold (XAU/USD) Lockstep. Strict Pacific/London/NY Killzones, <= 1.2p spread, 7-15p SL, 1.25R TP, +0.65R fast BE scale-out.",
                    "strat-029": "v3.2 Apex Fiber Scalp: IFVG anti-retail trap flip + OrderFlowEngine v3.0 + Dual Fiber SMT (GBP/USD) & Inverse USD/JPY Lock. Strict 06:45-10:30 & 12:30-15:30 UTC Killzones, <= 1.0p spread, 7-14p SL, 1.25R TP, +0.65R fast BE scale-out.",
                    "strat-030": "v3.2 Kiwi Pacific Sweep: Asian range sweep + AUD/USD Sister-SMT divergence gate + Inverse DXY lock + 06:00-10:30 & 12:30-15:30 UTC Killzones, <= 2.0p spread, 8-16p SL, 1.25R-1.35R TP, +0.65R fast BE scale-out.",
                    "strat-031": "v3.2 Eura-Yen Judas Reversal: Frankfurt Judas swing fakeout + Dual Cross Sync (EUR/USD & USD/JPY) + IFVG retest + 06:45-11:30 & 12:30-16:00 UTC Killzones, <= 2.0p spread, 12-22p SL, 1.30R-1.50R TP, +0.65R fast BE scale-out.",
                }
                old_ver = strategy.strategyVersion or "1.0"
                strategy.parentStrategyId = f"{strategy.id}-v{old_ver}"
                strategy.strategyVersion = "3.2"
                if strategy.id in v32_upgrade_notes:
                    strategy.reviewNotes = v32_upgrade_notes[strategy.id]
                if "Anti-Wick Fakeout Filter (v3.2)" not in strategy.requiredConfirmations:
                    strategy.requiredConfirmations = list(strategy.requiredConfirmations) + ["Anti-Wick Fakeout Filter (v3.2)"]
        return strategies


strategy_engine = StrategyEngine()
