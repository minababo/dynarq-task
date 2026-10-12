"""Tests for the page server: a real server on a free port, driven over HTTP."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from app import ReminderServer, load_config
from tests.helpers import TODAY, make_invoice


class LoadConfigTest(unittest.TestCase):
    def test_defaults(self):
        port, data_dir, today = load_config({})
        self.assertEqual(port, 8000)
        self.assertEqual(data_dir, Path("../data"))
        self.assertRegex(today, r"^\d{4}-\d{2}-\d{2}$")

    def test_values_from_environment(self):
        port, data_dir, today = load_config({"PORT": "9001", "DATA_DIR": "/tmp/x", "TODAY": "2026-10-12"})
        self.assertEqual((port, data_dir, today), (9001, Path("/tmp/x"), "2026-10-12"))

    def test_empty_today_means_real_date(self):
        self.assertRegex(load_config({"TODAY": ""})[2], r"^\d{4}-\d{2}-\d{2}$")

    def test_invalid_values(self):
        for environ in [{"PORT": "abc"}, {"PORT": "0"}, {"PORT": "70000"}, {"PORT": "-1"},
                        {"TODAY": "2026-02-30"}, {"TODAY": "12/10/2026"}]:
            with self.subTest(environ=environ):
                with self.assertRaises(ValueError):
                    load_config(environ)


class ServerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        self.write_data([
            make_invoice("INV-1", customer="Alder Ltd", due_date="2026-09-30"),  # firm
            make_invoice("INV-2", customer="Birch Ltd", due_date="2026-10-09"),  # friendly
            make_invoice("INV-3", due_date="2026-02-30"),                        # skipped
        ])
        self.server = ReminderServer(("127.0.0.1", 0), self.data_dir, TODAY, quiet=True)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                  daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def write_data(self, invoices, sent=()):
        (self.data_dir / "invoices.json").write_text(json.dumps(invoices), encoding="utf-8")
        (self.data_dir / "sent.json").write_text(json.dumps(list(sent)), encoding="utf-8")

    def get(self, path="/"):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8")

    def post(self, fields, path="/decision"):
        request = urllib.request.Request(self.base + path, data=urlencode(fields).encode("utf-8"))
        try:
            # urlopen follows the 303 redirect, so a success returns the page itself.
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8")

    def test_page_shows_plan_from_rules_engine(self):
        status, html = self.get()
        self.assertEqual(status, 200)
        for text in ["Alder Ltd", "Birch Ltd", "INV-3", "Firm reminder", "Friendly reminder"]:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_unknown_path_is_404(self):
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertEqual(self.post({}, path="/nope")[0], 404)

    def test_approve_then_undo(self):
        status, html = self.post({"invoice_id": "INV-1", "step": "firm", "decision": "approved"})
        self.assertEqual(status, 200)
        self.assertIn(">Approved</span>", html)
        self.assertEqual(self.server.decisions, {("INV-1", "firm"): "approved"})

        status, html = self.post({"invoice_id": "INV-1", "step": "firm", "decision": "undo"})
        self.assertEqual(status, 200)
        self.assertNotIn(">Approved</span>", html)
        self.assertEqual(self.server.decisions, {})

    def test_reject(self):
        status, html = self.post({"invoice_id": "INV-1", "step": "firm", "decision": "rejected"})
        self.assertEqual(status, 200)
        self.assertIn(">Rejected</span>", html)

    def test_decision_kept_between_page_loads(self):
        self.post({"invoice_id": "INV-1", "step": "firm", "decision": "approved"})
        self.assertIn(">Approved</span>", self.get()[1])

    def test_invalid_decisions_rejected(self):
        bad = [
            {"invoice_id": "INV-1", "step": "firm", "decision": "maybe"},     # unknown decision
            {"invoice_id": "INV-1", "step": "firm"},                          # missing decision
            {"invoice_id": "INV-1", "step": "final", "decision": "approved"}, # wrong step
            {"invoice_id": "INV-2", "step": "friendly", "decision": "approved"},  # needs no approval
            {"invoice_id": "INV-3", "step": "firm", "decision": "approved"},  # skipped invoice
            {"invoice_id": "INV-404", "step": "firm", "decision": "approved"},# not in data
        ]
        for fields in bad:
            with self.subTest(fields=fields):
                self.assertEqual(self.post(fields)[0], 400)
        self.assertEqual(self.server.decisions, {})

    def test_nothing_to_do(self):
        self.write_data([make_invoice("INV-1", due_date=TODAY)])
        status, html = self.get()
        self.assertEqual(status, 200)
        self.assertIn("Nothing to do today", html)

    def test_unreadable_data_shows_error_page(self):
        (self.data_dir / "invoices.json").write_text("[{", encoding="utf-8")
        status, html = self.get()
        self.assertEqual(status, 500)
        self.assertIn("could not be read", html)

    def test_missing_data_folder_shows_error_page(self):
        self.server.data_dir = self.data_dir / "missing"
        status, html = self.get()
        self.assertEqual(status, 500)
        self.assertIn("could not be read", html)

    def test_data_changes_show_without_restart(self):
        self.write_data([make_invoice("INV-5", customer="Copper Co", due_date="2026-09-30")])
        self.assertIn("Copper Co", self.get()[1])


if __name__ == "__main__":
    unittest.main()
