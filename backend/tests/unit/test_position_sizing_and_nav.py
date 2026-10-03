"""
Unit tests for Precision Position Sizing Service.
Verifies mathematically exact NAV-based unit and lot calculations across FX majors, JPY crosses, and Gold.
"""
from decimal import Decimal
import pytest

from app.core.services.position_sizing_service import PositionSizingService


@pytest.fixture
def sizing_service():
    return PositionSizingService(
        default_risk_pct=Decimal("0.01"),  # 1.0%
        max_risk_pct=Decimal("0.015"),     # 1.5%
        account_currency="USD",
    )


def test_eurusd_position_sizing(sizing_service):
    # NAV = $10,000, 1.0% risk = $100
    # Entry = 1.1000, SL = 1.0980 (20 pips = 0.0020)
    # Units = $100 / 0.0020 = 50,000 units = 0.50 lots
    nav = Decimal("10000.00")
    entry = Decimal("1.10000")
    sl = Decimal("1.09800")
    units, lots, cash_risk = sizing_service.calculate_units("EURUSD", entry, sl, nav)

    assert cash_risk == Decimal("100.00")
    assert units == 50000
    assert lots == Decimal("0.50")


def test_gold_xauusd_position_sizing(sizing_service):
    # NAV = $10,000, 1.0% risk = $100
    # Entry = 2000.00, SL = 1995.00 ($5.00 distance)
    # Units = $100 / 5.00 = 20 units (ounces) = 0.20 lots
    nav = Decimal("10000.00")
    entry = Decimal("2000.00")
    sl = Decimal("1995.00")
    units, lots, cash_risk = sizing_service.calculate_units("XAUUSD", entry, sl, nav)

    assert cash_risk == Decimal("100.00")
    assert units == 20
    assert lots == Decimal("0.20")


def test_jpy_cross_position_sizing(sizing_service):
    # NAV = $10,000, 1.0% risk = $100
    # GBPJPY: Entry = 190.00, SL = 189.75 (25 pips = 0.25 JPY)
    # USDJPY rate = 155.00
    # Loss per unit in USD = 0.25 / 155.00 = 0.0016129 USD
    # Units = $100 / 0.0016129 = 62,000 units = 0.62 lots
    nav = Decimal("10000.00")
    entry = Decimal("190.00")
    sl = Decimal("189.75")
    usdjpy = Decimal("155.00")
    units, lots, cash_risk = sizing_service.calculate_units(
        "GBPJPY", entry, sl, nav, usdjpy_rate=usdjpy
    )

    assert cash_risk == Decimal("100.00")
    assert units == 62000
    assert lots == Decimal("0.62")


def test_risk_clamp_enforces_safety_ceiling(sizing_service):
    # If user requests 5% risk, clamped to max_risk_pct (1.5%)
    nav = Decimal("10000.00")
    entry = Decimal("1.10000")
    sl = Decimal("1.09800")
    units, lots, cash_risk = sizing_service.calculate_units(
        "EURUSD", entry, sl, nav, risk_pct=Decimal("0.05")
    )

    assert cash_risk == Decimal("150.00")  # Exactly 1.5% of $10,000
    assert units == 75000
    assert lots == Decimal("0.75")
