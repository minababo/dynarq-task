"""Tests for the page HTML (rendering only, no server)."""

import unittest

from page import REASON_TEXT, format_amount, render_error_page, render_plan_page
from plan import build_plan
from tests.helpers import TODAY, make_invoice


def render(invoices, sent=(), decisions=None):
    plan = build_plan(invoices, list(sent), TODAY)
    return render_plan_page(plan, invoices, decisions or {})


class FormatAmountTest(unittest.TestCase):
    def test_two_decimals_and_thousands(self):
        self.assertEqual(format_amount(1250.0, "EUR"), "EUR 1,250.00")
        self.assertEqual(format_amount(215.5, "EUR"), "EUR 215.50")
        self.assertEqual(format_amount(7, "USD"), "USD 7.00")


class PlanPageTest(unittest.TestCase):
    def test_action_shows_all_fields(self):
        html = render([make_invoice("INV-7", customer="Alder Ltd", amount=1250.0,
                                    due_date="2026-09-30")])
        for text in ["Alder Ltd", "INV-7", "EUR 1,250.00", "2026-09-30", "<dd>12</dd>", "Firm reminder"]:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_firm_and_final_have_approve_and_reject(self):
        html = render([make_invoice("INV-1", due_date="2026-09-30")])
        self.assertIn('value="approved"', html)
        self.assertIn('value="rejected"', html)
        self.assertIn('aria-label="Approve the firm reminder for INV-1"', html)
        self.assertIn("1 waiting for your approval", html)

    def test_friendly_has_no_decision_buttons(self):
        html = render([make_invoice("INV-1", due_date="2026-10-09")])
        self.assertIn("No approval needed", html)
        self.assertNotIn("<button", html)

    def test_recorded_decision_is_shown_with_undo(self):
        invoices = [make_invoice("INV-1", due_date="2026-09-30")]
        for decision, text in [("approved", "Approved"), ("rejected", "Rejected")]:
            with self.subTest(decision=decision):
                html = render(invoices, decisions={("INV-1", "firm"): decision})
                self.assertIn(f">{text}</span>", html)
                self.assertIn('value="undo"', html)
                self.assertNotIn('value="approved"', html)
                self.assertIn("0 waiting for your approval", html)

    def test_decision_for_an_older_step_does_not_apply(self):
        invoices = [make_invoice("INV-1", due_date="2026-09-01")]  # now final
        html = render(invoices, decisions={("INV-1", "firm"): "approved"})
        self.assertIn('value="approved"', html)  # still asks about the final step

    def test_nothing_to_do(self):
        html = render([make_invoice(due_date="2026-10-11")])
        self.assertIn("Nothing to do today", html)
        self.assertNotIn("Today's reminders", html)

    def test_empty_data(self):
        html = render([])
        self.assertIn("Nothing to do today", html)
        self.assertNotIn("could not check", html)

    def test_skipped_in_plain_words(self):
        html = render([make_invoice("INV-9", customer="Granite Row", due_date="2026-02-30")])
        self.assertIn("Invoices we could not check (1)", html)
        self.assertIn("Granite Row", html)
        self.assertIn(REASON_TEXT["invalid_due_date"], html)
        self.assertNotIn("invalid_due_date", html)

    def test_every_reason_has_plain_words(self):
        self.assertEqual(set(REASON_TEXT), {"duplicate_id", "invalid_amount", "missing_due_date",
                                            "invalid_due_date", "invalid_paid_date"})

    def test_duplicate_listed_once(self):
        html = render([make_invoice("INV-1"), make_invoice("INV-1")])
        self.assertEqual(html.count("<h3>INV-1"), 1)

    def test_data_is_escaped(self):
        html = render([make_invoice("INV-<b>", customer="<script>alert(1)</script>",
                                    due_date="2026-09-30")])
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("INV-<b>", html)

    def test_mobile_and_language_basics(self):
        html = render([])
        self.assertIn('<html lang="en">', html)
        self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', html)


class ErrorPageTest(unittest.TestCase):
    def test_explains_problem_and_escapes_details(self):
        html = render_error_page("cannot read <data>/invoices.json")
        self.assertIn("could not be read", html)
        self.assertIn('role="alert"', html)
        self.assertIn("&lt;data&gt;", html)


if __name__ == "__main__":
    unittest.main()
