# Development notes

## What I wanted to build

I wanted an analyst to understand where a number came from and when the data was not enough to answer. I used ChatGPT to question the design choices and understand the financial terms, and Codex to develop the code, tests and documentation. I chose Gemini because I already use it and could set up the API credentials easily. I chose Streamlit to keep the interface and calculations in one Python project.

## What worked and what needed correction

Separating the model from the arithmetic was useful. Gemini selects an operation; Python calculates. I could therefore test the financial tools even when the model service was unavailable.

The missing September 2024 EUR rate was an important finding. A complete USD total would be misleading, so the implementation returns the subtotal it can calculate and identifies the missing rate. Similarly, ledger entries can suggest duplicate payments, but they cannot prove that two payments occurred.

My first integrated run stopped because the evaluation command did not have the API key available. The runner now loads the local .env and checks for the key. In my latest attempt, the request reached Gemini but returned 503 UNAVAILABLE with a high-demand message. That is a different failure, and it is still an incomplete integration test.

I also used an AI-assisted review to challenge the generated implementation. It found that the documents were cited by filename but were not actually being read during a run, and that passing the existing evals did not check every source and caveat. Those findings are listed in the README as remaining work. I do not have a documented example of repeatedly correcting the same model mistake, so I am not claiming one. For the issues found, the next step is to add specific regression checks.

## What I verified

On Windows with Python 3.13.0, my latest local run finished with 9 tests passed in 111.75 seconds and the eight deterministic evaluations passed. Streamlit also started locally. These checks do not establish that all eight questions work through Gemini: the latest integrated run stopped at the provider error before reporting any passed cases. The README records the current validation status and its limits.

## Scope, time and next steps

I left out hosting, authentication, a vector database, LangChain, conversational memory and unrestricted code execution. There are only four short internal documents, so a vector search pipeline did not justify its extra complexity. This choice does not remove the need to expose the actual documentary evidence.

I did not track active working hours, so I cannot give a reliable total. The test duration above is a measured test duration, not my development time.

With two more days, I would first finish the documented reliability fixes and run all eight questions through Gemini. Then I would test another dataset with the same columns, improve the evidence view, and define the invoice/payment and HR inputs needed to answer the questions the ledger cannot resolve.
