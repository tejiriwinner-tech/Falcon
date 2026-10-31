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
                self.__class__._status_overrides[s.id.lower()] = StrategyStatus.INCUBATION
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
        return affected

    def pause_expansion_strategies(self) -> List[str]:
        """Pause the 6 multi-pair expansion strategies (strat-013 through strat-018)."""
        self.__class__._expansion_paused = True
        for sid in EXPANSION_STRATEGY_IDS:
            self.__class__._paused_strategy_ids.add(sid)
        return sorted(EXPANSION_STRATEGY_IDS)

    def resume_expansion_strategies(self) -> List[str]:
        """Resume the 6 multi-pair expansion strategies (strat-013 through strat-018)."""
        self.__class__._expansion_paused = False
        for sid in EXPANSION_STRATEGY_IDS:
            self.__class__._paused_strategy_ids.discard(sid)
        for sym in ("USDJPY", "GBPJPY", "AUDUSD"):
            self.__class__._paused_symbols.discard(sym)
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
            strategyVersion="2.3",
            parentStrategyId="strat-001-v2.1",
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Removed RSI filter. Added EMA 200 confirmation. Reduced SL from 25 to 18 pips.",
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
            strategyVersion="1.1",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Updated default stop-loss buffer.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Active S/R bounce framework for horizontal ranges.",
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
            riskLevel=RiskLevel.HIGH,
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
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=5,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 7, 1, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="2.0",
            parentStrategyId="strat-004-v1.0",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Slightly reduced leverage recommendations.",
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
            strategyVersion="1.2",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Active GBP/USD structural pullback strategy.",
            dependencies=["Trend Bias"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        # 6. European Breakout
        s6 = StrategyItem(
            id="strat-006",
            name="European Breakout",
            type=StrategyType.BREAKOUT,
            category=StrategyCategory.SCALPING,
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
            preferredSessions=["London", "New York", "Asian"],
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
            strategyVersion="1.5",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=True,
            reviewNotes="Active long-term EUR/USD trend continuation model.",
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
            strategyVersion="2.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Upgraded to Session Momentum & Multi-Timeframe Volume Expansion engine.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Optimized for overnight Asian session automated tracking.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Captain",
            readyForExecution=False,
            reviewNotes="Institutional swing framework for capturing macro moves.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Integrated institutional candlestick engine covering 30+ classical & SMC patterns.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Institutional Smart Money Concepts (SMC) Liquidity Sweep & FVG sniper engine.",
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
            strategyVersion="1.0",
            parentStrategyId="strat-009",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Paired with strat-009 to harvest Tokyo Fix and London Open liquidity sweeps on USD/JPY.",
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
            strategyVersion="1.0",
            parentStrategyId="strat-009",
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Pairs with strat-009 so USD/JPY transitions seamlessly from Asian mean reversion to London/NY yield breakouts.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Dedicated institutional session breakout strategy for GBP/JPY.",
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Institutional SMC & FVG pullback sniper for GBP/JPY.",
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
            riskLevel=RiskLevel.LOW,
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
                "1:2.8+ R:R target pool reached",
                "Breakeven stop locked at +1.5R"
            ],
            idealVolatility="Medium",
            avoidDuring=["RBA Rate Decision", "US CPI / NFP"],
            confirmationIndicators=["Smart Money Sweep Engine", "Synthetic DXY & Gold Confluence", "3-Candle FVG"],
            successConditions=["Liquidity Sweep Confirmed", "Macro DXY & Gold Aligned", "Spread <= 1.2 pips"],
            minimumConfidence=83,
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="Pairs AUD/USD SMC liquidity sweeps with Gold and DXY cross-asset confirmation.",
            dependencies=["Smart Money Engine", "Macro Cross-Asset Gate", "Candlestick Pattern Engine"],
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
            strategyVersion="1.0",
            parentStrategyId=None,
            createdBy="Falcon AI",
            readyForExecution=False,
            reviewNotes="Institutional trend-continuation and EMA pullback strategy for AUD/USD.",
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
            riskLevel=RiskLevel.HIGH,
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
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=5,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="2.0",
            parentStrategyId="strat-004",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="London Momentum engine replicated for XAU/USD without modifying GBP/USD strat-004.",
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
            riskLevel=RiskLevel.HIGH,
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
            preferredSessions=["London", "New York", "Asian"],
            avoidConditions=["Low Volume", "Spread Widening"],
            requiredConfirmations=["MACD crossover", "Volume spikes"],
            grade="A+",
            lastUsed=now,
            marketCompatibility=["Volatile", "High Liquidity"],
            estimatedHoldingTime="10-30 minutes",
            maxConsecutiveLosses=5,
            createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2026, 10, 31, tzinfo=timezone.utc),
            lastReviewedAt=now,
            strategyVersion="2.0",
            parentStrategyId="strat-004",
            createdBy="Falcon AI",
            readyForExecution=True,
            reviewNotes="London Momentum engine replicated for EUR/USD without modifying GBP/USD strat-004.",
            dependencies=["Market Session Engine", "Volatility Filter"],
            strategyScore=_empty_score(),
            latestValidation=_empty_validation()
        )

        strategies = [
            s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12,
            s13, s14, s15, s16, s17, s18, s19, s20,
        ]
        for strategy in strategies:
            default_active_ids = {"strat-004", "strat-007", "strat-012", "strat-013", "strat-016", "strat-017", "strat-019", "strat-020"}
            strategy.status = StrategyStatus.ACTIVE if strategy.id in default_active_ids else StrategyStatus.INCUBATION
            strategy.readyForExecution = (strategy.status == StrategyStatus.ACTIVE)
            if strategy.minimumRiskReward and strategy.minimumRiskReward > 1.5:
                strategy.minimumRiskReward = 1.5
            strategy.strategyScore.riskRating = strategy.riskLevel
        return strategies


strategy_engine = StrategyEngine()
