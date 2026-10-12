"""Shared test data builders."""

TODAY = "2026-10-12"

MISSING = object()  # marker: remove the key instead of setting it


def make_invoice(invoice_id="INV-1", **fields):
    """Return a valid, unpaid invoice due on TODAY. Override fields with keyword arguments.

    Pass a field as MISSING to remove the key entirely.
    """
    invoice = {
        "id": invoice_id,
        "customer": "Example Ltd",
        "email": "accounts@example.test",
        "amount": 100.0,
        "currency": "EUR",
        "due_date": TODAY,
        "paid_date": None,
    }
    for key, value in fields.items():
        if value is MISSING:
            invoice.pop(key, None)
        else:
            invoice[key] = value
    return invoice
