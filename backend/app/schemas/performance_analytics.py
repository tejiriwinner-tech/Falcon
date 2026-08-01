from typing import List
from datetime import datetime
from pydantic import BaseModel


class DailyPerformance(BaseModel):
    day: str
    totalTrades: int
    wins: int
    losses: int
    breakEvens: int
    winRate: float
    profitLoss: float


class MonthlyPerformance(BaseModel):
    month: str
    totalTrades: int
    wins: int
    losses: int
    winRate: float
    profitLoss: float
    bestDay: str


class TradingCalendarDay(BaseModel):
    date: str           # ISO date string, e.g. "2026-06-01"
    result: str         # WIN | LOSS | BREAKEVEN | NO_TRADE


class EquityPoint(BaseModel):
    date: str           # ISO date string
    equity: float
    drawdown: float


class PerformanceAnalyticsResponse(BaseModel):
    # ── Aggregate stats ────────────────────────────────────────────
    avgTradesPerDay: float
    avgTradesPerWeek: float
    longestWinStreak: int
    longestLossStreak: int
    avgHoldingTimeMinutes: int

    # ── Scoring ───────────────────────────────────────────────────
    tradingScore: int           # 0-100
    consistencyScore: int       # 0-100

    # ── Equity ────────────────────────────────────────────────────
    startingEquity: float
    currentEquity: float
    netProfit: float
    maxDrawdown: float

    # ── Today's snapshot ──────────────────────────────────────────
    todaySignals: int
    todayOpenTrades: int
    todayClosedTrades: int
    todayWins: int
    todayLosses: int
    todayUpcomingNews: int

    # ── Lessons ───────────────────────────────────────────────────
    commonLessons: List[str]

    # ── Time-series data ──────────────────────────────────────────
    dailyPerformance: List[DailyPerformance]
    monthlyPerformance: List[MonthlyPerformance]
    tradingCalendar: List[TradingCalendarDay]
    equityCurve: List[EquityPoint]

    # ── Meta ──────────────────────────────────────────────────────
    lastUpdated: datetime
