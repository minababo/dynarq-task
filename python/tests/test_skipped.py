"""Tests for rule 1: invoices skipped because of bad data."""

import unittest

from plan import build_plan
from tests.helpers import MISSING, TODAY, make_invoice


def skipped_of(invoices, sent=None):
    return build_plan(invoices, sent or [], TODAY)["skipped"]


def reason_for(**fields):
    """Plan a single invoice and return its skip reason, or None if it was not skipped."""
    skipped = skipped_of([make_invoice(**fields)])
    return skipped[0]["reason"] if skipped else None


class ValidInvoiceTest(unittest.TestCase):
    def test_valid_invoice_is_not_skipped(self):
        self.assertIsNone(reason_for())


class DuplicateIdTest(unittest.TestCase):
    def test_all_invoices_with_same_id_skipped_and_listed_once(self):
        invoices = [make_invoice("INV-1"), make_invoice("INV-1"), make_invoice("INV-1")]
        self.assertEqual(skipped_of(invoices), [{"invoice_id": "INV-1", "reason": "duplicate_id"}])

    def test_duplicate_wins_over_other_bad_data(self):
        invoices = [make_invoice("INV-1", amount="x"), make_invoice("INV-1", due_date=None)]
        self.assertEqual(skipped_of(invoices), [{"invoice_id": "INV-1", "reason": "duplicate_id"}])

    def test_other_invoices_unaffected(self):
        invoices = [make_invoice("INV-1"), make_invoice("INV-2"), make_invoice("INV-1")]
        self.assertEqual(skipped_of(invoices), [{"invoice_id": "INV-1", "reason": "duplicate_id"}])

    def test_ids_are_case_sensitive(self):
        self.assertEqual(skipped_of([make_invoice("inv-1"), make_invoice("INV-1")]), [])


class InvalidAmountTest(unittest.TestCase):
    def test_bad_amounts(self):
        for value in [MISSING, None, "100", True, 0, 0.0, -5, float("nan")]:
            with self.subTest(amount=value):
                self.assertEqual(reason_for(amount=value), "invalid_amount")

    def test_integer_amount_is_valid(self):
        self.assertIsNone(reason_for(amount=100))

    def test_amount_checked_before_dates(self):
        self.assertEqual(reason_for(amount=0, due_date=None, paid_date=""), "invalid_amount")


class DueDateTest(unittest.TestCase):
    def test_missing_due_date(self):
        for value in [MISSING, None, ""]:
            with self.subTest(due_date=value):
                self.assertEqual(reason_for(due_date=value), "missing_due_date")

    def test_invalid_due_date(self):
        for value in ["2026-02-30", "30/09/2026", "2026-9-30", " ", 20260930, False]:
            with self.subTest(due_date=value):
                self.assertEqual(reason_for(due_date=value), "invalid_due_date")

    def test_due_date_checked_before_paid_date(self):
        self.assertEqual(reason_for(due_date="bad", paid_date="bad"), "invalid_due_date")


class PaidDateTest(unittest.TestCase):
    def test_unpaid_when_missing_or_null(self):
        for value in [MISSING, None]:
            with self.subTest(paid_date=value):
                self.assertIsNone(reason_for(paid_date=value))

    def test_invalid_paid_date(self):
        for value in ["", "2026-02-30", "12/10/2026", 0, False]:
            with self.subTest(paid_date=value):
                self.assertEqual(reason_for(paid_date=value), "invalid_paid_date")

    def test_paid_after_today_is_invalid(self):
        self.assertEqual(reason_for(paid_date="2026-10-13"), "invalid_paid_date")

    def test_paid_today_or_earlier_is_valid(self):
        for value in [TODAY, "2026-01-01"]:
            with self.subTest(paid_date=value):
                self.assertIsNone(reason_for(paid_date=value))


class OrderTest(unittest.TestCase):
    def test_skipped_sorted_by_id_as_plain_text(self):
        invoices = [make_invoice("INV-99", amount=0), make_invoice("INV-100", amount=0),
                    make_invoice("INV-2", amount=0)]
        ids = [item["invoice_id"] for item in skipped_of(invoices)]
        self.assertEqual(ids, ["INV-100", "INV-2", "INV-99"])


class TodayTest(unittest.TestCase):
    def test_invalid_today_raises(self):
        for value in ["2026-02-30", "12/10/2026", "", None]:
            with self.subTest(today=value):
                with self.assertRaises(ValueError):
                    build_plan([], [], value)


if __name__ == "__main__":
    unittest.main()
