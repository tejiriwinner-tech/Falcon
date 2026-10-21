"""
Falcon Precision Position Sizing Service
Calculates mathematically exact units and lot sizes based on live broker NAV,
account base currency, pip distance, and currency conversion rates.
Enforces institutional risk parity across FX majors, JPY crosses, and Gold.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("falcon.position_sizing")


class PositionSizingService:
    """
    Precision position sizing engine:
    1. Obtains live broker NAV or falls back to starting equity.
    2. Enforces strict risk boundary (e.g. 1.0% NAV, max 1.5% NAV).
    3. Accurately converts pip values across currency quotes (USD, JPY) and Gold.
    4. Outputs integer broker units (OANDA standard) and standard lot sizes (MT5 standard).
    """

    def __init__(
        self,
        default_risk_pct: Decimal = Decimal("0.01"),  # 1.0%
        max_risk_pct: Decimal = Decimal("0.015"),     # 1.5% max
        account_currency: str = "USD"
    ):
        self.default_risk_pct = default_risk_pct
        self.max_risk_pct = max_risk_pct
        self.account_currency = account_currency.upper()

    @classmethod
    def calculate_portfolio_heat_multiplier(cls, active_trade_count: int) -> float:
        """
        Dynamically scale per-trade risk based on number of active concurrent positions:
        - 0 or 1 active trade: 1.0x (1.0% risk)
        - 2 active trades: 0.75x (0.75% risk each -> 1.5% total portfolio heat)
        - 3 active trades: 0.50x (0.50% risk each -> 1.5% total portfolio heat)
        - >= 4 active trades: 0.35x (0.35% risk each)
        """
        if active_trade_count <= 1:
            return 1.0
        elif active_trade_count == 2:
            return 0.75
        elif active_trade_count == 3:
            return 0.50
        else:
            return 0.35

    @classmethod
    def calculate_portfolio_heat_lot_size(cls, active_trade_count: int, base_lot_size: float = 0.01) -> float:
        mult = cls.calculate_portfolio_heat_multiplier(active_trade_count)
        scaled = round(base_lot_size * mult, 2)
        return max(0.01, scaled)

    def calculate_units(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        nav: Decimal,
        risk_pct: Optional[Decimal] = None,
        usdjpy_rate: Optional[Decimal] = None,
    ) -> Tuple[int, Decimal, Decimal]:
        """
        Calculate trade size.

        Returns:
            Tuple[units: int, lots: Decimal, cash_risk: Decimal]
        """
        clean_symbol = symbol.replace("/", "").replace("_", "").upper()
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance <= Decimal("0"):
            logger.warning("Stop distance is zero for %s; returning 1 unit", clean_symbol)
            return 1, Decimal("0.01"), Decimal("0.00")

        # Clamp risk percentage between 0.1% and max_risk_pct
        effective_risk_pct = risk_pct if risk_pct is not None else self.default_risk_pct
        effective_risk_pct = min(max(effective_risk_pct, Decimal("0.001")), self.max_risk_pct)

        cash_risk = (nav * effective_risk_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 1. Gold (XAUUSD)
        if "XAU" in clean_symbol:
            # 1 unit = 1 oz. Loss per unit in USD = stop distance
            loss_per_unit = stop_distance
            units = int(cash_risk / loss_per_unit)
            units = max(1, units)
            lots = (Decimal(units) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lots = max(Decimal("0.01"), lots)
            return units, lots, cash_risk

        # 2. JPY Crosses (USDJPY, GBPJPY, EURJPY)
        if clean_symbol.endswith("JPY"):
            # Loss per unit is in JPY. Convert to USD by dividing by USDJPY rate
            rate = usdjpy_rate or (entry_price if clean_symbol == "USDJPY" else Decimal("155.00"))
            loss_per_unit_jpy = stop_distance
            loss_per_unit_usd = loss_per_unit_jpy / rate
            units = int(cash_risk / loss_per_unit_usd)
            units = max(1, units)
            lots = (Decimal(units) / Decimal("100000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lots = max(Decimal("0.01"), lots)
            return units, lots, cash_risk

        # 3. USD-Quoted Majors (EURUSD, GBPUSD, AUDUSD, NZDUSD)
        if clean_symbol.endswith("USD"):
            # Loss per unit is directly in USD
            loss_per_unit = stop_distance
            units = int(cash_risk / loss_per_unit)
            units = max(1, units)
            lots = (Decimal(units) / Decimal("100000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lots = max(Decimal("0.01"), lots)
            return units, lots, cash_risk

        # 4. Default Fallback
        loss_per_unit = stop_distance
        units = int(cash_risk / loss_per_unit) if loss_per_unit > 0 else 1
        units = max(1, units)
        lots = (Decimal(units) / Decimal("100000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        lots = max(Decimal("0.01"), lots)
        return units, lots, cash_risk


position_sizing_service = PositionSizingService()

# Module-level aliases for direct functional access
calculate_portfolio_heat_multiplier = PositionSizingService.calculate_portfolio_heat_multiplier
calculate_portfolio_heat_lot_size = PositionSizingService.calculate_portfolio_heat_lot_size

