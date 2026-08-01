from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from app.schemas.performance_analytics import (
    PerformanceAnalyticsResponse,
    DailyPerformance,
    MonthlyPerformance,
    TradingCalendarDay,
    EquityPoint,
)

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date_str(days_ago: int) -> str:
    """Return an ISO date string N days before today."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ── Mock helpers ───────────────────────────────────────────────────────────────

def _build_daily_performance() -> list[DailyPerformance]:
    """Two weeks of Mon–Fri performance snapshots."""
    return [
        DailyPerformance(day="Monday",    totalTrades=4, wins=3, losses=1, breakEvens=0, winRate=0.75, profitLoss=185.50),
        DailyPerformance(day="Tuesday",   totalTrades=3, wins=2, losses=1, breakEvens=0, winRate=0.67, profitLoss=95.00),
        DailyPerformance(day="Wednesday", totalTrades=5, wins=3, losses=1, breakEvens=1, winRate=0.60, profitLoss=210.75),
        DailyPerformance(day="Thursday",  totalTrades=2, wins=1, losses=1, breakEvens=0, winRate=0.50, profitLoss=-30.00),
        DailyPerformance(day="Friday",    totalTrades=3, wins=2, losses=1, breakEvens=0, winRate=0.67, profitLoss=120.25),
    ]


def _build_monthly_performance() -> list[MonthlyPerformance]:
    """Last three calendar months."""
    return [
        MonthlyPerformance(month="May 2026",  totalTrades=38, wins=22, losses=12, winRate=0.579, profitLoss=820.50,  bestDay="Wednesday"),
        MonthlyPerformance(month="June 2026", totalTrades=45, wins=27, losses=14, winRate=0.600, profitLoss=1250.75, bestDay="Monday"),
        MonthlyPerformance(month="July 2026", totalTrades=17, wins=11, losses=5,  winRate=0.647, profitLoss=580.00,  bestDay="Tuesday"),
    ]


def _build_trading_calendar() -> list[TradingCalendarDay]:
    """Last 30 days — realistic WIN/LOSS/BREAKEVEN/NO_TRADE distribution."""
    pattern = [
        "WIN", "WIN", "LOSS", "WIN", "NO_TRADE",
        "NO_TRADE", "WIN", "WIN", "BREAKEVEN", "LOSS",
        "WIN", "NO_TRADE", "WIN", "WIN", "LOSS",
        "NO_TRADE", "NO_TRADE", "WIN", "WIN", "LOSS",
        "WIN", "WIN", "BREAKEVEN", "WIN", "NO_TRADE",
        "NO_TRADE", "WIN", "LOSS", "WIN", "WIN",
    ]
    return [
        TradingCalendarDay(date=_date_str(29 - i), result=pattern[i])
        for i in range(30)
    ]


def _build_equity_curve() -> list[EquityPoint]:
    """30 data points starting at $10 000, ending ~$12 650."""
    raw = [
        (10000.00, 0.00),
        (10145.00, 0.00),
        (10280.50, 0.00),
        (10190.00, 0.88),
        (10350.25, 0.00),
        (10210.00, 1.36),
        (10410.75, 0.00),
        (10560.00, 0.00),
        (10490.50, 0.66),
        (10680.00, 0.00),
        (10820.25, 0.00),
        (10750.00, 0.65),
        (10920.50, 0.00),
        (11080.00, 0.00),
        (10960.00, 1.08),
        (11120.75, 0.00),
        (11280.00, 0.00),
        (11180.50, 0.88),
        (11350.00, 0.00),
        (11520.25, 0.00),
        (11440.00, 0.70),
        (11610.50, 0.00),
        (11780.00, 0.00),
        (11920.75, 0.00),
        (11840.00, 0.68),
        (12010.50, 0.00),
        (12180.00, 0.00),
        (12090.50, 0.74),
        (12350.25, 0.00),
        (12650.00, 0.00),
    ]
    return [
        EquityPoint(date=_date_str(29 - i), equity=eq, drawdown=dd)
        for i, (eq, dd) in enumerate(raw)
    ]


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.get("/performance-analytics", response_model=PerformanceAnalyticsResponse)
def get_performance_analytics():
    """
    Returns comprehensive mock performance analytics for the authenticated trader.
    All figures are illustrative; a real implementation would compute these from
    the Trade Journal database records.
    """
    return PerformanceAnalyticsResponse(
        # ── Aggregate stats ──────────────────────────────────────
        avgTradesPerDay=3.4,
        avgTradesPerWeek=17.0,
        longestWinStreak=7,
        longestLossStreak=3,
        avgHoldingTimeMinutes=95,

        # ── Scoring ──────────────────────────────────────────────
        tradingScore=89,
        consistencyScore=94,

        # ── Equity ───────────────────────────────────────────────
        startingEquity=10000.00,
        currentEquity=12650.00,
        netProfit=2650.00,
        maxDrawdown=1.36,           # percentage

        # ── Today's snapshot ─────────────────────────────────────
        todaySignals=5,
        todayOpenTrades=2,
        todayClosedTrades=3,
        todayWins=2,
        todayLosses=1,
        todayUpcomingNews=3,

        # ── Lessons learned ──────────────────────────────────────
        commonLessons=[
            "Wait for candle confirmation before entry.",
            "Avoid trading immediately before high-impact news.",
            "Respect stop losses — do not move them against the trade.",
            "London session continues to produce the highest win rate.",
            "Reduce position size after two consecutive losses.",
        ],

        # ── Time-series ──────────────────────────────────────────
        dailyPerformance=_build_daily_performance(),
        monthlyPerformance=_build_monthly_performance(),
        tradingCalendar=_build_trading_calendar(),
        equityCurve=_build_equity_curve(),

        # ── Meta ─────────────────────────────────────────────────
        lastUpdated=_now(),
    )
