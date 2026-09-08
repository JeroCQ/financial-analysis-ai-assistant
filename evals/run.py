from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from finance_assistant.data import DataRepository
from finance_assistant.orchestrator import Assistant
from finance_assistant.tools import FinanceTools

INFRASTRUCTURE = {"provider_unavailable", "configuration_error"}


def check(case: dict, result) -> list[str]:
    errors: list[str] = []
    if result.status != case["expected_status"]:
        errors.append(f"status {result.status} != {case['expected_status']}")
    for source in case["sources"]:
        if not any(item == source or item.startswith(source + "#") for item in result.sources):
            errors.append(f"missing source {source}")
    expected = case["expected"]
    if expected.get("missing") and not any(expected["missing"] in item for item in result.missing):
        errors.append(f"missing disclosure {expected['missing']}")
    if result.status == "partial" and not result.missing:
        errors.append("partial result does not disclose missing information")
    if case["id"] == "opex_q2":
        values = {f"{r['cost_centre']}|{r['currency']}": r["amount"] for r in result.data}
        if values != expected["rows"]:
            errors.append("cost-centre rows mismatch")
    elif case["id"] == "travel_yoy":
        for key in ("prior_usd", "current_usd", "difference_usd", "change_percent"):
            if result.data[0][key] != expected[key]:
                errors.append(f"{key} mismatch")
    elif case["id"] == "consolidated_q3" and result.data[0]["amount_usd"] != expected["known_rate_subtotal_usd"]:
        errors.append("subtotal mismatch")
    elif case["id"] == "top_vendors":
        actual = [{"vendor_id": row["vendor_id"], "spend_usd": row["spend_usd"]} for row in result.data]
        if actual != expected["rows"]:
            errors.append("vendor ranking mismatch")
    elif case["id"] == "budget_q3":
        worst = result.data[0]
        if worst["cost_centre"] != expected["known_rate_worst"] or worst["known_rate_variance_usd"] != expected["known_rate_variance_usd"]:
            errors.append("variance mismatch")
        if worst["top_drivers"][0]["account"] != expected["top_driver"]:
            errors.append("driver mismatch")
        if not any(not row["complete"] and row["actual_usd"] is None for row in result.data):
            errors.append("missing-FX centres appear complete")
    elif case["id"] == "travel_policy" and len(result.data) != expected["known_missing_approval_candidates"]:
        errors.append("candidate count mismatch")
    elif case["id"] == "fte" and not any("FTE" in item for item in result.missing):
        errors.append("FTE denominator not disclosed")
    elif case["id"] == "duplicates" and len(result.data) != expected["ledger_candidate_pairs"]:
        errors.append("candidate count mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=".")
    parser.add_argument("--integrated", action="store_true", help="Route exact questions through Gemini")
    args = parser.parse_args()
    load_dotenv()
    if args.integrated and not os.getenv("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY is missing. Create .env in the repository root and add your key.")
    cases = json.loads((Path(__file__).parent / "questions.json").read_text())
    tools = FinanceTools(DataRepository(args.data))
    failures = 0
    blocked = 0
    for index, case in enumerate(cases):
        result = Assistant(tools).run(case["question"]).result if args.integrated else tools.dispatch(case["tool"], **case["arguments"])
        if args.integrated and result.status in INFRASTRUCTURE:
            blocked = len(cases) - index
            print(f"BLOCKED {case['id']}: {result.summary}")
            for pending in cases[index + 1:]:
                print(f"BLOCKED {pending['id']}: not requested after infrastructure failure")
            break
        errors = check(case, result)
        failures += bool(errors)
        print(f"{'FAIL' if errors else 'PASS'} {case['id']}: {', '.join(errors) or result.status}")
    passed = len(cases) - failures - blocked
    print(f"Summary: {passed} passed, {failures} failed, {blocked} blocked")
    return 2 if blocked else int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
