"""Tests for rules 2-4: paid, not yet, and one action at most."""

import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from plan import build_plan
from tests.helpers import TODAY, make_invoice

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def due_days_ago(days):
    """Due date that makes an invoice `days` overdue on TODAY."""
    return (date.fromisoformat(TODAY) - timedelta(days=days)).isoformat()


def plan_one(days_overdue, sent_steps=(), **fields):
    """Plan one invoice that is `days_overdue` with the given steps already sent."""
    invoice = make_invoice("INV-1", due_date=due_days_ago(days_overdue), **fields)
    sent = [{"invoice_id": "INV-1", "step": step, "sent_on": TODAY} for step in sent_steps]
    return build_plan([invoice], sent, TODAY)


def step_of(days_overdue, sent_steps=(), **fields):
    actions = plan_one(days_overdue, sent_steps, **fields)["actions"]
    return actions[0]["step"] if actions else None


class StepBoundaryTest(unittest.TestCase):
    def test_boundaries(self):
        cases = {-5: None, 0: None, 2: None, 3: "friendly", 9: "friendly",
                 10: "firm", 23: "firm", 24: "final", 400: "final"}
        for days, expected in cases.items():
            with self.subTest(days_overdue=days):
                self.assertEqual(step_of(days), expected)

    def test_action_fields(self):
        action = plan_one(12)["actions"][0]
        self.assertEqual(set(action), {"invoice_id", "step", "needs_approval", "days_overdue", "message"})
        self.assertEqual(action["invoice_id"], "INV-1")
        self.assertEqual(action["step"], "firm")
        self.assertIs(action["needs_approval"], True)
        self.assertEqual(action["days_overdue"], 12)

    def test_only_firm_and_final_need_approval(self):
        for days, expected in {3: False, 10: True, 24: True}.items():
            with self.subTest(days_overdue=days):
                self.assertIs(plan_one(days)["actions"][0]["needs_approval"], expected)

    def test_days_counted_across_month_and_year_end(self):
        plan = build_plan([make_invoice(due_date="2025-12-31")], [], "2026-01-03")
        self.assertEqual(plan["actions"][0]["days_overdue"], 3)

    def test_days_counted_across_leap_day(self):
        plan = build_plan([make_invoice(due_date="2028-02-27")], [], "2028-03-08")
        self.assertEqual(plan["actions"][0]["days_overdue"], 10)


class PaidTest(unittest.TestCase):
    def test_paid_invoice_plans_nothing(self):
        self.assertIsNone(step_of(30, paid_date="2026-10-01"))

    def test_paid_today_plans_nothing(self):
        self.assertIsNone(step_of(30, paid_date=TODAY))

    def test_paid_after_reminders_plans_nothing(self):
        self.assertIsNone(step_of(30, sent_steps=["friendly", "firm"], paid_date="2026-10-01"))

    def test_paid_invoice_is_not_skipped(self):
        self.assertEqual(plan_one(30, paid_date="2026-10-01")["skipped"], [])


class AlreadySentTest(unittest.TestCase):
    def test_lower_step_sent_plans_reached_step(self):
        self.assertEqual(step_of(12, ["friendly"]), "firm")
        self.assertEqual(step_of(30, ["friendly", "firm"]), "final")

    def test_same_step_sent_plans_nothing(self):
        self.assertIsNone(step_of(3, ["friendly"]))
        self.assertIsNone(step_of(12, ["firm"]))
        self.assertIsNone(step_of(30, ["final"]))

    def test_higher_step_sent_plans_nothing(self):
        self.assertIsNone(step_of(5, ["firm"]))
        self.assertIsNone(step_of(12, ["final"]))

    def test_skipped_lower_steps_are_not_sent_later(self):
        # firm was sent without friendly; at 12 days nothing more is due.
        self.assertIsNone(step_of(12, ["firm"]))

    def test_duplicate_sent_entries(self):
        self.assertEqual(step_of(12, ["friendly", "friendly"]), "firm")

    def test_unknown_steps_ignored(self):
        for step in ["FIRM", "reminder", "", None, 2]:
            with self.subTest(step=step):
                self.assertEqual(step_of(12, [step]), "firm")

    def test_sent_for_other_invoice_ignored(self):
        invoice = make_invoice("INV-1", due_date=due_days_ago(12))
        sent = [{"invoice_id": "INV-2", "step": "firm", "sent_on": TODAY},
                {"invoice_id": "inv-1", "step": "firm", "sent_on": TODAY}]
        self.assertEqual(build_plan([invoice], sent, TODAY)["actions"][0]["step"], "firm")

    def test_malformed_sent_entries_ignored(self):
        invoice = make_invoice("INV-1", due_date=due_days_ago(12))
        sent = ["INV-1", None, {}, {"step": "firm"}, {"invoice_id": "INV-1"}]
        self.assertEqual(build_plan([invoice], sent, TODAY)["actions"][0]["step"], "firm")

    def test_sent_on_is_not_used(self):
        invoice = make_invoice("INV-1", due_date=due_days_ago(12))
        sent = [{"invoice_id": "INV-1", "step": "firm", "sent_on": "not a date"}]
        self.assertEqual(build_plan([invoice], sent, TODAY)["actions"], [])


class OrderTest(unittest.TestCase):
    def test_actions_sorted_by_id_as_plain_text(self):
        invoices = [make_invoice(i, due_date=due_days_ago(5)) for i in ["INV-99", "INV-100", "INV-2"]]
        ids = [a["invoice_id"] for a in build_plan(invoices, [], TODAY)["actions"]]
        self.assertEqual(ids, ["INV-100", "INV-2", "INV-99"])


class SampleDataTest(unittest.TestCase):
    """End-to-end check of the sample files against the rules worked out by hand."""

    def test_sample_plan(self):
        invoices = json.loads((DATA_DIR / "invoices.json").read_text(encoding="utf-8"))
        sent = json.loads((DATA_DIR / "sent.json").read_text(encoding="utf-8"))
        plan = build_plan(invoices, sent, "2026-10-12")

        actions = [(a["invoice_id"], a["step"], a["needs_approval"], a["days_overdue"])
                   for a in plan["actions"]]
        self.assertEqual(actions, [
            ("INV-1001", "firm", True, 12),       # friendly already sent
            ("INV-1002", "friendly", False, 3),
            ("INV-1004", "final", True, 32),      # firm already sent
            ("INV-1009", "firm", True, 12),       # nothing sent: firm only, not friendly too
            ("INV-1011", "firm", True, 10),
        ])
        self.assertEqual(plan["skipped"], [
            {"invoice_id": "INV-1007", "reason": "invalid_due_date"},
            {"invoice_id": "INV-1008", "reason": "missing_due_date"},
            {"invoice_id": "INV-1010", "reason": "duplicate_id"},
        ])


if __name__ == "__main__":
    unittest.main()
