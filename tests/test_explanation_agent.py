from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from code.explanation_agent import (
    FinalDecision,
    explain_decision,
    explain_decisions,
    validate_explanation,
)
from code.extraction_common import CallLogger, ProviderError, ProviderResponse


class ExplanationAgentTests(unittest.TestCase):
    def decision(self, request_id: str = "request_01") -> FinalDecision:
        return FinalDecision(
            request_id=request_id,
            requested_amount=Decimal("25256"),
            amount_safe_to_pay=Decimal("25256"),
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment=date(2024, 3, 3),
            spending_changes_needed="none",
        )

    def test_returns_only_prose_and_does_not_mutate_final_decision(self) -> None:
        calls = []

        def fake_transport(body):
            calls.append(body)
            system = body["messages"][0]["content"]
            self.assertIn("already final", system)
            self.assertIn("never change", system)
            payload = json.loads(body["messages"][1]["content"])
            self.assertEqual(payload["DECISION"]["request_id"], "request_01")
            return ProviderResponse(
                {"text": "Pay IDR 25,256 today. This keeps the minimum balance protected."},
                50,
                12,
            )

        decision = self.decision()
        before = decision
        with tempfile.TemporaryDirectory() as directory:
            result = explain_decision(
                decision,
                ("The request is safe today.", "The minimum balance is protected."),
                transport=fake_transport,
                cache_dir=Path(directory) / "cache",
                call_logger=CallLogger(Path(directory) / "calls.jsonl"),
            )
        self.assertIsInstance(result.explanation, str)
        self.assertEqual(result.explanation, "Pay IDR 25,256 today. This keeps the minimum balance protected.")
        self.assertEqual(decision, before)
        self.assertEqual(calls[0]["max_tokens"], 180)
        self.assertEqual(calls[0]["temperature"], 0)

    def test_cache_prevents_second_provider_call(self) -> None:
        calls = []

        def fake_transport(_body):
            calls.append(1)
            return ProviderResponse({"text": "Wait until 15 June 2024, then pay in full."}, 10, 8)

        with tempfile.TemporaryDirectory() as directory:
            first = explain_decision(
                self.decision("request_cache"),
                ("The full payment is safe later.", "The current minimum must remain protected."),
                transport=fake_transport,
                cache_dir=Path(directory) / "cache",
            )
            second = explain_decision(
                self.decision("request_cache"),
                ("The full payment is safe later.", "The current minimum must remain protected."),
                transport=fake_transport,
                cache_dir=Path(directory) / "cache",
            )
        self.assertEqual(first.explanation, second.explanation)
        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(len(calls), 1)

    def test_requires_two_to_four_nonempty_supporting_facts(self) -> None:
        for facts in ((), ("one",), ("a", "b", "c", "d", "e"), ("ok", "")):
            with self.subTest(facts=facts):
                with self.assertRaises(ValueError):
                    explain_decision(self.decision(), facts, transport=lambda _: ProviderResponse({"text": "ok"}))

    def test_rejects_non_prose_or_more_than_two_sentences(self) -> None:
        invalid = [
            "{\"recommended_payment_method\":\"wait\"}",
            "- Pay today.",
            "One. Two. Three.",
            "",
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ProviderError):
                    validate_explanation(value)

    def test_five_sample_style_explanations_use_only_fixed_decision_facts(self) -> None:
        def fake_transport(body):
            payload = json.loads(body["messages"][1]["content"])
            decision = payload["DECISION"]
            method = decision["recommended_payment_method"]
            amount = decision["amount_safe_to_pay"]
            return ProviderResponse(
                {"text": f"Use {method} for the request; the safe amount is {amount}."},
                20,
                10,
            )

        rows = []
        for index in range(5):
            decision = self.decision(f"request_{index:02d}")
            rows.append((decision, ("The final plan is fixed.", "The safe amount is a deterministic result.")))
        with tempfile.TemporaryDirectory() as directory:
            results = explain_decisions(rows, transport=fake_transport, cache_dir=directory)
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIsInstance(result.explanation, str)
            self.assertIn("full_payment", result.explanation)
            self.assertIn("25256", result.explanation)
            self.assertLessEqual(result.explanation.count("."), 2)


if __name__ == "__main__":
    unittest.main()
