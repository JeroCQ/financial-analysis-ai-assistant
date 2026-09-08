# Development notes

## How I used AI

I used ChatGPT/Codex to inspect the files, draft code and tests, and challenge some assumptions. Gemini is only used at runtime to understand the question and select one allowed tool. Pandas and Python perform the calculations.

I did not accept generated totals as proof. I kept a separate reference script based on `csv` and `Decimal`, and I compared the tool outputs against the eight evaluation cases.

## What I corrected

The most important correction was missing FX. September 2024 has no EUR rate. An early reference calculation treated that gap like zero, which made the subtotal look complete. I changed both the tools and the independent check so they identify the missing pair and label affected answers as partial.

I also corrected the budget comparison. Budget-only rows could disappear because the outer join left the reporting cost-centre key empty. The final code fills the key from either side, keeps actual-only rows, and does not publish a confirmed variance for centres whose actuals have missing FX.

The Gemini integration reached the provider in my earlier Windows run, but it ended with `503 UNAVAILABLE` because of high demand. I did not count that as a passed integrated evaluation. The final code uses the SDK's bounded retry policy and stops the remaining integrated cases after a persistent infrastructure failure.

I did not record a repeated AI error during this work, so I am not inventing one. The repeated check I did enforce in code was that missing data must not become zero: focused tests now cover missing FX, missing periods, and one-sided budget rows.

## Scope and validation record

I left out authentication, deployment, a database, a vector store, LangChain, conversation memory, vendor-name guessing, and model-written financial narratives. The available documents are short, so full bounded context is simpler than retrieval infrastructure.

Before the final corrections, I ran this project on Windows with Python 3.13.0: 9 tests passed in 111.75 seconds without warnings, deterministic evaluations passed 8/8, Streamlit started, and the integrated run reached Gemini but stopped on a 503 before any case passed. Those results describe the earlier revision, not the final commit.

The total working time was not tracked from the start, so I cannot give a reliable number. With two more days I would test a second client-shaped dataset, run the integrated suite at a quieter time, and add real invoice/payment and HR inputs for the two questions the ledger cannot answer.
