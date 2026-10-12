"""Payment reminder rules engine (part 1).

Run from inside python/:

    python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json

This starter only reads the files and writes an empty plan in the required shape.
The rules are yours to build.
"""

import argparse
import json
import math
import re
from datetime import date

DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # not \d: it also matches non-ASCII digits


def parse_date(value):
    """Return a date if value is a real date written exactly as YYYY-MM-DD, else None.

    The pattern check comes first because date.fromisoformat also accepts other
    forms (for example "20261012"), which the rules do not allow.
    """
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:  # right shape, impossible date such as 2026-02-30
        return None


def is_valid_amount(value):
    """True if value is a finite JSON number greater than 0.

    bool is excluded on purpose: in Python True is an int, but in JSON it is not a number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0


def build_plan(invoices, sent, today):
    """Return the plan for `today` as a dict with the keys today, actions and skipped.

    invoices: the list from invoices.json
    sent: the list from sent.json
    today: a date string, YYYY-MM-DD
    """
    # TODO: apply the rules in README.md part 1 and fill both lists,
    # sorted by invoice id. Each action also needs a message (part 3).
    return {"today": today, "actions": [], "skipped": []}


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Plan today's payment reminders.")
    parser.add_argument("--invoices", required=True, help="path to invoices.json")
    parser.add_argument("--sent", required=True, help="path to sent.json")
    parser.add_argument("--today", required=True, help="date as YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="path to write the plan JSON")
    args = parser.parse_args()

    invoices = read_json(args.invoices)
    sent = read_json(args.sent)
    plan = build_plan(invoices, sent, args.today)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
