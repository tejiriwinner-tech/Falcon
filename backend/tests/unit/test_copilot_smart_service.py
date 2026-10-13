"""
Unit tests for the Falcon Smart AI Co-Pilot Service (Pillar 3)
Verifies live RAG context aggregation, multi-turn handling,
action chip parsing, and deterministic fallback.
"""

import unittest
from app.core.services.copilot_context_service import copilot_context_service
from app.core.services.llm_client import llm_client
from app.core.services.copilot_service import CopilotService
from app.schemas.copilot import ChatMessage, CopilotQueryRequest, ActionChip


class TestCopilotSmartService(unittest.TestCase):
    def setUp(self):
        self.copilot_service = CopilotService()

    def test_context_snapshot_aggregation(self):
        """Context service must assemble all platform telemetry without error."""
        snapshot = copilot_context_service.build_snapshot(target_symbol="XAUUSD")
        self.assertIn("timestamp", snapshot)
        self.assertIn("market_state", snapshot)
        self.assertIn("session_corridors", snapshot)
        self.assertIn("active_signals", snapshot)
        self.assertIn("trade_journal_stats", snapshot)
        self.assertIn("capital_risk_state", snapshot)
        self.assertIn("economic_calendar", snapshot)

    def test_extract_action_chips_from_json_block(self):
        """Action chip parser must extract valid action chips and strip json block from markdown."""
        llm_text = (
            "### Analysis of Gold\n\n"
            "Gold is trading at 2650.50 near the Asian high.\n\n"
            "```json:actions\n"
            '[\n'
            '  {"label": "View Gold Chart", "action": "OPEN_CHART", "payload": {"symbol": "XAUUSD"}},\n'
            '  {"label": "Audit Risk Limits", "action": "AUDIT_RISK", "payload": {}}\n'
            ']\n'
            "```"
        )
        clean_text, chips = llm_client._extract_actions(llm_text)
        self.assertEqual(len(chips), 2)
        self.assertEqual(chips[0].label, "View Gold Chart")
        self.assertEqual(chips[0].action, "OPEN_CHART")
        self.assertEqual(chips[0].payload.get("symbol"), "XAUUSD")
        self.assertNotIn("```json:actions", clean_text)
        self.assertIn("Gold is trading at 2650.50", clean_text)

    def test_extract_action_chips_fallback_defaults(self):
        """When no action block is returned, helpful default action chips are provided."""
        text_without_actions = "Gold looks bullish today."
        clean_text, chips = llm_client._extract_actions(text_without_actions)
        self.assertGreater(len(chips), 0)
        self.assertEqual(chips[0].action, "AUDIT_RISK")

    def test_copilot_handles_technical_analysis_query(self):
        """Query 'Analyze Gold right now' triggers technical analysis with action chips."""
        req = CopilotQueryRequest(
            query="Analyze Gold right now",
            symbol="XAU/USD",
        )
        res = self.copilot_service.handle_query(req)
        self.assertIn(res.intent, ["TECHNICAL_ANALYSIS", "AI_REASONING"])
        self.assertIn("XAU", res.response)
        self.assertIsNotNone(res.suggested_actions)
        self.assertGreater(len(res.suggested_actions), 0)

    def test_copilot_handles_streak_and_risk_query(self):
        """Query 'What is our current streak and recovery status?' returns risk metrics."""
        req = CopilotQueryRequest(
            query="What is our current streak and recovery status?",
        )
        res = self.copilot_service.handle_query(req)
        self.assertIn(res.intent, ["STREAK_AND_RISK", "AI_REASONING"])
        self.assertIn("Multiplier", res.response)
        self.assertIsNotNone(res.risk_context)

    def test_copilot_accepts_conversation_history(self):
        """Copilot must accept multi-turn message history without breaking."""
        history = [
            ChatMessage(role="user", content="What is our risk per trade?"),
            ChatMessage(role="assistant", content="Risk per trade is strictly capped at 1.0% of equity."),
        ]
        req = CopilotQueryRequest(
            query="And what happens after 1 loss?",
            conversation_history=history,
        )
        res = self.copilot_service.handle_query(req)
        self.assertIsNotNone(res.response)
        self.assertGreater(len(res.response), 20)


if __name__ == "__main__":
    unittest.main()
