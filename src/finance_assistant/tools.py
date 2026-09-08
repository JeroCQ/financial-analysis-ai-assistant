from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
from typing import Callable

import pandas as pd
from pydantic import ValidationError

from .data import DataRepository
from .models import (
    BudgetArguments,
    EmptyArguments,
    LimitArguments,
    PeriodArguments,
    ToolResult,
    TravelArguments,
)

CENT = Decimal("0.01")


def _money(value: object) -> str:
    return str(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))


class FinanceTools:
    """Bounded financial operations; no model is used for arithmetic."""

    def __init__(self, repository: DataRepository):
        self.repo = repository

    @staticmethod
    def _period(year: int, quarter: int) -> tuple[pd.Timestamp, pd.Timestamp]:
        args = PeriodArguments(year=year, quarter=quarter)
        month = (args.quarter - 1) * 3 + 1
        start = pd.Timestamp(year=args.year, month=month, day=1)
        return start, start + pd.offsets.QuarterEnd()

    def latest_complete_year(self) -> int | None:
        dates = self.repo.gl.accrual_date
        years = []
        for year, group in dates.groupby(dates.dt.year):
            months = set(group.dt.month)
            if months == set(range(1, 13)) and group.min().month == 1 and group.max().month == 12:
                years.append(int(year))
        return max(years) if years else None

    def _classified(self) -> pd.DataFrame:
        gl = self.repo.gl
        joined = gl.merge(self.repo.coa, on="account_code", how="left", validate="many_to_many")
        active = joined[(joined.accrual_date >= joined.valid_from) & (joined.accrual_date <= joined.valid_to)]
        if len(active) != len(gl) or active.txn_id.duplicated().any():
            raise ValueError("Chart validity does not classify every transaction exactly once")
        return active

    def _with_usd(self, frame: pd.DataFrame, date_col: str = "accrual_date", amount_col: str = "amount") -> pd.DataFrame:
        out = frame.copy()
        out["period_month"] = out[date_col].dt.strftime("%Y-%m")
        out = out.merge(self.repo.fx, on=["period_month", "currency"], how="left", validate="many_to_one")
        missing = out[out.rate_to_usd.isna()][["period_month", "currency"]].drop_duplicates()
        out.attrs["missing_fx"] = missing.to_dict("records")
        out["amount_usd"] = [amount * rate if pd.notna(rate) else None for amount, rate in zip(out[amount_col], out.rate_to_usd)]
        return out

    @staticmethod
    def _fx_disclosure(data: pd.DataFrame) -> tuple[str, list[str], list[str]]:
        gaps = data.attrs.get("missing_fx", [])
        if not gaps:
            return "supported", [], []
        labels = [f"rate_to_usd for {row['currency']} in {row['period_month']}" for row in gaps]
        return "partial", ["USD figures exclude transactions whose monthly FX rate is missing; conclusions may change."], labels

    @staticmethod
    def _transactions(data: pd.DataFrame, limit: int = 200) -> list[dict[str, object]]:
        columns = [c for c in ("txn_id", "accrual_date", "posting_date", "entity", "cost_centre", "account_code", "amount", "currency", "vendor_id", "doc_ref") if c in data]
        rows = data[columns].head(limit).copy()
        for column in ("accrual_date", "posting_date"):
            if column in rows:
                rows[column] = rows[column].dt.strftime("%Y-%m-%d")
        return rows.astype("string").fillna("").to_dict("records")

    def _period_data(self, year: int, quarter: int) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame]:
        start, end = self._period(year, quarter)
        data = self._classified()
        selected = data[data.accrual_date.between(start, end)]
        return start, end, selected

    def operating_expenses(self, year: int, quarter: int) -> ToolResult:
        _, _, period = self._period_data(year, quarter)
        data = period[period.statement_line == "Operating Expenses"]
        if data.empty:
            return ToolResult(status="insufficient_data", summary=f"No operating-expense ledger coverage exists for {year} Q{quarter}.", missing=[f"ledger transactions for {year} Q{quarter}"], sources=["gl_transactions.csv", "chart_of_accounts.csv"])
        rows = data.groupby(["cost_centre", "currency"], as_index=False).amount.sum().sort_values(["cost_centre", "currency"])
        result = [{"cost_centre": r.cost_centre, "currency": r.currency, "amount": _money(r.amount)} for r in rows.itertuples()]
        return ToolResult(status="supported", summary=f"Operating expenses for {year} Q{quarter}, by cost centre and transaction currency.", data=result, sources=["gl_transactions.csv", "chart_of_accounts.csv"], conventions={"date_basis": "accrual_date", "sign": "credits reduce spend", "classification": "effective on accrual_date", "rounding": "2 decimals, half up"}, evidence={"filters": {"year": year, "quarter": quarter, "statement_line": "Operating Expenses"}, "transactions": self._transactions(data)})

    def travel_comparison(self, year: int = 2024, quarter: int | None = None) -> ToolResult:
        TravelArguments(year=year, quarter=quarter)
        data = self._classified()
        data = data[(data.parent_name == "Travel & Entertainment") & data.accrual_date.dt.year.isin([year - 1, year])]
        if quarter is not None:
            data = data[data.accrual_date.dt.quarter == quarter]
        years = set(data.accrual_date.dt.year)
        if not {year - 1, year}.issubset(years):
            return ToolResult(status="insufficient_data", summary="Both comparison periods need ledger coverage.", missing=[f"Travel & Entertainment ledger coverage for {sorted({year - 1, year} - years)}"], sources=["gl_transactions.csv", "chart_of_accounts.csv"])
        converted = self._with_usd(data)
        totals = converted.groupby(converted.accrual_date.dt.year).amount_usd.sum()
        previous, current = Decimal(str(totals[year - 1])), Decimal(str(totals[year]))
        delta = current - previous
        pct = None if previous == 0 else (delta / previous * 100).quantize(CENT, rounding=ROUND_HALF_UP)
        status, fx_warnings, missing = self._fx_disclosure(converted)
        excerpt = self.repo.document_excerpt("board_memo_2024_q2.md", "3. Chart of accounts")
        if excerpt is None:
            missing.append("board_memo_2024_q2.md")
            status = "partial"
        row = {"prior_year": year - 1, "prior_usd": _money(previous), "current_year": year, "current_usd": _money(current), "difference_usd": _money(delta), "change_percent": str(pct) if pct is not None else None}
        sources = ["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv"] + (["board_memo_2024_q2.md#3-chart-of-accounts"] if excerpt else [])
        return ToolResult(status=status, summary="Travel spend comparison in USD." if status == "supported" else "Partial travel comparison using available FX rates and documents.", data=[row], sources=sources, warnings=["Account 6230 leaves Travel & Entertainment on 2024-07-01; the comparison follows the dated chart."] + fx_warnings, missing=missing, conventions={"date_basis": "accrual_date", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend", "rounding": "2 decimals, half up"}, evidence={"filters": {"years": [year - 1, year], "quarter": quarter, "parent_name": "Travel & Entertainment"}, "documents": [excerpt] if excerpt else [], "transactions": self._transactions(data)})

    def consolidated_spend(self, year: int, quarter: int) -> ToolResult:
        _, _, period = self._period_data(year, quarter)
        data = period[period.statement_line == "Operating Expenses"]
        if data.empty:
            return ToolResult(status="insufficient_data", summary=f"No ledger coverage exists for {year} Q{quarter}.", missing=[f"ledger transactions for {year} Q{quarter}"], sources=["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv"])
        converted = self._with_usd(data)
        total = converted.amount_usd.sum()
        status, warnings, missing = self._fx_disclosure(converted)
        return ToolResult(status=status, summary=f"Consolidated operating spend for {year} Q{quarter}." if status == "supported" else f"Partial consolidated spend for {year} Q{quarter} using available FX rates.", data=[{"amount_usd": _money(total)}], sources=["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv"], warnings=warnings, missing=missing, conventions={"scope": "all entities; Operating Expenses", "date_basis": "accrual_date", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend", "rounding": "2 decimals, half up"}, evidence={"filters": {"year": year, "quarter": quarter, "statement_line": "Operating Expenses"}, "transactions": self._transactions(data)})

    def largest_vendors(self, limit: int = 10) -> ToolResult:
        LimitArguments(limit=limit)
        raw = self.repo.gl
        data = self._with_usd(raw[raw.vendor_id.notna() & (raw.vendor_id != "")])
        if data.empty:
            return ToolResult(status="insufficient_data", summary="No vendor-tagged ledger entries are available.", missing=["vendor-tagged ledger entries"], sources=["gl_transactions.csv", "vendors.csv"])
        rows = data.groupby("vendor_id", as_index=False).amount_usd.sum().merge(self.repo.vendors, on="vendor_id", how="left", validate="one_to_one").sort_values(["amount_usd", "vendor_id"], ascending=[False, True]).head(limit)
        result = [{"rank": i + 1, "vendor_id": r.vendor_id, "vendor_name": r.vendor_name, "spend_usd": _money(r.amount_usd)} for i, r in enumerate(rows.itertuples())]
        status, warnings, missing = self._fx_disclosure(data)
        return ToolResult(status=status, summary=f"Top {limit} vendors by net ledger spend using available FX rates.", data=result, sources=["gl_transactions.csv", "vendors.csv", "fx_rates.csv"], warnings=["Vendor-name variants remain separate; the master has no canonical relationship."] + warnings, missing=missing, conventions={"date_basis": "accrual_date", "scope": "vendor-tagged ledger entries", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend"}, evidence={"filters": {"vendor_id": "not blank", "limit": limit}, "transactions": self._transactions(data)})

    def budget_variance(self, year: int, quarter: int, limit: int = 10) -> ToolResult:
        BudgetArguments(year=year, quarter=quarter, limit=limit)
        start, end = self._period(year, quarter)
        budget = self.repo.budget.copy()
        budget_month = pd.to_datetime(budget.period_month, format="%Y-%m", errors="raise")
        selected_budget = budget[budget_month.between(start, end)].copy()
        available_years = sorted(set(budget_month.dt.year))
        if selected_budget.empty:
            return ToolResult(status="insufficient_data", summary="Budget is unavailable for the requested period.", missing=[f"budget for {year} Q{quarter}; available years: {available_years}"], sources=["budget.csv"])
        currencies = sorted(selected_budget.currency.dropna().unique())
        if currencies != ["USD"]:
            return ToolResult(status="insufficient_data", summary="Budget currency is not consistently USD, so it cannot be compared safely.", missing=[f"USD-only budget; found currencies: {currencies}"], sources=["budget.csv"])
        _, _, period = self._period_data(year, quarter)
        if period.empty:
            return ToolResult(status="insufficient_data", summary="Actual ledger coverage is unavailable for the budget period.", missing=[f"actual ledger transactions for {year} Q{quarter}"], sources=["gl_transactions.csv", "budget.csv"])
        period = period[period.statement_line == "Operating Expenses"]
        actual = self._with_usd(period)
        status, fx_warnings, missing = self._fx_disclosure(actual)
        actual["reporting_cc"] = actual.cost_centre.replace({"OPS-NA": "OPS-AMER"})
        incomplete_cc = set(actual.loc[actual.amount_usd.isna(), "reporting_cc"])
        known = actual[actual.amount_usd.notna()]
        actuals = known.groupby(["reporting_cc", "account_code"], as_index=False).amount_usd.sum()
        budgets = selected_budget.groupby(["cost_centre", "account_code"], as_index=False).budget_amount.sum()
        merged = actuals.merge(budgets, left_on=["reporting_cc", "account_code"], right_on=["cost_centre", "account_code"], how="outer")
        merged["reporting_cc"] = merged.reporting_cc.fillna(merged.cost_centre)
        merged[["amount_usd", "budget_amount"]] = merged[["amount_usd", "budget_amount"]].fillna(Decimal("0"))
        names = self.repo.coa.sort_values("valid_from").drop_duplicates("account_code", keep="last")[["account_code", "account_name"]]
        merged = merged.merge(names, on="account_code", how="left", validate="many_to_one")
        merged["variance_usd"] = merged.amount_usd - merged.budget_amount
        grouped = merged.groupby("reporting_cc", as_index=False)[["amount_usd", "budget_amount", "variance_usd"]].sum()
        grouped["complete"] = ~grouped.reporting_cc.isin(incomplete_cc)
        grouped = grouped.sort_values(["complete", "variance_usd"], ascending=[False, False]).head(limit)
        result = []
        for row in grouped.itertuples():
            drivers = merged[merged.reporting_cc == row.reporting_cc].sort_values("variance_usd", ascending=False).head(3)
            result.append({"cost_centre": row.reporting_cc, "actual_usd": _money(row.amount_usd) if row.complete else None, "known_actual_usd": _money(row.amount_usd), "budget_usd": _money(row.budget_amount), "unfavourable_variance_usd": _money(row.variance_usd) if row.complete else None, "known_rate_variance_usd": _money(row.variance_usd), "complete": bool(row.complete), "top_drivers": [{"account": d.account_name, "variance_usd": _money(d.variance_usd)} for d in drivers.itertuples()]})
        excerpt = self.repo.document_excerpt("board_memo_2024_q2.md", "2. Americas reorganisation")
        if excerpt is None:
            missing.append("board_memo_2024_q2.md")
            status = "partial"
        sources = ["gl_transactions.csv", "chart_of_accounts.csv", "budget.csv", "fx_rates.csv"] + (["board_memo_2024_q2.md#2-americas-reorganisation"] if excerpt else [])
        return ToolResult(status=status, summary=f"Cost-centre budget comparison for {year} Q{quarter}; incomplete FX centres are not ranked as confirmed savings or overruns.", data=result, sources=sources, warnings=["OPS-NA actuals map to OPS-AMER for the restated 2024 plan."] + fx_warnings, missing=missing, conventions={"date_basis": "accrual_date", "budget_scope": f"{year} Q{quarter}, USD rows only", "currency": "actual USD at monthly rate; budget USD", "variance": "actual minus budget", "rounding": "2 decimals, half up"}, evidence={"filters": {"year": year, "quarter": quarter}, "documents": [excerpt] if excerpt else [], "transactions": self._transactions(period)})

    def travel_policy_review(self) -> ToolResult:
        data = self._classified()
        travel = self._with_usd(data[data.account_code.isin(["6210", "6220", "6230", "6240"])])
        candidates = travel[travel.amount_usd.notna() & (travel.amount_usd >= 1000) & travel.approval_ref.isna()]
        rows = [{"txn_id": r.txn_id, "rule": "USD 1,000 pre-approval", "amount_usd": _money(r.amount_usd), "approval_ref": None, "memo": r.memo} for r in candidates.itertuples()]
        missing = ["flight duration and cabin class", "hotel city, nights, room rate and tax", "meal travel days", "entertainment event/attendees and approval timing", "employee-expense/payment evidence"] + [f"rate_to_usd for {r['currency']} in {r['period_month']}" for r in travel.attrs.get("missing_fx", [])]
        excerpt = self.repo.document_excerpt("travel_expense_policy.md", "Pre-approval")
        if excerpt is None:
            missing.append("travel_expense_policy.md")
        sources = ["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv"] + (["travel_expense_policy.md#pre-approval"] if excerpt else [])
        return ToolResult(status="partial", summary=f"Found {len(rows)} ledger candidates for the testable missing-approval rule; they are not confirmed breaches.", data=rows, sources=sources, missing=missing, warnings=["Accounting entries do not prove employee reimbursement or approval timing."], conventions={"date_basis": "accrual_date", "currency": "policy USD threshold using monthly rate_to_usd", "threshold": "amount >= USD 1,000 and approval_ref missing"}, evidence={"filters": {"accounts": ["6210", "6220", "6230", "6240"], "threshold_usd": "1000"}, "documents": [excerpt] if excerpt else [], "transactions": self._transactions(candidates)})

    def headcount_cost_per_fte(self) -> ToolResult:
        excerpt = self.repo.document_excerpt("board_memo_2024_q2.md", "5. Headcount")
        missing = ["FTE counts by a defined period and population from the HR system"]
        if excerpt is None:
            missing.append("board_memo_2024_q2.md")
        sources = ["gl_transactions.csv", "chart_of_accounts.csv"] + (["board_memo_2024_q2.md#5-headcount"] if excerpt else [])
        return ToolResult(status="insufficient_data", summary="A personnel-cost numerator exists, but no FTE denominator is present.", sources=sources, missing=missing, evidence={"documents": [excerpt] if excerpt else []})

    def duplicate_payment_review(self) -> ToolResult:
        valid = self.repo.gl
        valid = valid[valid.vendor_id.notna() & (valid.vendor_id != "") & (valid.amount > 0)].sort_values(["vendor_id", "amount", "currency", "accrual_date", "txn_id"])
        candidates = []
        seen: set[tuple[str, str]] = set()
        for _, group in valid.groupby(["vendor_id", "amount", "currency"]):
            for left, right in combinations(group.itertuples(), 2):
                days = abs((right.accrual_date - left.accrual_date).days)
                pair = tuple(sorted((left.txn_id, right.txn_id)))
                if days > 30 or pair in seen:
                    continue
                seen.add(pair)
                same_ref = pd.notna(left.doc_ref) and left.doc_ref == right.doc_ref
                candidates.append({"txn_id_1": pair[0], "txn_id_2": pair[1], "vendor_id": left.vendor_id, "amount": _money(left.amount), "currency": left.currency, "days_apart": days, "doc_refs": [left.doc_ref, right.doc_ref], "candidate_type": "repeated_document_reference" if same_ref else "similar_ledger_entries"})
        return ToolResult(status="partial", summary=f"Found {len(candidates)} unique ledger-entry candidate pairs; payment duplication cannot be established.", data=candidates, sources=["gl_transactions.csv"], missing=["canonical invoice ID, accounts-payable status, payment records (ID/date/account) and reversal links"], warnings=["A repeated document reference can be a repeated posting, not proof of a duplicate invoice or payment; different references may be legitimate recurring invoices."], conventions={"candidate_rule": "same vendor, positive amount and currency, accrual dates <=30 days; same and different doc_ref retained", "claim_boundary": "ledger candidate != invoice duplicate != confirmed duplicate payment"}, evidence={"filters": {"positive_amount": True, "days_apart_max": 30}, "transactions": self._transactions(valid)})

    def dispatch(self, name: str, **kwargs: object) -> ToolResult:
        allowed: dict[str, tuple[type, Callable[..., ToolResult]]] = {
            "operating_expenses": (PeriodArguments, self.operating_expenses),
            "travel_comparison": (TravelArguments, self.travel_comparison),
            "consolidated_spend": (PeriodArguments, self.consolidated_spend),
            "largest_vendors": (LimitArguments, self.largest_vendors),
            "budget_variance": (BudgetArguments, self.budget_variance),
            "travel_policy_review": (EmptyArguments, self.travel_policy_review),
            "headcount_cost_per_fte": (EmptyArguments, self.headcount_cost_per_fte),
            "duplicate_payment_review": (EmptyArguments, self.duplicate_payment_review),
        }
        if name not in allowed:
            raise ValueError(f"Unknown tool: {name}")
        schema, function = allowed[name]
        try:
            arguments = schema.model_validate(kwargs).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise ValueError(f"Invalid arguments for {name}: {exc}") from exc
        return function(**arguments)
