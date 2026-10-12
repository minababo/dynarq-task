"""The owner's page (part 2). Standard library only, no install needed.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date

The data files are read again on every request, so the page always shows the
current files. Decisions are kept in memory while the app runs; nothing is sent.
"""

import os
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from page import render_error_page, render_plan_page
from plan import InputError, build_plan, load_inputs, parse_date

MAX_FORM_BYTES = 10_000
DECISIONS = {"approved", "rejected", "undo"}


def load_config(environ):
    """Return (port, data_dir, today) from environment variables, or raise ValueError."""
    port_text = environ.get("PORT", "8000")
    if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        raise ValueError(f"PORT must be a number from 1 to 65535, got {port_text!r}")

    today = environ.get("TODAY") or date.today().isoformat()
    if parse_date(today) is None:
        raise ValueError(f"TODAY must be a real date as YYYY-MM-DD, got {today!r}")

    return int(port_text), Path(environ.get("DATA_DIR", "../data")), today


class ReminderServer(ThreadingHTTPServer):
    def __init__(self, address, data_dir, today, quiet=False):
        super().__init__(address, Handler)
        self.data_dir = Path(data_dir)
        self.today = today
        self.quiet = quiet
        self.decisions = {}  # (invoice_id, step) -> "approved" | "rejected"
        self.lock = threading.Lock()

    def current_plan(self):
        """Read the data files and build today's plan. Raises InputError if they cannot be used."""
        invoices, sent = load_inputs(self.data_dir / "invoices.json", self.data_dir / "sent.json")
        return build_plan(invoices, sent, self.today), invoices


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404, "Page not found")
            return
        try:
            plan, invoices = self.server.current_plan()
        except InputError as error:
            self.send_html(500, render_error_page(str(error)))
            return
        with self.server.lock:
            decisions = dict(self.server.decisions)
        self.send_html(200, render_plan_page(plan, invoices, decisions))

    def do_POST(self):
        if self.path != "/decision":
            self.send_error(404, "Page not found")
            return

        form = self.read_form()
        if form is None:
            return  # read_form already sent the error
        invoice_id, step, decision = (form.get(key, [""])[0] for key in ("invoice_id", "step", "decision"))
        if decision not in DECISIONS:
            self.send_error(400, "Unknown decision")
            return

        try:
            plan, _ = self.server.current_plan()
        except InputError as error:
            self.send_html(500, render_error_page(str(error)))
            return
        # Only accept decisions for reminders that are in today's plan and need approval.
        if not any(a["invoice_id"] == invoice_id and a["step"] == step and a["needs_approval"]
                   for a in plan["actions"]):
            self.send_error(400, "That reminder is not in today's plan or needs no approval")
            return

        with self.server.lock:
            if decision == "undo":
                self.server.decisions.pop((invoice_id, step), None)
            else:
                self.server.decisions[(invoice_id, step)] = decision

        # Post/Redirect/Get: refreshing the page does not resubmit the form.
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_form(self):
        """Return the parsed form body, or None after sending an error response."""
        length_text = self.headers.get("Content-Length", "")
        if not length_text.isdigit():
            self.send_error(411, "Content-Length required")
            return None
        if int(length_text) > MAX_FORM_BYTES:
            self.send_error(413, "Form too large")
            return None
        body = self.rfile.read(int(length_text))
        try:
            return parse_qs(body.decode("utf-8"))
        except UnicodeDecodeError:
            self.send_error(400, "Form is not UTF-8")
            return None

    def send_html(self, status, html):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        if not self.server.quiet:
            super().log_message(format, *args)


def main():
    try:
        port, data_dir, today = load_config(os.environ)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    server = ReminderServer(("", port), data_dir, today)
    print(f"Serving on http://localhost:{port}/ (today {today}, data from {data_dir})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
