"""Reminder messages (part 3): the email text the customer would receive.

Messages come from fixed templates, so they work with no API key and no internet.
Each message contains only facts from the invoice: customer, invoice id, due date,
amount and days overdue. No fees, interest, deadlines or earlier reminders; legal
wording is the owner's decision (see RESEARCH.md).

message_problems() checks a message against those rules. The templates are tested
with it, and any future text source (for example an AI model) should be checked
with it before use.
"""

import re

TEMPLATES = {
    "friendly": (
        "Dear {customer},\n\n"
        "This is a friendly reminder that invoice {invoice_id} for {amount} was due on {due_date} "
        "and is now {days} days overdue. It may simply have been missed.\n\n"
        "If you have already paid, thank you, and please ignore this message. Otherwise, we would "
        "be grateful if you could arrange payment at your earliest convenience.\n\n"
        "Kind regards"
    ),
    "firm": (
        "Dear {customer},\n\n"
        "Invoice {invoice_id} for {amount} was due on {due_date} and is now {days} days overdue. "
        "We have not received payment.\n\n"
        "Please arrange payment as soon as possible. If there is a problem with this invoice, "
        "please contact us so we can resolve it.\n\n"
        "Regards"
    ),
    "final": (
        "Dear {customer},\n\n"
        "This is our final reminder about invoice {invoice_id} for {amount}. It was due on "
        "{due_date} and is now {days} days overdue, and it remains unpaid.\n\n"
        "Please pay this invoice now. If you believe it is not owed, contact us immediately.\n\n"
        "Regards"
    ),
}

NUMBER = re.compile(r"[0-9]+(?:[.,][0-9]+)*")


def format_amount(amount, currency):
    """Format as e.g. 'EUR 1,250.00'."""
    return f"{currency} {amount:,.2f}"


def build_message(invoice, step, days_overdue):
    """Return the reminder text for an invoice with valid data at the given step."""
    return TEMPLATES[step].format(
        customer=invoice["customer"],
        invoice_id=invoice["id"],
        amount=format_amount(invoice["amount"], invoice["currency"]),
        due_date=invoice["due_date"],
        days=days_overdue,
    )


def message_problems(message, invoice, days_overdue):
    """Return a list of rule problems with a message; an empty list means it is fine.

    Checks that the required facts are present and that no other figure appears.
    Figures inside the facts themselves (for example "INV-1001" or a customer called
    "3D Print Ltd") are allowed, so those texts are removed before looking for numbers.
    """
    facts = {
        "customer name": str(invoice["customer"]),
        "invoice id": invoice["id"],
        "due date": invoice["due_date"],
        "amount": format_amount(invoice["amount"], invoice["currency"]),
    }
    problems = [f"missing {name}" for name, text in facts.items() if text not in message]

    rest = message
    for text in sorted(facts.values(), key=len, reverse=True):  # longest first
        if text:
            rest = rest.replace(text, " ")

    figures = NUMBER.findall(rest)
    if str(days_overdue) not in figures:
        problems.append("missing days overdue")
    extra = [figure for figure in figures if figure != str(days_overdue)]
    if extra:
        problems.append(f"unexpected figures: {', '.join(extra)}")
    return problems
