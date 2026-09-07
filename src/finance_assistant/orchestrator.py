from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from .models import Route, ToolResult
from .tools import FinanceTools


ROUTER_PROMPT = """You route finance questions to one bounded calculation tool.
Return one function call only. Infer ordinary periods (Q1-Q4) and years from the question.
Do not calculate or answer. When a quarter has no year, use {default_year}, the latest complete accrual year in the loaded ledger; the UI discloses this convention.
Tools have these meanings: operating_expenses requires year+quarter; travel_comparison defaults to 2024;
consolidated_spend requires year+quarter; largest_vendors defaults to 10; budget_variance requires year+quarter;
travel_policy_review, headcount_cost_per_fte, and duplicate_payment_review take no parameters.
"""

DECLARATIONS = [
    {"name": "operating_expenses", "description": "Operating expenses by cost centre.", "parameters": {"type": "OBJECT", "properties": {"year": {"type": "INTEGER"}, "quarter": {"type": "INTEGER"}}, "required": ["year", "quarter"]}},
    {"name": "travel_comparison", "description": "Compare travel spend with the prior year.", "parameters": {"type": "OBJECT", "properties": {"year": {"type": "INTEGER"}, "quarter": {"type": "INTEGER"}}}},
    {"name": "consolidated_spend", "description": "Consolidated operating spend in USD.", "parameters": {"type": "OBJECT", "properties": {"year": {"type": "INTEGER"}, "quarter": {"type": "INTEGER"}}, "required": ["year", "quarter"]}},
    {"name": "largest_vendors", "description": "Largest vendors by net spend.", "parameters": {"type": "OBJECT", "properties": {"limit": {"type": "INTEGER"}}}},
    {"name": "budget_variance", "description": "Worst cost centres versus budget and account drivers.", "parameters": {"type": "OBJECT", "properties": {"year": {"type": "INTEGER"}, "quarter": {"type": "INTEGER"}}, "required": ["year", "quarter"]}},
    {"name": "travel_policy_review", "description": "Find supported T&E policy breach candidates.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "headcount_cost_per_fte", "description": "Calculate or refuse headcount cost per FTE.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "duplicate_payment_review", "description": "Review possible duplicate payments.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "clarify", "description": "Required parameters or intent are missing.", "parameters": {"type": "OBJECT", "properties": {"rationale": {"type": "STRING"}}, "required": ["rationale"]}},
]


@dataclass
class RunOutput:
    result: ToolResult
    trace: dict[str, Any]


class Assistant:
    def __init__(self, tools: FinanceTools, trace_dir: str | Path = "traces", model: str | None = None):
        self.tools = tools
        self.trace_dir = Path(trace_dir)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_steps = int(os.getenv("MAX_AGENT_STEPS", "4"))
        self.max_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))

    def _route(self, question: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model=self.model,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=ROUTER_PROMPT.format(default_year=int(self.tools.repo.gl.accrual_date.dt.year.max())),
                tools=[types.Tool(function_declarations=DECLARATIONS)],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
                max_output_tokens=self.max_tokens,
                temperature=0,
            ),
        )
        calls = response.function_calls or []
        if len(calls) != 1:
            raise ValueError("Router must return exactly one tool call")
        usage = response.usage_metadata
        prompt = int(getattr(usage, "prompt_token_count", 0) or 0)
        output = int(getattr(usage, "candidates_token_count", 0) or 0)
        return calls[0].name, dict(calls[0].args or {}), {"prompt_tokens": prompt, "output_tokens": output}

    def run(self, question: str) -> RunOutput:
        started = time.perf_counter()
        trace: dict[str, Any] = {"run_id": str(uuid.uuid4()), "question": question, "model": self.model, "limits": {"steps": self.max_steps, "output_tokens": self.max_tokens}, "events": []}
        name, args, usage = self._route(question)
        trace["events"].append({"type": "model_route", "tool": name, "arguments": args, "usage": usage})
        if name == "clarify":
            result = ToolResult(status="needs_clarification", summary=args.get("rationale", "Please provide the missing period or scope."))
        else:
            if self.max_steps < 2:
                raise ValueError("MAX_AGENT_STEPS must allow routing and one tool")
            result = self.tools.dispatch(name, **args)
            trace["events"].append({"type": "tool_result", "tool": name, "arguments": args, "status": result.status, "summary": result.summary, "rows": len(result.data), "sources": result.sources, "warnings": result.warnings})
        trace["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        trace["result_status"] = result.status
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        (self.trace_dir / f"{trace['run_id']}.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
        return RunOutput(result=result, trace=trace)
