"""Tests that run the real command, as the graders will."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from plan import InputError, load_inputs
from tests.helpers import make_invoice

PLAN_PY = Path(__file__).resolve().parents[1] / "plan.py"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "actions.json"

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    def run_plan(self, invoices, sent, today="2026-10-12", out=None):
        return subprocess.run(
            [sys.executable, str(PLAN_PY), "--invoices", str(invoices), "--sent", str(sent),
             "--today", today, "--out", str(out or self.out)],
            capture_output=True, text=True, timeout=30,
        )

    def test_sample_data_writes_plan(self):
        result = self.run_plan(DATA_DIR / "invoices.json", DATA_DIR / "sent.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(list(plan), ["today", "actions", "skipped"])
        self.assertEqual(plan["today"], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 5)
        self.assertEqual(len(plan["skipped"]), 3)

    def test_empty_lists(self):
        result = self.run_plan(self.write("i.json", []), self.write("s.json", []))
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(plan, {"today": "2026-10-12", "actions": [], "skipped": []})

    def test_bad_data_inside_invoices_still_exits_0(self):
        invoices = [make_invoice("A", amount="x"), make_invoice("B", due_date=None), make_invoice("A")]
        result = self.run_plan(self.write("i.json", invoices), self.write("s.json", []))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_today(self):
        for today in ["2026-02-30", "12/10/2026", "", "tomorrow"]:
            with self.subTest(today=today):
                result = self.run_plan(DATA_DIR / "invoices.json", DATA_DIR / "sent.json", today=today)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--today", result.stderr)
                self.assertFalse(self.out.exists())

    def test_missing_file(self):
        result = self.run_plan(self.dir / "nope.json", DATA_DIR / "sent.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot read", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_json(self):
        result = self.run_plan(self.write("i.json", "[{"), DATA_DIR / "sent.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unwritable_output(self):
        out = self.dir / "missing-folder" / "actions.json"
        result = self.run_plan(DATA_DIR / "invoices.json", DATA_DIR / "sent.json", out=out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot write", result.stderr)

    def test_missing_argument(self):
        result = subprocess.run([sys.executable, str(PLAN_PY), "--today", "2026-10-12"],
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)


class LoadInputsTest(unittest.TestCase):
    """The file shape checks, without starting a process."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, content):
        path = self.dir / name
        path.write_bytes(content if isinstance(content, bytes) else json.dumps(content).encode("utf-8"))
        return path

    def assert_input_error(self, invoices, sent, expected_text):
        with self.assertRaises(InputError) as caught:
            load_inputs(self.write("i.json", invoices), self.write("s.json", sent))
        self.assertIn(expected_text, str(caught.exception))

    def test_valid_files(self):
        invoices, sent = load_inputs(self.write("i.json", [make_invoice()]), self.write("s.json", []))
        self.assertEqual(len(invoices), 1)
        self.assertEqual(sent, [])

    def test_top_level_must_be_list(self):
        self.assert_input_error({"invoices": []}, [], "JSON list of invoices")
        self.assert_input_error([], {"a": 1}, "JSON list of sent reminders")

    def test_invoice_without_text_id(self):
        for invoice in ["INV-1", None, {}, {"id": 1001}, {"id": None}]:
            with self.subTest(invoice=invoice):
                self.assert_input_error([make_invoice(), invoice], [], "invoice number 2 has no text id")

    def test_not_utf8(self):
        self.assert_input_error(b"\xff\xfe[]", [], "not UTF-8")

    def test_empty_file(self):
        self.assert_input_error(b"", [], "not valid JSON")


if __name__ == "__main__":
    unittest.main()
