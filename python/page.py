"""HTML for the owner's page (part 2). Pure functions: no server, no file reading.

All text that comes from the data files goes through escape(), because a customer
name such as "<script>" must show as text, not run.
"""

from html import escape

from messages import format_amount

STEP_LABELS = {
    "friendly": "Friendly reminder",
    "firm": "Firm reminder",
    "final": "Final reminder",
}

REASON_TEXT = {
    "duplicate_id": "More than one invoice has this number, so we cannot tell which one is right.",
    "invalid_amount": "The amount is missing, is not a number, or is zero or less.",
    "missing_due_date": "The invoice has no due date.",
    "invalid_due_date": "The due date is not a real date written as YYYY-MM-DD.",
    "invalid_paid_date": "The paid date is not a real date written as YYYY-MM-DD, or it is in the future.",
}

DECISION_TEXT = {"approved": "Approved", "rejected": "Rejected"}

STYLE = """
:root { color-scheme: light; --text: #1d2330; --muted: #5a6275; --line: #d6dae3;
  --bg: #f5f6f8; --card: #ffffff; --accent: #1f5fd1; --ok: #146c3a; --warn: #9a3412; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--text); background: var(--bg); }
main { max-width: 860px; margin: 0 auto; padding: 16px; }
h1 { font-size: 1.6rem; margin: 0.5rem 0 0.25rem; }
h2 { font-size: 1.25rem; margin: 2rem 0 0.75rem; }
p { margin: 0.25rem 0 0.75rem; }
.muted { color: var(--muted); }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
.card h3 { font-size: 1.05rem; margin: 0 0 0.5rem; overflow-wrap: anywhere; }
.facts { display: grid; grid-template-columns: max-content 1fr; gap: 2px 12px; margin: 0 0 0.75rem; }
.facts dt { color: var(--muted); }
.facts dd { margin: 0; overflow-wrap: anywhere; }
.message { white-space: pre-wrap; background: var(--bg); border-radius: 6px; padding: 12px;
  margin: 0.5rem 0 0; font: inherit; overflow-wrap: anywhere; }
.status { font-weight: 600; flex-basis: 100%; }  /* own line, so the buttons stay together */
.status.approved { color: var(--ok); }
.status.rejected { color: var(--warn); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 0.75rem; }
.actions form { margin: 0; }
button { font: inherit; min-height: 44px; padding: 8px 16px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--accent); background: var(--card); color: var(--accent); }
button.primary { background: var(--accent); color: #fff; }
button:focus-visible, summary:focus-visible { outline: 3px solid #f59e0b; outline-offset: 2px; }
summary { cursor: pointer; color: var(--accent); min-height: 44px; display: flex; align-items: center; }
.notice { background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--accent);
  border-radius: 8px; padding: 16px; }
.notice.error { border-left-color: var(--warn); }
"""


def _page(title, body):
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{escape(title)}</title>\n<style>{STYLE}</style>\n</head>\n"
        f"<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n"
    )


def _decision_controls(action, decision):
    """Approve/reject forms for one action, or its recorded decision with an undo button."""
    invoice_id = escape(action["invoice_id"])
    step = escape(action["step"])
    hidden = (f'<input type="hidden" name="invoice_id" value="{invoice_id}">'
              f'<input type="hidden" name="step" value="{step}">')

    def button(value, text, css_class=""):
        label = f"{text} the {step} reminder for {invoice_id}"
        return (f'<form method="post" action="/decision">{hidden}'
                f'<input type="hidden" name="decision" value="{value}">'
                f'<button type="submit" class="{css_class}" aria-label="{label}">{text}</button></form>')

    if decision is None:
        return (f'<div class="actions"><span class="status">Waiting for your approval</span>'
                f'{button("approved", "Approve", "primary")}{button("rejected", "Reject")}</div>')
    return (f'<div class="actions"><span class="status {decision}" role="status">'
            f'{DECISION_TEXT[decision]}</span>{button("undo", "Undo")}</div>')


