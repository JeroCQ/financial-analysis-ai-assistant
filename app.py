import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from finance_assistant.data import DataRepository
from finance_assistant.orchestrator import Assistant
from finance_assistant.tools import FinanceTools

load_dotenv()
st.set_page_config(page_title="Finance Analyst Assistant", page_icon="📊", layout="wide")
st.title("Finance Analyst Assistant")
st.caption("Source-grounded analysis for Meridian Instruments")

with st.sidebar:
    st.header("Run settings")
    folder = st.text_input("Data folder", value=".")
    st.text_input("Gemini model", value=os.getenv("GEMINI_MODEL", "gemini-flash-latest"), key="model")
    st.caption("The API key is read from GEMINI_API_KEY and is never displayed or traced.")

examples = [
    "What did we spend on operating expenses in Q2 2024, by cost center?",
    "How did travel spend in 2024 compare to 2023?",
    "Which transactions look like they breached our T&E policy?",
    "What's our headcount cost per FTE?",
]
question = st.text_area("Question", placeholder=examples[0])
st.caption("Examples: " + " · ".join(examples))

if st.button("Analyze", type="primary", disabled=not question.strip()):
    try:
        repository = DataRepository(Path(folder))
        run = Assistant(FinanceTools(repository), model=st.session_state.model).run(question.strip())
        result = run.result
        labels = {"supported": "Supported answer", "partial": "Partial answer", "needs_clarification": "Needs clarification", "insufficient_data": "Insufficient financial data", "provider_unavailable": "Gemini unavailable", "configuration_error": "Configuration error"}
        st.subheader(labels[result.status])
        st.write(result.summary)
        if result.data:
            st.dataframe(pd.json_normalize(result.data), width="stretch", hide_index=True)
        left, right = st.columns(2)
        with left:
            st.markdown("#### How this was calculated")
            st.json(result.conventions or {"note": "No calculation performed"})
            if result.warnings:
                st.markdown("#### Warnings")
                for warning in result.warnings:
                    st.warning(warning)
        with right:
            st.markdown("#### Evidence")
            for source in result.sources:
                st.code(source)
            for document in result.evidence.get("documents", []):
                with st.expander(f"{document['source']} — {document['section']}"):
                    st.markdown(document["text"])
            if result.missing:
                st.markdown("#### Missing information")
                for item in result.missing:
                    st.write(f"- {item}")
        transactions = result.evidence.get("transactions", [])
        if transactions:
            st.markdown("#### Transaction evidence")
            transaction_frame = pd.DataFrame(transactions)
            st.dataframe(transaction_frame, width="stretch", hide_index=True)
            st.download_button("Download evidence CSV", transaction_frame.to_csv(index=False), "transaction_evidence.csv", "text/csv")
        if result.evidence.get("filters"):
            st.markdown("#### Applied filters")
            st.json(result.evidence["filters"])
        usage = run.trace["events"][0]["usage"]
        st.markdown("#### Run trace")
        st.write({"steps": len(run.trace["events"]), "duration_ms": run.trace["duration_ms"], **usage})
        st.json(run.trace)
    except KeyError as exc:
        st.error(f"Missing credential: {exc}. Add GEMINI_API_KEY to your environment or .env file.")
    except Exception as exc:
        st.error(f"Run failed: {exc}")
