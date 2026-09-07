# Development notes — review draft

This is a fact-based draft to rewrite in the candidate's own voice before submission.

## AI use and checks

OpenAI Codex was used to inspect the files, propose the architecture, write the implementation and tests, and draft documentation. Its output was checked against direct CSV inspection and a separate standard-library reference script (`csv`, `Decimal`, and explicit joins), rather than treating implementation output as its own oracle. The Gemini integration follows Google's `google-genai` API shape and keeps the selected model configurable.

One useful result was the separation between interpretation and arithmetic: Gemini only selects from a small function contract, while deterministic tools preserve signs, dates, classifications, and evidence. This makes local evaluation possible without credentials and makes a routing failure distinguishable from a calculation failure.

## Correction observed

The first calculation attempt implicitly expected a complete 24-month × 3-currency FX grid. The independent reference script failed on `EUR / 2024-09`, revealing that the 71-row FX file intentionally lacks one of 72 combinations. The design was corrected so affected results are partial, expose known-rate subtotals, and name the missing rate rather than imputing or crashing.

No model mistake had to be corrected repeatedly during this recorded implementation session. I have deliberately not invented one to satisfy that prompt; this is a point the candidate should discuss honestly if their own later review or Gemini evaluation produces a recurring issue.

## Scope choices

Cut deliberately: authentication, deployment, database/vector store, LangChain, conversational memory, arbitrary querying, vendor entity-resolution guesses, and model-written final narratives. There are no separate agents because each workflow is known and bounded. Full documents are small enough to cite directly; CSV computation belongs in tools.

Elapsed working time was not instrumented from the beginning, so this draft does not claim a number. Before submission, the candidate should replace this sentence only with a defensible personal estimate. With two more days, priorities would be: test against a second schema-compatible dataset, execute and review all Gemini routes, add explicit invoice/payment inputs, add richer T&E evidence fields, and improve the UI with reviewed screenshots and downloadable traces.

## Remaining validation

The local environment could not download project dependencies because its package-index proxy returned HTTP 403. Syntax-only checks can still run, but pytest, Streamlit startup, and Gemini integration must be executed in an environment where dependencies install and the evaluator supplies `GEMINI_API_KEY`. No successful API run or UI screenshot should be claimed until that happens.
