import unittest
from app.core.engines.risk_auditor_engine import InstitutionalRiskAuditor
from app.core.engines.htf_structure_engine import HTFAlignmentResult
from app.core.engines.order_flow_engine import IntraCandleDecomposition


class TestInstitutionalRiskAuditor(unittest.TestCase):
    def setUp(self):
        self.auditor = InstitutionalRiskAuditor()

    def test_grade_a_prime_setup(self):
        # High base conviction, HTF bullish flow aligned, strong positive delta, normal volatility
        htf = HTFAlignmentResult(
            symbol="EURUSD",
            direction="BUY",
            is_aligned=True,
            htf_trend_bias="BULLISH_FLOW",
            nearest_barrier=None,
            distance_to_barrier_pips=100.0,
            barrier_conflict=False,
            confluence_score=0.90,
            advisory_note="Flow aligned",
        )
        of = IntraCandleDecomposition(
            symbol="EURUSD",
            timeframe="15m",
            bar_delta=500.0,
            cvd_20=2500.0,
            ofi=0.45,
            is_bullish_delta=True,
            upper_wick_ratio=0.1,
            lower_wick_ratio=0.1,
            is_upper_absorption=False,
            is_lower_absorption=False,
            sub_bars_count=0,
            confluence_tag="🟢 Strong Buying Delta (+500)",
        )
        res = self.auditor.audit(
            symbol="EURUSD",
            direction="BUY",
            base_conviction=85.0,
            htf_result=htf,
            order_flow=of,
            current_sigma=0.5,
            is_sweep_confirmed=True,
        )
        self.assertEqual(res.grade, "A")
        self.assertEqual(res.recommended_risk_multiplier, 1.0)
        self.assertTrue(res.is_approved)  # Never drops
        self.assertIn("Grade A", res.tactical_advice)

    def test_grade_b_extended_volatility(self):
        # Technical setup solid, but price stretched into 2.2σ band and delta neutral
        htf = HTFAlignmentResult(
            symbol="EURUSD",
            direction="BUY",
            is_aligned=True,
            htf_trend_bias="BULLISH_FLOW",
            nearest_barrier=None,
            distance_to_barrier_pips=100.0,
            barrier_conflict=False,
            confluence_score=0.75,
            advisory_note="Flow aligned",
        )
        res = self.auditor.audit(
            symbol="EURUSD",
            direction="BUY",
            base_conviction=72.0,
            htf_result=htf,
            order_flow=None,
            current_sigma=2.2,  # Extended
            is_sweep_confirmed=True,
        )
        self.assertEqual(res.grade, "B")
        self.assertEqual(res.recommended_risk_multiplier, 0.75)
        self.assertTrue(res.is_approved)  # Preserved
        self.assertIn("Lock Breakeven", res.tactical_advice)

    def test_grade_c_absorption_caution_never_suppressed(self):
        # Setup has lower confidence, counter-trend or absorption caution
        res = self.auditor.audit(
            symbol="EURUSD",
            direction="BUY",
            base_conviction=55.0,
            htf_result=None,
            order_flow=None,
            current_sigma=2.7,
            is_sweep_confirmed=False,
        )
        self.assertEqual(res.grade, "C")
        self.assertEqual(res.recommended_risk_multiplier, 0.5)
        self.assertTrue(res.is_approved)  # ZERO SIGNAL DROPPING GUARANTEE
        self.assertIn("Grade C", res.tactical_advice)


if __name__ == "__main__":
    unittest.main()
