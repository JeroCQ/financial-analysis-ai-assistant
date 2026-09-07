# Architecture

## Boundary

The assistant is a bounded router, not an open-ended agent. Gemini receives the question and a fixed function schema, then chooses exactly one tool and validated arguments. This is useful for normal variations in wording, dates, quarters, limits, and intent. It cannot execute Python, SQL, filesystem paths, or arbitrary retries. Tool output—not model prose—is the answer, so the model never performs financial arithmetic or invents a source.

Known paths stay deterministic. Each tool loads schema-validated files, applies dated joins and filters, computes, and returns a typed `ToolResult`. A run is at most one routing call plus one tool call. `MAX_AGENT_STEPS` and `MAX_OUTPUT_TOKENS` are hard configuration ceilings. The tool allow-list is enforced in `dispatch`; Pydantic constrains states and route concepts. The current implementation intentionally does not use a planner/executor loop or multiple agents: none of the eight workflows benefits enough to justify added latency, cost, and failure modes.

## Tools

- **Operating expenses:** dated chart classification and cost-centre/local-currency aggregation.
- **Travel comparison:** dated Travel & Entertainment membership, monthly FX, prior/current arithmetic.
- **Consolidated spend:** all entities and operating-expense accounts, monthly conversion to USD.
- **Largest vendors:** net vendor-tagged ledger entries, master names, bounded ranking.
- **Budget variance:** 2024 actual/budget alignment, OPS-NA → OPS-AMER reporting map, top account drivers.
- **T&E review:** screens only the threshold and recorded approval fields that exist; lists missing evidence for other rules.
- **FTE:** an explicit insufficiency response because the denominator is absent.
- **Duplicate review:** conservative candidate pairs; refuses to convert ledger similarity into a payment claim.

Documents are full, small local sources identified by filename and Markdown section. Deterministic tools cite only relevant sections. The ledger is never sent to Gemini. Numerical “drivers” are observed account variances; the tooling-failure explanation remains separately attributed to the board memo rather than presented as inferred causality.

## Data controls

Analytical periods use `accrual_date`; `posting_date` is evidence, not the period selector. A many-to-many join against the chart is reduced by effective dates and must classify every transaction exactly once. Credits retain their sign. Monetary values and FX rates use `Decimal`; only display values are rounded, half-up, to two decimals. The budget is supplied in USD, while actuals use monthly rates. Missing FX changes status to partial and is named instead of being imputed.

OPS-NA actuals are mapped to OPS-AMER only for budget comparison, based on the memo and restated plan. Prior-year records are not mutated. “Consolidated spend” is explicitly defined as net Operating Expenses across all entities—not cash paid. This prevents conflating journal entries, invoices, and payments.

## Evidence and observability

Every result carries status, rows, sources, warnings, missing information, and conventions. JSON traces record the question, short operational decision, arguments, summarized tool result, duration, and token usage reported by Gemini. Credentials and hidden reasoning are never recorded.