def _action_card(action, invoice, decision):
    step_label = STEP_LABELS[action["step"]]
    if action["needs_approval"]:
        controls = _decision_controls(action, decision)
    else:
        controls = '<div class="actions"><span class="status">No approval needed</span></div>'
    return (
        '<li class="card">'
        f'<h3>{escape(step_label)}: {escape(str(invoice.get("customer", "")))}</h3>'
        '<dl class="facts">'
        f'<dt>Invoice</dt><dd>{escape(action["invoice_id"])}</dd>'
        f'<dt>Amount</dt><dd>{escape(format_amount(invoice["amount"], str(invoice.get("currency", ""))))}</dd>'
        f'<dt>Due date</dt><dd>{escape(invoice["due_date"])}</dd>'
        f'<dt>Days overdue</dt><dd>{action["days_overdue"]}</dd>'
        '</dl>'
        '<details><summary>Show the message</summary>'
        f'<div class="message">{escape(action["message"]) or "<em>No message.</em>"}</div></details>'
        f'{controls}'
        '</li>'
    )


def _skipped_item(item, customers):
    customer = customers.get(item["invoice_id"])
    who = f" ({escape(str(customer))})" if customer else ""
    reason = REASON_TEXT.get(item["reason"], "The invoice data could not be checked.")
    return (f'<li class="card"><h3>{escape(item["invoice_id"])}{who}</h3>'
            f'<p>{escape(reason)}</p></li>')


def render_plan_page(plan, invoices, decisions):
    """The page for a plan from plan.build_plan.

    invoices: the invoice list the plan was built from (for customer, amount, due date)
    decisions: {(invoice_id, step): "approved" | "rejected"}
    """
    # Action ids are unique (duplicate ids are skipped), so a lookup by id is safe for them.
    # For skipped duplicates, the first customer with that id is shown.
    by_id = {}
    for invoice in invoices:
        by_id.setdefault(invoice["id"], invoice)
    customers = {invoice_id: invoice.get("customer") for invoice_id, invoice in by_id.items()}

    actions = plan["actions"]
    skipped = plan["skipped"]
    waiting = sum(1 for a in actions
                  if a["needs_approval"] and (a["invoice_id"], a["step"]) not in decisions)

    parts = [
        "<h1>Payment reminders</h1>",
        f'<p class="muted">Plan for {escape(plan["today"])}.</p>',
    ]

    if actions:
        parts.append(f'<p>{len(actions)} reminder{"s" if len(actions) != 1 else ""} to send today. '
                     f'{waiting} waiting for your approval.</p>')
        parts.append('<p class="muted">Nothing is sent from this page. It only records your decisions.</p>')
    else:
        parts.append('<div class="notice"><p><strong>Nothing to do today.</strong></p>'
                     '<p>No invoice needs a reminder: they are paid, not overdue enough yet, '
                     'or already reminded at their current step.</p></div>')

    if actions:
        parts.append('<h2>Today\'s reminders</h2><ul class="list">')
        parts.extend(_action_card(a, by_id[a["invoice_id"]], decisions.get((a["invoice_id"], a["step"])))
                     for a in actions)
        parts.append("</ul>")

    if skipped:
        parts.append(f'<h2>Invoices we could not check ({len(skipped)})</h2>'
                     '<p class="muted">Fix these in the invoice data; they get no reminder until then.</p>'
                     '<ul class="list">')
        parts.extend(_skipped_item(item, customers) for item in skipped)
        parts.append("</ul>")

    return _page("Payment reminders", "\n".join(parts))


def render_error_page(problem):
    """The page shown when the plan cannot be made, for example unreadable data files."""
    body = (
        "<h1>Payment reminders</h1>"
        '<div class="notice error" role="alert">'
        "<p><strong>The invoice data could not be read, so there is no plan for today.</strong></p>"
        "<p>No reminders are planned until this is fixed. Ask whoever maintains the data files to check them.</p>"
        f'<p class="muted">Details: {escape(problem)}</p>'
        "</div>"
    )
    return _page("Payment reminders: data problem", body)
