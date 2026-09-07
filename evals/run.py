from __future__ import annotations

import argparse
import json
from pathlib import Path

from finance_assistant.data import DataRepository
from finance_assistant.orchestrator import Assistant
from finance_assistant.tools import FinanceTools


def check(case: dict, result) -> list[str]:
    errors = []
    if result.status != case["expected_status"]:
        errors.append(f"status {result.status} != {case['expected_status']}")
    expected = case["expected"]
    if "row_count" in expected and len(result.data) != expected["row_count"]:
        errors.append(f"rows {len(result.data)} != {expected['row_count']}")
    if case["id"] == "opex_q2":
        values = {f"{r['cost_centre']}|{r['currency']}": r["amount"] for r in result.data}
        if values.get("OPS-NA|USD") != expected["OPS-NA|USD"]: errors.append("OPS-NA mismatch")
    elif case["id"] == "travel_yoy":
        for key in ("prior_usd", "current_usd"):
            if result.data[0][key] != expected[key]: errors.append(f"{key} mismatch")
    elif case["id"] == "consolidated_q3" and result.data[0]["amount_usd"] != expected["known_rate_subtotal_usd"]: errors.append("subtotal mismatch")
    elif case["id"] == "top_vendors" and (result.data[0]["vendor_id"] != expected["known_rate_leader"] or result.data[0]["spend_usd"] != expected["known_rate_leader_usd"]): errors.append("leader mismatch")
    elif case["id"] == "budget_q3" and (result.data[0]["cost_centre"] != expected["known_rate_worst"] or result.data[0]["unfavourable_variance_usd"] != expected["known_rate_variance_usd"]): errors.append("variance mismatch")
    elif case["id"] == "travel_policy" and len(result.data) != expected["known_missing_approval_candidates"]: errors.append("candidate count mismatch")
    elif case["id"] == "duplicates" and len(result.data) != expected["ledger_candidate_pairs"]: errors.append("candidate count mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=".")
    parser.add_argument("--integrated", action="store_true", help="Route exact questions through Gemini")
    args = parser.parse_args()
    cases = json.loads((Path(__file__).parent / "questions.json").read_text())
    tools = FinanceTools(DataRepository(args.data))
    failures = 0
    for case in cases:
        result = Assistant(tools).run(case["question"]).result if args.integrated else tools.dispatch(case["tool"], **case["arguments"])
        errors = check(case, result)
        failures += bool(errors)
        print(f"{'FAIL' if errors else 'PASS'} {case['id']}: {', '.join(errors) or result.status}")
    print(f"{len(cases) - failures}/{len(cases)} passed")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
