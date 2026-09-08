"""Generate reviewed deterministic samples without calling Gemini."""
import json
from pathlib import Path

from finance_assistant.data import DataRepository
from finance_assistant.tools import FinanceTools

ROOT = Path(__file__).parents[1]
TOOLS = FinanceTools(DataRepository(ROOT))
CASES = {
    "numeric-supported.json": ("operating_expenses", {"year": 2024, "quarter": 2}),
    "partial-missing-fx.json": ("consolidated_spend", {"year": 2024, "quarter": 3}),
    "refusal-missing-fte.json": ("headcount_cost_per_fte", {}),
}
for filename, (tool, arguments) in CASES.items():
    result = TOOLS.dispatch(tool, **arguments)
    if "transactions" in result.evidence:
        result.evidence["transactions"] = result.evidence["transactions"][:5]
    sample = {
        "execution": "deterministic/tool-only",
        "model_called": False,
        "tokens": None,
        "cost": None,
        "tool": tool,
        "arguments": arguments,
        "result": result.model_dump(mode="json"),
    }
    (ROOT / "traces" / "samples" / filename).write_text(json.dumps(sample, indent=2), encoding="utf-8")
