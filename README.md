# Finance Analyst Assistant

A reviewable Streamlit prototype for Meridian Instruments. Gemini interprets a question and chooses one bounded tool; Python/Pandas performs every financial calculation and returns evidence, caveats, and a trace.

## Quick start

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

The integration uses Google's current `google-genai` SDK (`from google import genai`) and manual function calling. `GEMINI_MODEL` is configurable and must name a model that supports function calling. The default is a configurable starting value, not a guarantee of future availability. Check the [official model documentation](https://ai.google.dev/gemini-api/docs/models) and [pricing page](https://ai.google.dev/gemini-api/docs/pricing) before evaluation.

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

`evals/questions.json` contains the exact challenge questions, expected status, evidence, independently checked Meridian fixture values, and refusal/partial-answer conditions. The integrated run checks routing plus calculations; it does not weaken expectations when Gemini fails.

## What the UI shows

- supported, partial, clarification, or insufficient-data status;
- result tables and explicit period/currency/sign conventions;
- calculation method, transaction/document evidence, warnings, and missing fields;
- bounded steps, elapsed time, actual API token counts, and estimated cost when current prices are configured.

A trace is saved to `traces/<run-id>.json`. It includes the question, brief routing decision, tool arguments, summarized result, sources, warnings, duration, usage, and configured ceilings. It excludes API keys and private chain-of-thought. Example shape:

```json
{
  "question": "What's our headcount cost per FTE?",
  "events": [
    {"type": "model_route", "tool": "headcount_cost_per_fte", "arguments": {}, "usage": {"prompt_tokens": 0, "output_tokens": 0, "estimated_cost_usd": null}},
    {"type": "tool_result", "status": "insufficient_data", "sources": ["board_memo_2024_q2.md#5-headcount"]}
  ]
}
```

The zero token values above only illustrate the schema; they are **not** represented as an executed Gemini run.

## Dataset conventions

- `accrual_date` defines analytical period; `posting_date` is retained as transaction evidence.
- Expense signs are preserved; credit memos reduce spend.
- Chart classifications are joined where accrual date falls within `valid_from`/`valid_to`.
- Monthly `rate_to_usd` multiplies a local amount. It is used only for requested USD consolidation/comparison, not extrapolated from the T&E policy.
- USD results use decimal arithmetic and round half-up to two decimals at presentation.
- “Spend” means net operating-expense ledger entries, not cash payments. Vendor rankings use vendor-tagged entries.
- For quarter-only questions, the router uses the latest complete accrual year in the loaded ledger and the output discloses the period.

## Known limitations

- `EUR / 2024-09` has no FX row. Affected USD analyses return partial known-rate subtotals and name the missing rate; rankings and variances may change.
- The ledger contains accounting entries, not invoice and payment status. Duplicate output is candidate review, never a duplicate-payment conclusion.
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
ARCHITECTURE.md                Control and design boundary
NOTES.md                       Fact-based development notes draft
```
