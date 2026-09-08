# Finance Analyst Assistant

I built this prototype for Keyrus's Meridian Instruments challenge. My goal is to make the financial answer easy to check: what was counted, which convention was used, and what information is missing.

Gemini selects one financial operation from the question. Python and Pandas do the calculations, and Streamlit displays the result, caveats and a run trace. I used AI to develop this project; my choices, checks and limitations are described in [NOTES.md](NOTES.md).

## Current validation

The following results come from my latest local Windows run with Python 3.13.0. They are reported terminal results, not a CI run or a guarantee that every code path is correct.

| Check | Result |
|---|---|
| `python -m pytest` | 9 passed in 111.75 seconds; no warnings listed in that run. |
| `python evals/run.py --data .` | 8/8 deterministic evaluations passed. |
| `python evals/run.py --data . --integrated` | Incomplete: Gemini returned `503 UNAVAILABLE` due to high demand before any case reported a pass. |
| Streamlit startup | Started locally; this is not evidence of a successful model-backed analysis. |

The earlier missing-key failure is addressed in the runner: it loads `.env` and checks `GEMINI_API_KEY`. The later 503 response is a provider availability error. I have not counted the integrated suite as passed. See [Google's troubleshooting guidance](https://ai.google.dev/gemini-api/docs/troubleshooting).

## Run on Windows

Clone this repository or download and unzip it. Open PowerShell in the folder containing `app.py`, `pyproject.toml` and the CSV files. If the folder name contains spaces, opening PowerShell from File Explorer's address bar avoids path quoting issues.

The project declares Python 3.11 through 3.14; the run reported above used Python 3.13.0. Other versions and operating systems have not been verified in that run. From the repository folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

If Python is not installed, install a compatible version from [python.org](https://www.python.org/downloads/). Use the matching version in the environment-creation command. Recreate the environment after moving to a newly downloaded copy; do not copy `.venv` between folders.

Get your own key from [Google AI Studio](https://aistudio.google.com/app/apikey). In the private `.env` next to `app.py`, set:

```dotenv
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-flash-latest
MAX_AGENT_STEPS=4
MAX_OUTPUT_TOKENS=2048
```

Save it as `.env`, not `.env.txt`. Keep `.env.example` key-free and never commit `.env`. The model is configurable; this alias is the current project default, not a promise of availability or fixed pricing. Check the [official model documentation](https://ai.google.dev/gemini-api/docs/models) for a compatible model available to your account.

Start the application:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Keep the terminal open while using the app; `Ctrl+C` stops it. Use a second terminal in the same repository folder for checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe evals\run.py --data .
.\.venv\Scripts\python.exe evals\run.py --data . --integrated
```

The first two commands run without Gemini credentials. The third makes API requests using the evaluator's key and can incur usage charges. A provider error is not a successful evaluation. The current integrated runner still stops on an unhandled provider error; it does not yet produce a complete per-case error report.

## macOS / Linux

With a compatible Python installed, run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
[ -f .env ] || cp .env.example .env
# Edit .env locally and set GEMINI_API_KEY before starting the app.
python -m streamlit run app.py
```

Use `python -m pytest`, `python evals/run.py --data .`, and `python evals/run.py --data . --integrated` for the same checks. The separate standard-library calculation script is `python evals/reference_check.py`; it must run from the repository root and does not import application code.

## Data and conventions

The five synthetic CSVs and four internal Markdown documents supplied for the challenge are in the repository root. The sidebar's data-folder setting accepts a folder with the same five CSV filenames and required columns. The numerical expectations in `evals/questions.json` belong to the supplied Meridian dataset; they are not expected to match a different dataset.

- Analytical periods use `accrual_date`; credits reduce spend.
- Account classification follows the chart's effective dates.
- Q2 OPEX is grouped by cost centre and original currency, without adding unlike currencies.
- USD conversion multiplies amounts by the supplied monthly `rate_to_usd`. Missing rates are not imputed.
- Budget comparison maps `OPS-NA` actuals to the restated `OPS-AMER` centre.
- Consolidated spend means net operating-expense entries across entities, not cash payments. Vendor rankings use vendor-tagged ledger entries.
- A quarter without a year currently defaults to the maximum accrual year in the ledger. The code does not establish that this year is complete; specify a year to avoid this ambiguity.

| Challenge question | Current deterministic result |
|---|---|
| Q2 operating expenses by cost centre | Supported, with separate currency rows. |
| Travel spend in 2024 versus 2023 | Partial: missing FX and a disclosed classification change. |
| Q3 consolidated spend in USD | Partial: known-rate subtotal, not a complete total. |
| Ten largest vendors | Partial: ranking can change when missing FX is supplied. |
| Q3 cost centres against budget and drivers | Partial: missing FX affects the comparison. |
| Possible T&E policy breaches | Partial: recorded approval-threshold candidates; other rules need more detail. |
| Headcount cost per FTE | Insufficient data: the HR denominator is absent. |
| Duplicate payments | Candidate ledger pairs only; payment duplication is not established. |

## Evidence and traces

The UI shows result tables, conventions, warnings, missing information and source filenames/section references. Completed assistant runs write `traces/<run-id>.json` with the model selection, arguments, token counts reported by the API, tool status, row count, sources and elapsed time.

At present, a trace summarizes the result rather than storing all calculated values. It has no cost estimate, and failed provider calls are not persisted by the application. There are no committed real Gemini sample runs yet. The example below shows only the intended event shape; it is illustrative, not an executed trace:

```json
{
  "question": "What's our headcount cost per FTE?",
  "events": [
    {"type": "model_route", "tool": "headcount_cost_per_fte", "arguments": {}},
    {"type": "tool_result", "status": "insufficient_data", "sources": ["board_memo_2024_q2.md#5-headcount"]}
  ]
}
```

## Limits and remaining work

The missing `EUR / 2024-09` rate, absent HR denominator and absent payment records are data limitations. Similar vendor names are kept separate without evidence of a canonical identity. T&E checks cannot establish hotel, flight, meal or approval-timing compliance from the existing ledger fields.

The current implementation also has engineering limitations identified in review:

- Documents are referenced by fixed source labels; their contents are not passed to Gemini or displayed as retrieved evidence during a run.
- Evals check statuses and selected numerical expectations. They do not yet enforce all declared sources, missing-data explanations or driver expectations.
- Budget-year availability is fixed to 2024, and budget-only rows need correct retention after the actual/budget join.
- Duplicate candidate selection currently excludes equal document references and needs broader, explicit evidence rules.
- The Pydantic route definition is not yet applied before dispatch. Full argument validation remains to be wired in.
- Provider-error handling, complete result traces, reviewed sample traces and cost/budget controls remain unfinished.

There is no hosting, authentication, conversational memory, vector search, arbitrary SQL or unrestricted code execution. These were deliberate scope choices. See [ARCHITECTURE.md](ARCHITECTURE.md) for the design; the implementation status recorded here takes precedence over unverified design claims.

## Files to review

| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface. |
| `src/finance_assistant/data.py` | CSV loading and column checks. |
| `src/finance_assistant/tools.py` | Financial calculations and evidence conventions. |
| `src/finance_assistant/orchestrator.py` | Gemini routing and trace writing. |
| `evals/` | Eight questions, runner and separate reference calculations. |
| `tests/` | Local tool tests. |
| `ARCHITECTURE.md` | Architecture and design rationale. |
| `NOTES.md` | My development choices, observed issues and validation. |
