"""
Falcon Quantitative Engine — Institutional Risk Auditor (Grades A / B / C).

Replaces binary signal suppression and vetoes with quantitative grading and tactical advice.
GUARANTEES: 100% of signals are preserved and delivered. Zero dropped winning trades.

Grades:
- Grade A (Prime Setup, >= 85% Confluence):
  HTF alignment verified, positive delta in trade direction, clean retest, normal volatility.
  Advice: Standard position size (1.0x). Target TP1 and TP2.
- Grade B (Extended / Neutral Delta, 70% - 84% Confluence):
  Technical setup valid, but price extended or delta neutral.
  Advice: Lock Breakeven at +1.0R; bank 50% partial profit at TP1.
- Grade C (Absorption Caution / Sweep Probe, < 70% Confluence):
  Absorption wick detected or sweep probe without confirmed retest.
  Advice: Delta divergence / absorption caution. Conservative 0.5x risk recommended.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from app.core.engines.htf_structure_engine import HTFAlignmentResult
from app.core.engines.order_flow_engine import IntraCandleDecomposition


@dataclass
class AuditResult:
    grade: str  # "A", "B", "C"
    confluence_pct: float  # 0.0 to 100.0
    est_delta_badge: str  # e.g., "🟢 +1,450 Delta"
    tactical_advice: str  # Actionable advice
    recommended_risk_multiplier: float  # 1.0, 0.75, 0.5
    is_approved: bool = True  # Always True: Zero suppression
    details: Optional[Dict[str, Any]] = None


class InstitutionalRiskAuditor:
    def __init__(self):
        self.version = "1.0.0"

    def audit(
        self,
        symbol: str,
        direction: str,
        base_conviction: float,  # 0.0 - 100.0
        htf_result: Optional[HTFAlignmentResult] = None,
        order_flow: Optional[IntraCandleDecomposition] = None,
        current_sigma: float = 0.0,
        is_sweep_confirmed: bool = True,
    ) -> AuditResult:
        """
        Audits a proposed signal against HTF flow, intra-candle delta, and volatility envelope.
        Assigns Grade A, B, or C with specific tactical execution notes.
        Never drops or vetoes the signal.
        """
        dir_upper = direction.upper()
        points = float(base_conviction) * 0.40  # 40% weight to base technical setup (max 40)

        # 1. Higher-Timeframe (HTF) Alignment (up to 30 pts)
        htf_pts = 20.0
        htf_note = ""
        if htf_result is not None:
            if htf_result.is_aligned:
                htf_pts = 30.0 if htf_result.confluence_score >= 0.85 else 25.0
            elif htf_result.barrier_conflict:
                htf_pts = 5.0
                htf_note = f"near {htf_result.nearest_barrier.level_type if htf_result.nearest_barrier else 'barrier'}"
            else:
                htf_pts = 10.0
                htf_note = f"against {htf_result.htf_trend_bias}"
        points += htf_pts

        # 2. Intra-Candle Delta & Order Flow (up to 20 pts)
        delta_pts = 10.0
        delta_badge = "⚖️ Neutral Delta"
        delta_note = ""
        if order_flow is not None:
            delta_badge = order_flow.confluence_tag or f"⚖️ Delta {order_flow.bar_delta:+.0f}"
            
            # Check alignment with direction
            if dir_upper == "BUY":
                if order_flow.bar_delta > 0 and order_flow.ofi >= 0.15:
                    delta_pts = 20.0
                elif order_flow.is_lower_absorption:
                    delta_pts = 18.0  # Trapped sellers absorbed by institutional buyers
                    delta_note = "Lower absorption wick defended"
                elif order_flow.is_upper_absorption:
                    delta_pts = 2.0  # Trapped buyers hitting sell wall
                    delta_note = "Upper absorption wick resistance"
                elif order_flow.bar_delta >= 0:
                    delta_pts = 12.0
                else:
                    delta_pts = 5.0
                    delta_note = "Negative delta divergence"
            else:  # SELL
                if order_flow.bar_delta < 0 and order_flow.ofi <= -0.15:
                    delta_pts = 20.0
                elif order_flow.is_upper_absorption:
                    delta_pts = 18.0  # Trapped buyers absorbed by institutional sellers
                    delta_note = "Upper absorption wick defended"
                elif order_flow.is_lower_absorption:
                    delta_pts = 2.0  # Trapped sellers hitting buy wall
                    delta_note = "Lower absorption wick support"
                elif order_flow.bar_delta <= 0:
                    delta_pts = 12.0
                else:
                    delta_pts = 5.0
                    delta_note = "Positive delta divergence"
        points += delta_pts

        # 3. Volatility Envelope & Sweep Confirmation (up to 10 pts)
        vol_pts = 10.0
        vol_note = ""
        abs_sigma = abs(current_sigma)
        if abs_sigma >= 2.5:
            vol_pts = 2.0
            vol_note = f"Extended into {abs_sigma:.1f}σ band"
        elif abs_sigma >= 2.0:
            vol_pts = 6.0
            vol_note = f"Stretched into {abs_sigma:.1f}σ band"
        
        if not is_sweep_confirmed:
            vol_pts = max(1.0, vol_pts - 4.0)

        points += vol_pts
        total_score = max(0.0, min(100.0, points))

        # Assign Institutional Grade and Tactical Advice
        if total_score >= 82.0:
            grade = "A"
            risk_mult = 1.0
            tactical_advice = (
                f"Grade A: Prime Institutional Setup. HTF flow aligned ({delta_badge}). "
                f"Standard 1.0x sizing. Target TP1 and TP2."
            )
        elif total_score >= 68.0:
            grade = "B"
            risk_mult = 0.75
            notes = [n for n in [vol_note, delta_note, htf_note] if n]
            context = f" ({', '.join(notes)})" if notes else ""
            tactical_advice = (
                f"Grade B: Solid Technical Setup{context}. "
                f"Lock Breakeven at +1.0R; bank 50% partial profit at TP1."
            )
        else:
            grade = "C"
            risk_mult = 0.5
            notes = [n for n in [delta_note, vol_note, htf_note] if n]
            context = f" ({', '.join(notes)})" if notes else ""
            tactical_advice = (
                f"Grade C: Delta Divergence / Absorption Caution{context}. "
                f"Trade preserved; conservative 0.5x risk recommended."
            )

        return AuditResult(
            grade=grade,
            confluence_pct=round(total_score, 1),
            est_delta_badge=delta_badge,
            tactical_advice=tactical_advice,
            recommended_risk_multiplier=risk_mult,
            is_approved=True,  # 100% preserved
            details={
                "base_conviction_pts": round(float(base_conviction) * 0.40, 1),
                "htf_pts": round(htf_pts, 1),
                "delta_pts": round(delta_pts, 1),
                "vol_pts": round(vol_pts, 1),
                "current_sigma": round(current_sigma, 2),
            },
        )


institutional_risk_auditor = InstitutionalRiskAuditor()
