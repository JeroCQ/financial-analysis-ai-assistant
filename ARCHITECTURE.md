# Architecture

## Boundary

I built this as a bounded router, not an open-ended agent. Gemini receives the question, the four short internal documents in delimited untrusted blocks, and a fixed function schema. It must select exactly one tool. Pydantic rejects missing, extra, or out-of-range arguments before dispatch. The model never receives the ledger and never calculates a financial number.

Known workflows stay deterministic. `DataRepository` checks the five CSV schemas and loads only the four allowed internal Markdown filenames from either the selected data directory or `docs/`. `FinanceTools` owns dated classification, period selection, signs, FX conversion, aggregation, policy screening, and evidence rows. I did not add LangChain, SQL execution, a vector store, or multiple agents because these eight paths are small and known.

## Financial controls

The analytical date is `accrual_date`; `posting_date` remains evidence. Account classification must match exactly one effective chart row. Credits keep their sign. USD conversion multiplies by the matching monthly `rate_to_usd`; a missing rate produces a partial result and never becomes zero.

Budget availability comes from `period_month`, not a hard-coded year. The tool requires USD-only budget rows, retains budget-only and actual-only rows after its outer join, and maps OPS-NA to OPS-AMER only for the documented restated-plan comparison. A centre with missing actual FX exposes a known-rate subtotal but no confirmed actual or variance. Duplicate review includes same and different document references, emits each pair once, and keeps ledger candidates separate from invoice and payment conclusions. A requested period without ledger coverage is insufficient data, not a supported zero.

For an omitted year, the router uses the latest year containing transactions in every calendar month. If no such year exists, it does not claim that the maximum year is complete.

## Gemini controls

A run permits one routing request and one tool call. The SDK owns transient retries; there is no second retry loop. Defaults are three total SDK attempts, a 15-second HTTP timeout, exponential backoff with jitter, and a 60-second total policy ceiling. Startup validation rejects settings whose worst-case request and delay budget exceeds that ceiling. Provider unavailability, credential/configuration failure, clarification, and insufficient financial data have different result states. All failures are sanitized and traced.

The token ceiling is checked before the request. Traces preserve nullable prompt, output, total, cache, thought, and tool-use token fields exactly as reported. Cost is estimated only when a concrete reported/requested model has an identified price entry; aliases remain unpriced rather than guessed. The estimate includes its model, rates, official pricing URL, check date, and an explicit statement that it is not an invoice.

## Evidence

Each result contains its complete structured data, status, conventions, warnings, missing information, sources, filters, relevant document excerpts, and a bounded transaction-evidence view. Streamlit displays these and offers evidence as CSV. Local traces are ignored; `traces/samples/` contains reviewed tool-only examples for supported, partial, and insufficient-data outcomes. Credentials and hidden reasoning are never stored.
