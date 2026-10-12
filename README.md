# Payment reminder assistant

Python 3.11+, standard library only (nothing to install). Run everything from inside `python/`.

- **Tests:** `python -m unittest` (99 tests: rules, CLI, messages, page rendering, and a real HTTP server).
- **Command:** `python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json`
  Exit 0 on success; 1 if a file cannot be read or is not a JSON list; 2 for a bad `--today` or missing argument.
- **Page:** `python app.py`, then open http://localhost:8000/. Uses `PORT` (8000), `DATA_DIR` (`../data`) and `TODAY` (real date).

Layout: `plan.py` rules engine and CLI · `messages.py` reminder text · `page.py` HTML · `app.py` server · `tests/`.

## Decisions

- Strict input checks: dates must match `YYYY-MM-DD` exactly and be real; `true`, strings, `NaN` and amounts <= 0 are not valid amounts.
- Bad values inside an invoice are reported in `skipped` and the run exits 0; only an unusable file (unreadable, invalid JSON, not a list, invoice without a text id) is an error.
- Step thresholds live in one table (`STEPS`); "highest step reached, unless that or a higher step was sent" is a rank comparison.
- The page calls `load_inputs` and `build_plan` on every request, so it uses the real engine and always shows the current files.
- Approve/reject are plain HTML forms (keyboard friendly, no JavaScript), kept in memory per `(invoice, step)`, so approving `firm` never approves a later `final`. The server only accepts decisions for firm/final reminders that are in today's plan.
- Messages use fixed templates, not an AI model: they work offline, and `message_problems()` checks that each message has the required facts and no other figure.
- Research answers use only `sources/`; the owner's note is treated as claims to check, not evidence.

## Next steps with more time

- Save decisions to a file so they survive a restart, and record who decided and when.
- Optional AI-written messages behind an API key, always checked with `message_problems()` and falling back to the template.
- Let the owner choose the date on the page, and add a CSRF token if the page is ever exposed beyond localhost.
