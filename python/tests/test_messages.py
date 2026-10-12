"""Tests for reminder messages (part 3)."""

import json
import unittest
from pathlib import Path

from messages import TEMPLATES, build_message, format_amount, message_problems
from plan import build_plan
from tests.helpers import TODAY, make_invoice

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

FORBIDDEN_WORDS = ["fee", "interest", "charge", "penalt", "legal", "court", "deadline", "within",
                   "%", "previous", "earlier", "last reminder", "already sent", "already reminded",
                   "again"]


class FormatAmountTest(unittest.TestCase):
    def test_two_decimals_with_currency(self):
        cases = [((1250.0, "EUR"), "EUR 1,250.00"), ((215.5, "EUR"), "EUR 215.50"),
                 ((7, "USD"), "USD 7.00"), ((0.1, "EUR"), "EUR 0.10"),
                 ((1234567.891, "GBP"), "GBP 1,234,567.89")]
        for (amount, currency), expected in cases:
            with self.subTest(amount=amount):
                self.assertEqual(format_amount(amount, currency), expected)


class BuildMessageTest(unittest.TestCase):
    def setUp(self):
        self.invoice = make_invoice("INV-1001", customer="Alder Fabrication Ltd", amount=1250.0,
                                    currency="EUR", due_date="2026-09-30")

    def test_every_step_contains_required_facts_and_nothing_else(self):
        for step in TEMPLATES:
            with self.subTest(step=step):
                message = build_message(self.invoice, step, 12)
                for text in ["Alder Fabrication Ltd", "INV-1001", "2026-09-30", "EUR 1,250.00", "12 days"]:
                    self.assertIn(text, message)
                self.assertEqual(message_problems(message, self.invoice, 12), [])

    def test_no_forbidden_claims(self):
        for step in TEMPLATES:
            message = build_message(self.invoice, step, 30).lower()
            for word in FORBIDDEN_WORDS:
                with self.subTest(step=step, word=word):
                    self.assertNotIn(word, message)

    def test_tone_differs_per_step(self):
        friendly, firm, final = (build_message(self.invoice, s, 30) for s in ["friendly", "firm", "final"])
        self.assertIn("friendly reminder", friendly)
        self.assertIn("as soon as possible", firm)
        self.assertIn("final reminder", final)
        self.assertEqual(len({friendly, firm, final}), 3)

    def test_figures_in_customer_name_and_id_are_allowed(self):
        invoice = make_invoice("INV-0042", customer="3D Print 2000 Ltd", amount=99.99, due_date="2026-09-01")
        message = build_message(invoice, "final", 41)
        self.assertEqual(message_problems(message, invoice, 41), [])

    def test_days_equal_to_part_of_another_fact(self):
        # 12 days overdue, and 12 also appears in the amount and due date.
        invoice = make_invoice("INV-12", amount=1212.0, due_date="2026-09-30")
        self.assertEqual(message_problems(build_message(invoice, "firm", 12), invoice, 12), [])

    def test_unusual_text_is_kept_as_is(self):
        invoice = make_invoice(customer="Zoë & Søn {Ltd}", due_date="2026-09-30")
        message = build_message(invoice, "firm", 12)
        self.assertIn("Zoë & Søn {Ltd}", message)
        self.assertEqual(message_problems(message, invoice, 12), [])


class MessageProblemsTest(unittest.TestCase):
    """The checker must catch text that breaks the rules (for example from an AI model)."""

    def setUp(self):
        self.invoice = make_invoice("INV-7", customer="Birch Ltd", amount=480.0, due_date="2026-10-09")
        self.good = "Dear Birch Ltd, invoice INV-7 for EUR 480.00 was due on 2026-10-09 and is 3 days overdue."

    def test_good_message(self):
        self.assertEqual(message_problems(self.good, self.invoice, 3), [])

    def test_missing_facts(self):
        cases = {
            "missing customer name": self.good.replace("Birch Ltd", "you"),
            "missing invoice id": self.good.replace("INV-7", "your invoice"),
            "missing due date": self.good.replace("2026-10-09", "last week"),
            "missing amount": self.good.replace("EUR 480.00", "EUR 480"),
            "missing days overdue": self.good.replace("3 days", "some days"),
        }
        for problem, message in cases.items():
            with self.subTest(problem=problem):
                self.assertIn(problem, message_problems(message, self.invoice, 3))

    def test_extra_figures(self):
        for addition in [" A fee of 40 EUR applies.", " Pay within 7 days.", " Interest is 8%.",
                         " We wrote on 2026-10-01.", " This is reminder 2."]:
            with self.subTest(addition=addition):
                problems = message_problems(self.good + addition, self.invoice, 3)
                self.assertTrue(any(p.startswith("unexpected figures") for p in problems), problems)

    def test_wrong_days(self):
        message = self.good.replace("3 days", "5 days")
        problems = message_problems(message, self.invoice, 3)
        self.assertIn("missing days overdue", problems)
        self.assertIn("unexpected figures: 5", problems)


class PlanMessagesTest(unittest.TestCase):
    def test_every_sample_action_has_a_valid_message(self):
        invoices = json.loads((DATA_DIR / "invoices.json").read_text(encoding="utf-8"))
        sent = json.loads((DATA_DIR / "sent.json").read_text(encoding="utf-8"))
        by_id = {invoice["id"]: invoice for invoice in invoices}
        actions = build_plan(invoices, sent, TODAY)["actions"]
        self.assertTrue(actions)
        for action in actions:
            with self.subTest(invoice_id=action["invoice_id"]):
                invoice = by_id[action["invoice_id"]]
                self.assertEqual(action["message"], build_message(invoice, action["step"],
                                                                  action["days_overdue"]))
                self.assertEqual(message_problems(action["message"], invoice, action["days_overdue"]), [])


if __name__ == "__main__":
    unittest.main()
