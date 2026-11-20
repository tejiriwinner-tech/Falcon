"""
Centralized configuration for Falcon's Apex Institutional Velocity Scalping Suite:
- strat-024: XAU/USD London-NY Velocity Scalp (Gold — isolated & untouched)
- strat-025: GBP/USD Cable London-NY Velocity Scalp
- strat-026: GBP/JPY Dragon Anti-Trap Velocity Scalp
- strat-027: USD/JPY Ninja Yield-Lock Velocity Scalp
- strat-028: AUD/USD Aussie Gold-Locked Velocity Scalp

Single source of truth consumed by strategy_engine.py, signal_generation_engine.py,
signal_service.py, and signal_outcome_resolver.py so killzones, spread caps, stop bands,
risk-reward targets, and +0.65R fast breakeven scale-out rules never drift.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, FrozenSet, Tuple


@dataclass(frozen=True)
class ApexScalpSpec:
    strategy_id: str
    symbol: str
    canonical_symbol: str
    display_name: str
    killzones_utc: Tuple[Tuple[int, int], ...]  # Inclusive (start_minute, end_minute) in UTC
    killzone_label: str
    max_spread_pips: float
    min_sl_dist: float  # In price units
    max_sl_dist: float  # In price units
    rr_target: float
    be_r_mult: float
    macro_shield: str  # "EURUSD_SYNC", "YEN_CROSS_SYNC", "US_YIELD_DXY_LOCK", "GOLD_DXY_LOCK"


# All velocity scalpers sharing +0.65R fast breakeven & 50% scale-out discipline
VELOCITY_SCALP_STRATEGY_IDS: FrozenSet[str] = frozenset({
    "strat-024",
    "strat-025",
    "strat-026",
    "strat-027",
    "strat-028",
    "strat-029",
})

# The 5 FX Apex Institutional Velocity Scalpers (strat-024 stays on its dedicated Gold path)
APEX_FX_SCALP_IDS: FrozenSet[str] = frozenset({
    "strat-025",
    "strat-026",
    "strat-027",
    "strat-028",
    "strat-029",
})

APEX_FX_SCALP_CONFIG: Dict[str, ApexScalpSpec] = {
    "strat-025": ApexScalpSpec(
        strategy_id="strat-025",
        symbol="GBP/USD",
        canonical_symbol="GBPUSD",
        display_name="GBP/USD Cable London-NY Velocity Scalp",
        # 07:00-11:00 UTC (London Open/Morning) & 12:30-15:30 UTC (NY Open/Overlap)
        killzones_utc=((420, 660), (750, 930)),
        killzone_label="07:00-11:00 & 12:30-15:30 UTC",
        max_spread_pips=1.4,
        min_sl_dist=0.0008,  # 8 pips
        max_sl_dist=0.0018,  # 18 pips
        rr_target=1.25,
        be_r_mult=0.65,
        macro_shield="EURUSD_SYNC",
    ),
    "strat-026": ApexScalpSpec(
        strategy_id="strat-026",
        symbol="GBP/JPY",
        canonical_symbol="GBPJPY",
        display_name="GBP/JPY Dragon Anti-Trap Velocity Retest",
        # 00:00-03:30 UTC (Tokyo Fix) & 07:00-11:00 UTC (London Open) & 12:30-15:00 UTC (Overlap)
        killzones_utc=((0, 210), (420, 660), (750, 900)),
        killzone_label="00:00-03:30, 07:00-11:00 & 12:30-15:00 UTC",
        max_spread_pips=3.5,  # Upgraded from 2.4 to 3.5 pips for Dragon intraday volatility
        min_sl_dist=0.14,  # 14 pips
        max_sl_dist=0.28,  # 28 pips
        rr_target=1.25,
        be_r_mult=0.65,
        macro_shield="YEN_CROSS_SYNC",
    ),
    "strat-027": ApexScalpSpec(
        strategy_id="strat-027",
        symbol="USD/JPY",
        canonical_symbol="USDJPY",
        display_name="USD/JPY Ninja Yield-Lock Velocity Scalp",
        # 00:00-03:30 UTC (Tokyo Open/Gotobi Fix) & 12:30-16:00 UTC (NY Open & US Bond Yield Window)
        killzones_utc=((0, 210), (750, 960)),
        killzone_label="00:00-03:30 & 12:30-16:00 UTC",
        max_spread_pips=1.3,
        min_sl_dist=0.10,  # 10 pips
        max_sl_dist=0.20,  # 20 pips
        rr_target=1.25,
        be_r_mult=0.65,
        macro_shield="US_YIELD_DXY_LOCK",
    ),
    "strat-028": ApexScalpSpec(
        strategy_id="strat-028",
        symbol="AUD/USD",
        canonical_symbol="AUDUSD",
        display_name="AUD/USD Aussie Gold-Locked Velocity Scalp",
        # 00:00-04:00 UTC (Sydney/Tokyo Peak) & 07:00-11:00 UTC (London Open) & 12:30-15:00 UTC (NY Open)
        killzones_utc=((0, 240), (420, 660), (750, 900)),
        killzone_label="00:00-04:00, 07:00-11:00 & 12:30-15:00 UTC",
        max_spread_pips=1.2,
        min_sl_dist=0.0007,  # 7 pips
        max_sl_dist=0.0015,  # 15 pips
        rr_target=1.25,
        be_r_mult=0.65,
        macro_shield="GOLD_DXY_LOCK",
    ),
    "strat-029": ApexScalpSpec(
        strategy_id="strat-029",
        symbol="EUR/USD",
        canonical_symbol="EURUSD",
        display_name="EUR/USD Fiber Frankfurt-NY Velocity Scalp",
        # 06:45-10:30 UTC (Frankfurt/London Open Judas Swing & Repricing) & 12:30-15:30 UTC (NY Open / Overlap Peak)
        killzones_utc=((405, 630), (750, 930)),
        killzone_label="06:45-10:30 & 12:30-15:30 UTC",
        max_spread_pips=1.0,
        min_sl_dist=0.0007,  # 7 pips
        max_sl_dist=0.0014,  # 14 pips
        rr_target=1.25,
        be_r_mult=0.65,
        macro_shield="FIBER_SMT_USD_LOCK",
    ),
}


def get_apex_fx_spec(strategy_id: str) -> ApexScalpSpec | None:
    return APEX_FX_SCALP_CONFIG.get((strategy_id or "").strip().lower())


def is_in_apex_killzone(strategy_id: str, utc_dt: datetime | None = None) -> Tuple[bool, str]:
    """
    Returns (in_killzone, human_label) for any Apex FX Velocity Scalp strategy.
    If strategy_id is not in APEX_FX_SCALP_CONFIG, returns (True, "").
    """
    spec = get_apex_fx_spec(strategy_id)
    if spec is None:
        return True, ""
    now_utc = (
        utc_dt.astimezone(timezone.utc)
        if (utc_dt is not None and getattr(utc_dt, "tzinfo", None) is not None)
        else (utc_dt.replace(tzinfo=timezone.utc) if utc_dt is not None else datetime.now(timezone.utc))
    )
    utc_mins = now_utc.hour * 60 + now_utc.minute
    in_kz = any(start <= utc_mins <= end for start, end in spec.killzones_utc)
    return in_kz, spec.killzone_label
