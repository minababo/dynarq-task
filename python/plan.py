"""Payment reminder rules engine (part 1).

Run from inside python/:

    python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json

Exit codes: 0 plan written, 1 an input or output file cannot be used, 2 bad arguments.
"""

import argparse
import json
import math
import re
import sys
from datetime import date

from messages import build_message

DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # not \d: it also matches non-ASCII digits

# (step, minimum days overdue, needs approval), lowest step first.
STEPS = [
    ("friendly", 3, False),
    ("firm", 10, True),
    ("final", 24, True),
]
STEP_RANK = {name: rank for rank, (name, _, _) in enumerate(STEPS)}


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


def bad_data_reason(invoice, today):
    """Return the first bad-data reason for one invoice, or None if its data is usable.

    Duplicate ids are checked separately, because they depend on the whole file.
    """
    if not is_valid_amount(invoice.get("amount")):
        return "invalid_amount"

    due_date = invoice.get("due_date")
    if due_date is None or due_date == "":
        return "missing_due_date"
    if parse_date(due_date) is None:
        return "invalid_due_date"

    # A missing key or null means unpaid; anything else must be a real date, not in the future.
    paid_date = invoice.get("paid_date")
    if paid_date is not None:
        paid = parse_date(paid_date)
        if paid is None or paid > today:
            return "invalid_paid_date"

    return None


def find_duplicate_ids(invoices):
    """Return the set of ids that appear on more than one invoice."""
    seen = set()
    duplicates = set()
    for invoice in invoices:
        invoice_id = invoice["id"]
        if invoice_id in seen:
            duplicates.add(invoice_id)
        seen.add(invoice_id)
    return duplicates


def highest_sent_ranks(sent):
    """Map invoice id -> rank of the highest step already sent. Unknown steps are ignored."""
    ranks = {}
    for entry in sent:
        if not isinstance(entry, dict):
            continue
        rank = STEP_RANK.get(entry.get("step"))
        if rank is None:
            continue
        invoice_id = entry.get("invoice_id")
        ranks[invoice_id] = max(rank, ranks.get(invoice_id, -1))
    return ranks


def reached_step(days_overdue):
    """Return (step, needs_approval) for the highest step reached, or None if none is."""
    reached = None
    for name, min_days, needs_approval in STEPS:
        if days_overdue >= min_days:
            reached = (name, needs_approval)
    return reached


def plan_action(invoice, today, sent_ranks):
    """Return the action for one invoice with valid data, or None if nothing is due today."""
    if invoice.get("paid_date") is not None:
        return None  # paid on or before today (already validated), even if reminders were sent

    days_overdue = (today - parse_date(invoice["due_date"])).days
    reached = reached_step(days_overdue)
    if reached is None:
        return None  # not yet: fewer than 3 days overdue

    step, needs_approval = reached
    if sent_ranks.get(invoice["id"], -1) >= STEP_RANK[step]:
        return None  # this step or a higher one was already sent

    return {
        "invoice_id": invoice["id"],
        "step": step,
        "needs_approval": needs_approval,
        "days_overdue": days_overdue,
        "message": build_message(invoice, step, days_overdue),
    }


def build_plan(invoices, sent, today):
    """Return the plan for `today` as a dict with the keys today, actions and skipped.

    invoices: the list from invoices.json
    sent: the list from sent.json
    today: a date string, YYYY-MM-DD (raises ValueError if it is not a real date)
    """
    today_date = parse_date(today)
    if today_date is None:
        raise ValueError(f"today must be a real date as YYYY-MM-DD, got {today!r}")

    duplicates = find_duplicate_ids(invoices)
    # Each duplicate id is listed once, however many invoices share it.
    skipped = [{"invoice_id": invoice_id, "reason": "duplicate_id"} for invoice_id in duplicates]
    actions = []
    sent_ranks = highest_sent_ranks(sent)

    for invoice in invoices:
        if invoice["id"] in duplicates:
            continue
        reason = bad_data_reason(invoice, today_date)
        if reason is not None:
            skipped.append({"invoice_id": invoice["id"], "reason": reason})
            continue
        action = plan_action(invoice, today_date, sent_ranks)
        if action is not None:
            actions.append(action)

    # Plain text order, character by character: INV-100 comes before INV-99.
    actions.sort(key=lambda item: item["invoice_id"])
    skipped.sort(key=lambda item: item["invoice_id"])
    return {"today": today, "actions": actions, "skipped": skipped}


class InputError(Exception):
    """An input file cannot be used. The message is written for the person running the tool."""


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as error:
        raise InputError(f"cannot read {path}: {error.strerror or error}") from error
    except UnicodeDecodeError as error:
        raise InputError(f"cannot read {path}: the file is not UTF-8 text") from error
    except json.JSONDecodeError as error:
        raise InputError(f"{path} is not valid JSON (line {error.lineno}, column {error.colno})") from error


def load_inputs(invoices_path, sent_path):
    """Read and shape-check both files. Returns (invoices, sent) or raises InputError.

    Only the file structure is checked here. Bad values inside an invoice are not
    errors: build_plan reports them as skipped.
    """
    invoices = read_json(invoices_path)
    if not isinstance(invoices, list):
        raise InputError(f"{invoices_path} must contain a JSON list of invoices")
    for position, invoice in enumerate(invoices, start=1):
        if not isinstance(invoice, dict) or not isinstance(invoice.get("id"), str):
            raise InputError(f"{invoices_path}: invoice number {position} has no text id")

    sent = read_json(sent_path)
    if not isinstance(sent, list):
        raise InputError(f"{sent_path} must contain a JSON list of sent reminders")
    return invoices, sent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plan today's payment reminders.")
    parser.add_argument("--invoices", required=True, help="path to invoices.json")
    parser.add_argument("--sent", required=True, help="path to sent.json")
    parser.add_argument("--today", required=True, help="date as YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="path to write the plan JSON")
    args = parser.parse_args(argv)

    if parse_date(args.today) is None:
        print(f"Error: --today must be a real date as YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
        return 2

    try:
        invoices, sent = load_inputs(args.invoices, args.sent)
    except InputError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    plan = build_plan(invoices, sent, args.today)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as error:
        print(f"Error: cannot write {args.out}: {error.strerror or error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(plan['actions'])} actions and {len(plan['skipped'])} skipped to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
