"""
Falcon V10 Exit Model Research Evaluator.

Provides isolated, deterministic mathematical simulation of exit models:
- Model A: Baseline Fixed 1.5 ATR Target (full position exits at +1.5R or -1.0R).
- Model B: Full Exit at +1.0R (entire position closes at +1.0R).
- Model D1: Partial Bank 50% at +1.0R, remainder to +1.5R with Breakeven Stop.

Guarantees:
1. Purely functional / read-only: does NOT mutate trade journal or portfolio state.
2. Identical trade inputs: all models evaluated against identical scorable trades.
3. Realistic friction: models spread, slippage, and conservative same-candle SL precedence.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ExitModelResult:
    model_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: float
    net_r: float
    mean_r_per_trade: float
    profit_factor: float
    max_drawdown_r: float
    per_trade_r: List[float]


class ExitModelEvaluator:
    """Evaluates and compares exit models across trade sets or excursion trajectories."""

    @staticmethod
    def calc_max_drawdown(r_multiples: List[float]) -> float:
        cum_r = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in r_multiples:
            cum_r += r
            if cum_r > peak:
                peak = cum_r
            dd = peak - cum_r
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 3)

    @classmethod
    def evaluate_historical_scorable(
        cls,
        trades: List[Dict[str, Any]],
        friction_r: float = 0.0,
    ) -> Dict[str, ExitModelResult]:
        """
        Evaluate Model A, Model B, and Model D1 across canonical historical scorable trades.
        """
        models = ["A", "B", "D1"]
        results: Dict[str, ExitModelResult] = {}

        for m in models:
            r_series: List[float] = []
            wins = 0
            losses = 0
            be = 0
            gross_win = 0.0
            gross_loss = 0.0

            for t in trades:
                base_r = float(t.get(m, 0.0))
                # Apply optional friction stress
                adjusted_r = base_r - friction_r if friction_r > 0 else base_r
                r_series.append(round(adjusted_r, 4))

                if adjusted_r > 0.05:
                    wins += 1
                    gross_win += adjusted_r
                elif adjusted_r < -0.05:
                    losses += 1
                    gross_loss += abs(adjusted_r)
                else:
                    be += 1

            total_t = len(r_series)
            net_r = round(sum(r_series), 3)
            mean_r = round(net_r / total_t, 3) if total_t > 0 else 0.0
            win_rate = round((wins / total_t) * 100.0, 1) if total_t > 0 else 0.0
            pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
            max_dd = cls.calc_max_drawdown(r_series)

            model_labels = {
                "A": "Model A (Baseline 1.5 ATR Target)",
                "B": "Model B (Full Exit @ +1.0R)",
                "D1": "Model D1 (50% @ +1.0R, 50% @ +1.5R w/ BE)",
            }

            results[m] = ExitModelResult(
                model_name=model_labels.get(m, m),
                total_trades=total_t,
                winning_trades=wins,
                losing_trades=losses,
                breakeven_trades=be,
                win_rate_pct=win_rate,
                net_r=net_r,
                mean_r_per_trade=mean_r,
                profit_factor=pf,
                max_drawdown_r=max_dd,
                per_trade_r=r_series,
            )

        return results

    @classmethod
    def simulate_from_excursions(
        cls,
        max_favorable_r: float,
        max_adverse_r: float,
        same_candle_ambiguity: bool = False,
    ) -> Dict[str, float]:
        """
        Simulate outcomes of Model A, Model B, and Model D1 from given MFE and MAE in R.
        """
        # Conservative fail-closed rule: if same candle hits SL and TP, SL takes precedence
        if same_candle_ambiguity:
            return {"A": -1.0, "B": -1.0, "D1": -1.0}

        # Model A: target 1.5R, SL -1.0R
        if max_adverse_r >= 1.0:
            res_a = -1.0
        elif max_favorable_r >= 1.5:
            res_a = 1.5
        else:
            # Trailing or floating MTM at close
            res_a = max(0.0, max_favorable_r) - max(0.0, max_adverse_r)

        # Model B: target 1.0R, SL -1.0R
        if max_adverse_r >= 1.0:
            res_b = -1.0
        elif max_favorable_r >= 1.0:
            res_b = 1.0
        else:
            res_b = max(0.0, max_favorable_r) - max(0.0, max_adverse_r)

        # Model D1: 50% at 1.0R, remainder to 1.5R with BE
        if max_adverse_r >= 1.0:
            res_d1 = -1.0
        elif max_favorable_r >= 1.5:
            res_d1 = 0.5 * 1.0 + 0.5 * 1.5  # +1.25R
        elif max_favorable_r >= 1.0:
            # First half banked, second half stopped at BE (0.0R) or floating
            res_d1 = 0.5 * 1.0 + 0.5 * 0.0  # +0.50R
        else:
            res_d1 = max(0.0, max_favorable_r) - max(0.0, max_adverse_r)

        return {"A": round(res_a, 3), "B": round(res_b, 3), "D1": round(res_d1, 3)}
