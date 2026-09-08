# Finance Analyst Assistant

A reviewable Streamlit prototype for Meridian Instruments. Gemini interprets a question and chooses one bounded tool; Python/Pandas performs every financial calculation and returns evidence, caveats, and a trace.

## Windows setup (PowerShell)

You do **not** edit `.env.example` directly. It is a safe template committed to Git. Copy it to a new file named `.env`, then put your key in that private copy. `.env` is intentionally absent from a downloaded repository because committing credentials would be unsafe.

### 1. Open the correct folder

1. Download and unzip the repository.
2. Open the unzipped folder in File Explorer—the folder that contains `app.py`, `README.md`, and the CSV files.
3. Click the File Explorer address bar, type `powershell`, and press Enter.

Create `.env` **inside that unzipped repository folder**, next to `app.py` and `.env.example`. Do not create it on the GitHub website, in Downloads outside the unzipped folder, or inside `.venv`.

The PowerShell prompt should now end with the repository folder name. Confirm it with:

```powershell
Get-ChildItem app.py, README.md, gl_transactions.csv
```

If all three names appear, you are in the correct place.

### 2. Check Python

Install Python 3.12 from [python.org](https://www.python.org/downloads/) if this command does not print a Python version:

```powershell
py -3.12 --version
```

During Python installation, enable **Add Python to PATH** if offered.

### 3. Create the environment

Copy and paste these commands one at a time:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

The conditional copy creates `.env` only when it does not already exist, so rerunning setup cannot overwrite a key. It is created beside `app.py` because PowerShell is already in the repository folder. If Windows hides dot-files, `notepad .env` still opens it.

Notepad will open the private `.env` file. Replace only `paste_your_key_here`:

```dotenv
GEMINI_API_KEY=your_real_gemini_key
```

Get a key through [Google AI Studio](https://aistudio.google.com/app/apikey). Do not add quotes or spaces around it, do not share it, and never upload `.env` to GitHub.

Save the file and close Notepad.

If you created `.env` from an older version of this repository, change its model line to:

```dotenv
GEMINI_MODEL=gemini-flash-latest
```

The `404 NOT_FOUND` message saying that `gemini-2.5-flash` is unavailable means the key was read correctly, but that model is not available for the account. The configurable `gemini-flash-latest` alias is now the project default.

### 4. Start the application

In the same PowerShell window, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit should open a browser tab. Keep PowerShell open while using the application. Stop it later with `Ctrl+C`.

### 5. Run checks

Open a second PowerShell window in the same folder, or stop Streamlit first, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe evals\run.py --data .
.\.venv\Scripts\python.exe evals\run.py --data . --integrated
```

The first two checks do not call Gemini. The integrated check uses your API key and may incur API usage.

The integrated runner reads `.env` automatically. If the key is missing, it stops with a short setup message instead of a Python `KeyError` traceback.

## macOS/Linux quick start

Python 3.11–3.14 is supported.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
# Add your GEMINI_API_KEY to .env
streamlit run app.py
```

The default data folder is the repository root. In the sidebar, select any other folder containing the same five CSV filenames and columns. Internal Markdown documents in that folder are available as cited evidence. Never commit `.env`.

## Environment variables

| Variable | Required | Meaning |
|---|---:|---|
| `GEMINI_API_KEY` | Yes | Private credential from Google AI Studio. |
| `GEMINI_MODEL` | No | Function-calling model name; defaults to `gemini-flash-latest`. |
| `MAX_AGENT_STEPS` | No | Maximum routing/tool steps. |
| `MAX_OUTPUT_TOKENS` | No | Maximum model output tokens. |
| `GEMINI_MAX_ATTEMPTS` | No | Total SDK attempts, 1–3 (default 3). |
| `GEMINI_TIMEOUT_SECONDS` | No | Per-attempt HTTP timeout (default 15). |
| `MAX_RUN_SECONDS` | No | Maximum configured request/retry envelope (default 60). |
| `MAX_ESTIMATED_COST_USD` | No | Post-call estimated-cost ceiling when the concrete model has an identified price (default 0.02). |

The integration uses Google's current `google-genai` SDK (`from google import genai`) and manual function calling. `GEMINI_MODEL` is configurable and must name a model that supports function calling. The default is a configurable starting value, not a guarantee of future availability. Check the [official model documentation](https://ai.google.dev/gemini-api/docs/models) before evaluation.

## Evaluation and tests

```bash
# Eight deterministic tool evaluations; no API key
python evals/run.py --data .

# Unit tests; no API key
pytest

# Independent stdlib reference calculations; no application imports
python evals/reference_check.py

# Eight end-to-end Gemini routing evaluations; uses evaluator credentials
python evals/run.py --data . --integrated
```

`evals/questions.json` contains the exact challenge questions, expected status, evidence, independently checked Meridian fixture values, and refusal/partial-answer conditions. The integrated run checks routing plus calculations; it does not weaken expectations when Gemini fails. A persistent provider/configuration failure is reported as `BLOCKED`, remaining API calls are skipped, and the process exits with code 2.

## What the UI shows

- supported, partial, clarification, or insufficient-data status;
- result tables and explicit period/currency/sign conventions;
- calculation method, transaction/document evidence, warnings, and missing fields;
- bounded steps, elapsed time, nullable API usage fields, and a sourced estimate only for a concrete priced model;
- relevant document excerpts, applied filters, transaction evidence, and a CSV evidence download.

A trace is saved to `traces/<run-id>.json`, including failed runs. It contains the complete structured result, routing/tool arguments, sanitized errors, requested/reported model, duration, nullable usage, and configured limits. It excludes API keys and private chain-of-thought. Three reviewed deterministic examples are committed under `traces/samples/`; each says `model_called: false` and does not invent tokens or API success. Regenerate them with `python evals/generate_samples.py`.

## Dataset conventions

- `accrual_date` defines analytical period; `posting_date` is retained as transaction evidence.
- Expense signs are preserved; credit memos reduce spend.
- Chart classifications are joined where accrual date falls within `valid_from`/`valid_to`.
- Monthly `rate_to_usd` multiplies a local amount. It is used only for requested USD consolidation/comparison, not extrapolated from the T&E policy.
- USD results use decimal arithmetic and round half-up to two decimals at presentation.
- “Spend” means net operating-expense ledger entries, not cash payments. Vendor rankings use vendor-tagged entries.
- For quarter-only questions, the router uses the latest year with ledger transactions in all 12 calendar months. If none exists, it asks for an explicit year.

## Known limitations

- `EUR / 2024-09` has no FX row. Affected USD analyses return partial known-rate subtotals and name the missing rate; rankings and variances may change.
- The ledger contains accounting entries, not invoice and payment status. Duplicate output distinguishes repeated document references from similar entries, but never claims a duplicate invoice or payment.
- T&E details such as nights, city, tax, flight duration/class, travel days, attendees, and approval timing are absent. Only the recorded pre-approval threshold can be screened.
- FTE data is explicitly held outside finance, so cost per FTE is refused.
- Similar vendor names are not merged without a canonical relationship.
- There is no conversational memory, authentication, deployment, arbitrary SQL/code execution, or causal inference from numerical movements.

## Repository map

```text
app.py                         Streamlit UI
src/finance_assistant/data.py Schema validation and loading
src/finance_assistant/tools.py Deterministic financial tools
src/finance_assistant/orchestrator.py Gemini router, limits, traces
evals/                         Eight challenge evaluations
tests/                         Local risk-focused tests
traces/samples/                Reviewed deterministic trace examples
ARCHITECTURE.md                Control and design boundary
NOTES.md                       Candidate development notes
```
