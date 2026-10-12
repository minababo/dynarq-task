"""Tests for the small input checks the rules are built on."""

import unittest
from datetime import date

from plan import is_valid_amount, parse_date


class ParseDateTest(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(parse_date("2026-09-30"), date(2026, 9, 30))

    def test_leap_day_only_in_leap_year(self):
        self.assertEqual(parse_date("2024-02-29"), date(2024, 2, 29))
        self.assertIsNone(parse_date("2026-02-29"))

    def test_impossible_dates(self):
        for value in ["2026-02-30", "2026-13-01", "2026-00-10", "2026-04-31", "2026-10-00"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_date(value))

    def test_wrong_format(self):
        for value in ["30/09/2026", "20260930", "2026-9-30", "2026-09-30T00:00:00",
                      " 2026-09-30", "2026-09-30 ", "2026-09-30\n", "", "today",
                      "٢٠٢٦-09-30"]:  # Arabic-Indic digits
            with self.subTest(value=value):
                self.assertIsNone(parse_date(value))

    def test_non_string_types(self):
        for value in [None, 20260930, 2026.0, True, ["2026-09-30"], {"d": "2026-09-30"}]:
            with self.subTest(value=value):
                self.assertIsNone(parse_date(value))


class IsValidAmountTest(unittest.TestCase):
    def test_positive_numbers(self):
        for value in [1, 0.01, 1250.0, 215.5]:
            with self.subTest(value=value):
                self.assertTrue(is_valid_amount(value))

    def test_zero_and_negative(self):
        for value in [0, 0.0, -0.0, -1, -0.01]:
            with self.subTest(value=value):
                self.assertFalse(is_valid_amount(value))

    def test_not_a_number(self):
        for value in ["1250.0", "", None, True, False, [1], {"a": 1}]:
            with self.subTest(value=value):
                self.assertFalse(is_valid_amount(value))

    def test_non_finite(self):
        # Python's json module accepts NaN and Infinity, so guard against them.
        for value in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(value=value):
                self.assertFalse(is_valid_amount(value))


if __name__ == "__main__":
    unittest.main()
