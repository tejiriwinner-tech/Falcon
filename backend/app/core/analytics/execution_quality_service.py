"""
Falcon V10 Phase 5C: Execution Quality & Excursion Measurement Service.

Provides single authoritative measurement for:
- Maximum Favorable Excursion (MFE)
- Maximum Adverse Excursion (MAE)
- Direction-aware excursion formulas (BUY vs SELL)
- R-denominated excursion conversions using persisted authoritative initial_monetary_risk
  and Capital Guardian contract sizing
- Post-fill peak/trough price tracking with strict observation timestamp gating
- Execution quality metrics (signal-to-fill duration, entry slippage, spread/ATR at entry)
- Purely descriptive, non-ranking aggregate reporting
- Zero-lookahead as-of historical analysis
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import List, Optional, Tuple

from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.schemas.execution_quality import (
    ExecutionQualitySummary,
    TradeExecutionQuality,
)
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.execution_quality_service")


class ExecutionQualityService:
    """
    Authoritative measurement engine for signal excursions and execution quality.
    Strictly read-only with respect to broker execution: Falcon is a decision-support
    tool and does not place, modify, close, or cancel broker orders.
    """

    def __init__(
        self,
        journal_repo: Optional[TradeJournalRepository] = None,
        guardian_service: Optional[CapitalGuardianService] = None,
    ):
        self._journal_repo = journal_repo or trade_journal_repository
        self._guardian = guardian_service or capital_guardian_service

    # ==========================================================================
    # 1. Direction-Aware Price Excursion Calculations
    # ==========================================================================

    @staticmethod
    def calculate_directional_price_excursion(
        direction: str,
        fill_price: Optional[float],
        peak_price: Optional[float],
        trough_price: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate direction-aware MFE and MAE in price points.

        Rules:
        - For BUY:
            MFE = peak_price - fill_price (highest post-fill price minus fill price)
            MAE = fill_price - trough_price (fill price minus lowest post-fill price)
        - For SELL:
            MFE = fill_price - trough_price (fill price minus lowest post-fill price)
            MAE = peak_price - fill_price (highest post-fill price minus fill price)
        - If fill_price, peak_price, or trough_price is None -> returns (None, None).
        - Excursions are strictly non-negative: max(0.0, ...).
        """
        if fill_price is None or peak_price is None or trough_price is None:
            return None, None

        dir_clean = str(direction).strip().upper()
        if dir_clean == "BUY":
            mfe = max(0.0, float(peak_price) - float(fill_price))
            mae = max(0.0, float(fill_price) - float(trough_price))
            return round(mfe, 5), round(mae, 5)
        elif dir_clean == "SELL":
            mfe = max(0.0, float(fill_price) - float(trough_price))
            mae = max(0.0, float(peak_price) - float(fill_price))
            return round(mfe, 5), round(mae, 5)
        else:
            return None, None

    # ==========================================================================
    # 2. R-Denominated Excursion Conversion
    # ==========================================================================

    def convert_price_excursion_to_r(
        self,
        symbol: str,
        mfe_price: Optional[float],
        mae_price: Optional[float],
        initial_monetary_risk: Optional[Decimal | float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Convert raw price excursions to R-multiples using the authoritative
        initial monetary risk established at authorization and Capital Guardian's
        contract sizing rules.

        Strict Safety:
        - If initial_monetary_risk is None, 0, or negative -> returns (None, None).
        - If instrument is unsupported or not USD quoted -> fails closed (None, None).
        - Never coerces None to 0.0.
        """
        if mfe_price is None or mae_price is None or initial_monetary_risk is None:
            return None, None

        try:
            risk_dec = Decimal(str(initial_monetary_risk))
            if risk_dec <= Decimal("0.00"):
                return None, None
        except Exception:
            return None, None

        # Resolve authoritative instrument units (based on standard Falcon 0.01 micro lot)
        sym_clean = str(symbol).strip().upper().replace("/", "").replace("_", "")
        inst = self._guardian._registry.get_instrument(sym_clean)
        if not inst or inst.currency != "USD":
            return None, None

        # Established contract sizes for supported Falcon USD instruments
        if "XAU" in sym_clean or "GOLD" in sym_clean:
            units = Decimal("1.0")  # 100 oz/lot * 0.01 lot = 1 oz
        elif sym_clean in ("EURUSD", "GBPUSD", "AUDUSD"):
            units = Decimal("1000.0")  # 100,000 units/lot * 0.01 lot = 1,000 units
        else:
            return None, None

        try:
            monetary_mfe = Decimal(str(mfe_price)) * units
            monetary_mae = Decimal(str(mae_price)) * units
            mfe_r = float(round(monetary_mfe / risk_dec, 2))
            mae_r = float(round(monetary_mae / risk_dec, 2))
            return mfe_r, mae_r
        except Exception:
            return None, None

    # ==========================================================================
    # 3. Peak / Trough Tracking Lifecycle
    # ==========================================================================

    def update_open_trade_excursion(
        self,
        trade: TradeJournalItem,
        observed_price: float,
        observation_time: datetime,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Update peak/trough for an OPEN or FILLED trade using a new market observation.

        Enforces:
        - PENDING trades do not track MFE/MAE.
        - EXPIRED / INVALIDATED trades do not track MFE/MAE.
        - Pre-fill observations (observation_time < fillTime) are strictly excluded.
        - Post-closure observations (observation_time > closeDate) are strictly excluded.
        - Direction-aware update of peak_price and trough_price.
        - Recomputation of mfe_r and mae_r when authoritative initial_monetary_risk is present.
        Returns: (peak_price, trough_price, mfe_r, mae_r)
        """
        status = (trade.status or "").upper()
        if status not in ("OPEN", "FILLED") or trade.fillPrice is None:
            return trade.peakPrice, trade.troughPrice, trade.mfeR, trade.maeR

        # Check post-fill timestamp boundary
        if trade.fillTime is not None and observation_time < trade.fillTime:
            return trade.peakPrice, trade.troughPrice, trade.mfeR, trade.maeR

        # Check close-time boundary
        if trade.closeDate is not None and observation_time > trade.closeDate:
            return trade.peakPrice, trade.troughPrice, trade.mfeR, trade.maeR

        fill_price = float(trade.fillPrice)
        current_peak = float(trade.peakPrice) if trade.peakPrice is not None else fill_price
        current_trough = float(trade.troughPrice) if trade.troughPrice is not None else fill_price

        new_peak = max(current_peak, float(observed_price))
        new_trough = min(current_trough, float(observed_price))

        mfe_price, mae_price = self.calculate_directional_price_excursion(
            direction=trade.direction,
            fill_price=fill_price,
            peak_price=new_peak,
            trough_price=new_trough,
        )

        mfe_r, mae_r = self.convert_price_excursion_to_r(
            symbol=trade.symbol,
            mfe_price=mfe_price,
            mae_price=mae_price,
            initial_monetary_risk=trade.initialMonetaryRisk,
        )

        return new_peak, new_trough, mfe_r, mae_r

    def finalize_closed_trade_excursion(
        self,
        trade: TradeJournalItem,
        exit_price: Optional[float],
        close_time: Optional[datetime] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Finalize peak_price, trough_price, mfe_r, and mae_r at trade closure.
        Incorporates exit_price as the final observation.
        """
        if trade.fillPrice is None:
            # Historical or untriggered trade without authoritative fill: preserve without fabrication
            return trade.peakPrice, trade.troughPrice, trade.mfeR, trade.maeR

        fill_price = float(trade.fillPrice)
        current_peak = float(trade.peakPrice) if trade.peakPrice is not None else fill_price
        current_trough = float(trade.troughPrice) if trade.troughPrice is not None else fill_price

        if exit_price is not None:
            final_peak = max(current_peak, float(exit_price))
            final_trough = min(current_trough, float(exit_price))
        else:
            final_peak = current_peak
            final_trough = current_trough

        mfe_price, mae_price = self.calculate_directional_price_excursion(
            direction=trade.direction,
            fill_price=fill_price,
            peak_price=final_peak,
            trough_price=final_trough,
        )

        mfe_r, mae_r = self.convert_price_excursion_to_r(
            symbol=trade.symbol,
            mfe_price=mfe_price,
            mae_price=mae_price,
            initial_monetary_risk=trade.initialMonetaryRisk,
        )

        return final_peak, final_trough, mfe_r, mae_r

    # ==========================================================================
    # 4. Descriptive Execution Quality Measurement
    # ==========================================================================

    def calculate_trade_execution_quality(
        self,
        trade: TradeJournalItem,
    ) -> TradeExecutionQuality:
        """Calculate descriptive execution and excursion metrics for a single trade."""
        signal_to_fill: Optional[float] = None
        if trade.fillTime is not None and trade.tradeDate is not None:
            diff = (trade.fillTime - trade.tradeDate).total_seconds()
            if diff >= 0:
                signal_to_fill = round(diff, 2)

        # Slippage calculation: only when both entryPrice and actual fillPrice are authoritative
        entry_slippage_price: Optional[float] = None
        entry_slippage_pips: Optional[float] = None
        if trade.fillPrice is not None and trade.entryPrice is not None and trade.entryPrice > 0:
            dir_clean = (trade.direction or "").upper()
            if dir_clean == "BUY":
                # For BUY: positive means filled higher than requested (adverse), negative is price improvement
                entry_slippage_price = round(trade.fillPrice - trade.entryPrice, 5)
            elif dir_clean == "SELL":
                # For SELL: positive means filled lower than requested (adverse), negative is price improvement
                entry_slippage_price = round(trade.entryPrice - trade.fillPrice, 5)

            if entry_slippage_price is not None:
                sym_clean = (trade.symbol or "").upper()
                if "XAU" in sym_clean or "GOLD" in sym_clean:
                    entry_slippage_pips = round(entry_slippage_price / 0.1, 2)
                elif "JPY" in sym_clean:
                    entry_slippage_pips = round(entry_slippage_price / 0.01, 2)
                else:
                    entry_slippage_pips = round(entry_slippage_price / 0.0001, 2)

        # Excursions
        mfe_price, mae_price = self.calculate_directional_price_excursion(
            direction=trade.direction,
            fill_price=trade.fillPrice,
            peak_price=trade.peakPrice,
            trough_price=trade.troughPrice,
        )

        has_auth_fill = trade.fillTime is not None and trade.fillPrice is not None
        has_auth_risk = (
            trade.initialMonetaryRisk is not None and float(trade.initialMonetaryRisk) > 0
        )

        return TradeExecutionQuality(
            tradeId=trade.id,
            signalId=trade.signalId,
            symbol=trade.symbol,
            direction=trade.direction,
            status=trade.status,
            result=trade.result,
            tradeDate=trade.tradeDate,
            fillTime=trade.fillTime,
            closeDate=trade.closeDate,
            signalToFillSeconds=signal_to_fill,
            entryPrice=trade.entryPrice,
            fillPrice=trade.fillPrice,
            entrySlippagePrice=entry_slippage_price,
            entrySlippagePips=entry_slippage_pips,
            spreadAtEntry=trade.spreadAtEntry,
            atrAtEntry=trade.atrAtEntry,
            peakPrice=trade.peakPrice,
            troughPrice=trade.troughPrice,
            mfePrice=mfe_price,
            maePrice=mae_price,
            mfeR=trade.mfeR,
            maeR=trade.maeR,
            realizedRMultiple=trade.realizedRMultiple,
            hasAuthoritativeFill=has_auth_fill,
            hasAuthoritativeRisk=has_auth_risk,
        )

    # ==========================================================================
    # 5. Aggregate Execution Quality Summary (Descriptive, Non-Ranking)
    # ==========================================================================

    def get_execution_quality_summary(
        self,
        as_of: Optional[datetime] = None,
    ) -> ExecutionQualitySummary:
        """
        Generate aggregate execution quality summary with strict lookahead safety.

        Rules:
        - If as_of is provided: only includes trades created <= as_of.
          For closed trades, only includes if closeDate <= as_of.
        - Excludes historical rows with NULL excursions from excursion averages without fabrication.
        - Descriptive facts only: zero arbitrary scoring or ranking.
        """
        all_trades = self._journal_repo.list_trades()

        # As-of filtering
        filtered_trades: List[TradeJournalItem] = []
        for t in all_trades:
            if as_of is not None:
                if t.tradeDate > as_of:
                    continue
                if t.closeDate is not None and t.closeDate > as_of:
                    continue
            filtered_trades.append(t)

        trade_qualities = [
            self.calculate_trade_execution_quality(t) for t in filtered_trades
        ]

        total_evaluated = len(trade_qualities)
        filled_trades = [t for t in trade_qualities if t.hasAuthoritativeFill]
        filled_count = len(filled_trades)

        # Signal-to-fill timing
        stf_values = [
            t.signalToFillSeconds
            for t in trade_qualities
            if t.signalToFillSeconds is not None
        ]
        avg_stf = round(sum(stf_values) / len(stf_values), 2) if stf_values else None

        # Spread at entry
        spread_values = [
            t.spreadAtEntry for t in trade_qualities if t.spreadAtEntry is not None
        ]
        avg_spread = (
            round(sum(spread_values) / len(spread_values), 5) if spread_values else None
        )

        # ATR at entry
        atr_values = [
            t.atrAtEntry for t in trade_qualities if t.atrAtEntry is not None
        ]
        avg_atr = (
            round(sum(atr_values) / len(atr_values), 5) if atr_values else None
        )

        # Entry slippage
        slippage_values = [
            t.entrySlippagePips
            for t in trade_qualities
            if t.entrySlippagePips is not None
        ]
        avg_slippage = (
            round(sum(slippage_values) / len(slippage_values), 2)
            if slippage_values
            else None
        )

        # MFE / MAE R
        mfe_r_values = [t.mfeR for t in trade_qualities if t.mfeR is not None]
        avg_mfe_r = (
            round(sum(mfe_r_values) / len(mfe_r_values), 2) if mfe_r_values else None
        )

        mae_r_values = [t.maeR for t in trade_qualities if t.maeR is not None]
        avg_mae_r = (
            round(sum(mae_r_values) / len(mae_r_values), 2) if mae_r_values else None
        )

        historical_excluded = len(
            [t for t in trade_qualities if t.mfeR is None and t.peakPrice is None]
        )

        return ExecutionQualitySummary(
            totalTradesEvaluated=total_evaluated,
            filledTradesCount=filled_count,
            averageSignalToFillSeconds=avg_stf,
            tradesWithSignalToFill=len(stf_values),
            averageSpreadAtEntry=avg_spread,
            tradesWithSpreadAtEntry=len(spread_values),
            averageAtrAtEntry=avg_atr,
            tradesWithAtrAtEntry=len(atr_values),
            averageEntrySlippagePips=avg_slippage,
            tradesWithEntrySlippage=len(slippage_values),
            averageMfeR=avg_mfe_r,
            averageMaeR=avg_mae_r,
            tradesWithMfeMaeR=len(mfe_r_values),
            historicalTradesExcludedCount=historical_excluded,
            asOfTimestamp=as_of,
            generatedAt=datetime.now(timezone.utc),
        )


execution_quality_service = ExecutionQualityService()
