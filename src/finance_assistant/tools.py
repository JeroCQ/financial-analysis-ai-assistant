from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

import pandas as pd

from .data import DataRepository
from .models import ToolResult

CENT = Decimal("0.01")


def _money(value: object) -> str:
    return str(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))


class FinanceTools:
    """Bounded financial operations; no model is used for arithmetic."""

    def __init__(self, repository: DataRepository):
        self.repo = repository

    @staticmethod
    def _period(year: int, quarter: int) -> tuple[pd.Timestamp, pd.Timestamp]:
        if quarter not in range(1, 5):
            raise ValueError("quarter must be 1-4")
        month = (quarter - 1) * 3 + 1
        start = pd.Timestamp(year=year, month=month, day=1)
        return start, start + pd.offsets.QuarterEnd()

    def _classified(self) -> pd.DataFrame:
        gl = self.repo.gl
        coa = self.repo.coa
        joined = gl.merge(coa, on="account_code", how="left", validate="many_to_many")
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

    def operating_expenses(self, year: int, quarter: int) -> ToolResult:
        start, end = self._period(year, quarter)
        data = self._classified()
        data = data[(data.accrual_date >= start) & (data.accrual_date <= end) & (data.statement_line == "Operating Expenses")]
        rows = data.groupby("cost_centre", as_index=False).amount.sum().sort_values("amount", ascending=False)
        # Separate currencies.
        rows = data.groupby(["cost_centre", "currency"], as_index=False).amount.sum().sort_values(["cost_centre", "currency"])
        result = [{"cost_centre": r.cost_centre, "currency": r.currency, "amount": _money(r.amount)} for r in rows.itertuples()]
        return ToolResult(status="supported", summary=f"Operating expenses for {year} Q{quarter}, by cost centre and transaction currency.", data=result, sources=["gl_transactions.csv", "chart_of_accounts.csv"], conventions={"date_basis": "accrual_date", "sign": "credits reduce spend", "classification": "effective on accrual_date", "rounding": "USD/local amounts: 2 decimals, half up"})

    def travel_comparison(self, year: int = 2024, quarter: int | None = None) -> ToolResult:
        data = self._classified()
        data = data[data.parent_name == "Travel & Entertainment"]
        data = data[data.accrual_date.dt.year.isin([year - 1, year])]
        if quarter:
            data = data[data.accrual_date.dt.quarter == quarter]
        data = self._with_usd(data)
        totals = data.groupby(data.accrual_date.dt.year).amount_usd.sum()
        previous, current = Decimal(str(totals.get(year - 1, 0))), Decimal(str(totals.get(year, 0)))
        delta = current - previous
        pct = None if previous == 0 else (delta / previous * 100).quantize(CENT, rounding=ROUND_HALF_UP)
        row = {"prior_year": year - 1, "prior_usd": _money(previous), "current_year": year, "current_usd": _money(current), "difference_usd": _money(delta), "change_percent": str(pct) if pct is not None else None}
        warnings = ["Client entertainment (account 6230) leaves Travel & Entertainment on 2024-07-01 under the dated chart; the comparison follows that reporting classification."]
        status, fx_warnings, missing = self._fx_disclosure(data)
        return ToolResult(status=status, summary="Travel spend comparison in USD." if status == "supported" else "Partial travel comparison using available FX rates.", data=[row], sources=["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv", "board_memo_2024_q2.md#3-chart-of-accounts"], warnings=warnings + fx_warnings, missing=missing, conventions={"date_basis": "accrual_date", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend", "rounding": "2 decimals, half up"})

    def consolidated_spend(self, year: int, quarter: int) -> ToolResult:
        start, end = self._period(year, quarter)
        data = self._classified()
        data = data[(data.accrual_date >= start) & (data.accrual_date <= end) & (data.statement_line == "Operating Expenses")]
        data = self._with_usd(data)
        total = data.amount_usd.sum()
        status, warnings, missing = self._fx_disclosure(data)
        return ToolResult(status=status, summary=f"Consolidated operating spend for {year} Q{quarter}." if status == "supported" else f"Partial consolidated spend for {year} Q{quarter} using available FX rates.", data=[{"amount_usd": _money(total)}], sources=["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv"], warnings=warnings, missing=missing, conventions={"scope": "all entities; Operating Expenses", "date_basis": "accrual_date", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend", "rounding": "2 decimals, half up"})

    def largest_vendors(self, limit: int = 10) -> ToolResult:
        data = self._with_usd(self.repo.gl)
        data = data[data.vendor_id.notna() & (data.vendor_id != "")]
        rows = data.groupby("vendor_id", as_index=False).amount_usd.sum().merge(self.repo.vendors, on="vendor_id", how="left", validate="one_to_one").sort_values("amount_usd", ascending=False).head(limit)
        result = [{"rank": i + 1, "vendor_id": r.vendor_id, "vendor_name": r.vendor_name, "spend_usd": _money(r.amount_usd)} for i, r in enumerate(rows.itertuples())]
        status, fx_warnings, missing = self._fx_disclosure(data)
        return ToolResult(status=status, summary=f"Top {limit} vendors by net ledger spend using available FX rates.", data=result, sources=["gl_transactions.csv", "vendors.csv", "fx_rates.csv"], warnings=["Vendor-name variants are ranked separately because the master contains no canonical-vendor relationship."] + fx_warnings, missing=missing, conventions={"date_basis": "accrual_date", "scope": "vendor-tagged ledger entries", "currency": "USD at monthly rate_to_usd", "sign": "credits reduce spend"})

    def budget_variance(self, year: int, quarter: int, limit: int = 10) -> ToolResult:
        if year != 2024:
            return ToolResult(status="insufficient_data", summary="Budget is unavailable for the requested year.", missing=[f"{year} budget"], sources=["budget.csv"])
        start, end = self._period(year, quarter)
        actual = self._classified()
        actual = actual[(actual.accrual_date >= start) & (actual.accrual_date <= end)]
        actual = self._with_usd(actual)
        status, fx_warnings, missing = self._fx_disclosure(actual)
        actual["reporting_cc"] = actual.cost_centre.replace({"OPS-NA": "OPS-AMER"})
        actuals = actual.groupby(["reporting_cc", "account_code", "account_name"], as_index=False).amount_usd.sum()
        budget = self.repo.budget
        budget = budget[budget.period_month.between(start.strftime("%Y-%m"), end.strftime("%Y-%m"))]
        budgets = budget.groupby(["cost_centre", "account_code"], as_index=False).budget_amount.sum()
        merged = actuals.merge(budgets, left_on=["reporting_cc", "account_code"], right_on=["cost_centre", "account_code"], how="outer")
        merged[["amount_usd", "budget_amount"]] = merged[["amount_usd", "budget_amount"]].fillna(0)
        merged["variance_usd"] = merged.amount_usd - merged.budget_amount
        cc = merged.groupby("reporting_cc", as_index=False)[["amount_usd", "budget_amount", "variance_usd"]].sum().sort_values("variance_usd", ascending=False).head(limit)
        result = []
        for row in cc.itertuples():
            drivers = merged[merged.reporting_cc == row.reporting_cc].sort_values("variance_usd", ascending=False).head(3)
            result.append({"cost_centre": row.reporting_cc, "actual_usd": _money(row.amount_usd), "budget_usd": _money(row.budget_amount), "unfavourable_variance_usd": _money(row.variance_usd), "top_drivers": [{"account": d.account_name, "variance_usd": _money(d.variance_usd)} for d in drivers.itertuples()]})
        return ToolResult(status=status, summary=f"Worst cost centres against budget in {year} Q{quarter}; positive variance is unfavourable.", data=result, sources=["gl_transactions.csv", "chart_of_accounts.csv", "budget.csv", "fx_rates.csv", "board_memo_2024_q2.md#2-americas-reorganisation"], warnings=["OPS-NA actuals are mapped to OPS-AMER, matching the full-year restated budget."] + fx_warnings, missing=missing, conventions={"date_basis": "accrual_date", "currency": "actual USD at monthly rate; budget supplied in USD", "variance": "actual minus budget", "rounding": "2 decimals, half up"})

    def travel_policy_review(self) -> ToolResult:
        data = self._classified()
        travel = self._with_usd(data[data.account_code.isin(["6210", "6220", "6230", "6240"])])
        missing_approval = travel[travel.amount_usd.notna() & (travel.amount_usd >= 1000) & travel.approval_ref.isna()]
        rows = [{"txn_id": r.txn_id, "rule": "USD 1,000 pre-approval", "amount_usd": _money(r.amount_usd), "approval_ref": None, "memo": r.memo} for r in missing_approval.itertuples()]
        missing = ["flight duration and cabin class", "hotel city, nights, room rate and tax", "meal travel days", "entertainment event/attendees and approval timing", "employee-expense/payment evidence"]
        missing += [f"rate_to_usd for {row['currency']} in {row['period_month']}" for row in travel.attrs.get("missing_fx", [])]
        return ToolResult(status="partial", summary=f"Found {len(rows)} ledger transactions that are candidates for the objectively testable missing-approval rule; other policy rules cannot be concluded from ledger fields.", data=rows, sources=["gl_transactions.csv", "chart_of_accounts.csv", "fx_rates.csv", "travel_expense_policy.md#pre-approval"], missing=missing, warnings=["These are accounting-entry candidates, not proven employee reimbursements or confirmed breaches."], conventions={"date_basis": "accrual_date", "currency": "policy USD threshold using monthly rate_to_usd", "threshold": "amount >= USD 1,000 and approval_ref missing"})

    def headcount_cost_per_fte(self) -> ToolResult:
        return ToolResult(status="insufficient_data", summary="A personnel-cost numerator exists, but no FTE denominator is present, so cost per FTE cannot be calculated honestly.", sources=["gl_transactions.csv", "chart_of_accounts.csv", "board_memo_2024_q2.md#5-headcount"], missing=["FTE counts by a defined period and population from the HR system"])

    def duplicate_payment_review(self) -> ToolResult:
        data = self.repo.gl.sort_values(["vendor_id", "amount", "currency", "accrual_date"])
        candidates = []
        valid = data[data.vendor_id.notna() & (data.vendor_id != "") & (data.amount > 0)]
        for _, group in valid.groupby(["vendor_id", "amount", "currency"]):
            if len(group) < 2:
                continue
            records = list(group.itertuples())
            for left, right in zip(records, records[1:]):
                days = (right.accrual_date - left.accrual_date).days
                if days <= 30 and left.doc_ref != right.doc_ref:
                    candidates.append({"txn_id_1": left.txn_id, "txn_id_2": right.txn_id, "vendor_id": left.vendor_id, "amount": _money(left.amount), "currency": left.currency, "days_apart": days, "doc_refs": [left.doc_ref, right.doc_ref]})
        return ToolResult(status="partial", summary=f"Found {len(candidates)} ledger-entry pairs with the same vendor, amount and currency within 30 days, but payment duplication cannot be established.", data=candidates, sources=["gl_transactions.csv"], missing=["accounts-payable invoice identifiers and payment records/status"], warnings=["Different document references can represent legitimate recurring invoices; the ledger is not a payment table."], conventions={"candidate_rule": "same vendor, positive amount and currency; distinct document reference; accrual dates <=30 days"})

    def dispatch(self, name: str, **kwargs: object) -> ToolResult:
        allowed: dict[str, Callable[..., ToolResult]] = {
            "operating_expenses": self.operating_expenses,
            "travel_comparison": self.travel_comparison,
            "consolidated_spend": self.consolidated_spend,
            "largest_vendors": self.largest_vendors,
            "budget_variance": self.budget_variance,
            "travel_policy_review": self.travel_policy_review,
            "headcount_cost_per_fte": self.headcount_cost_per_fte,
            "duplicate_payment_review": self.duplicate_payment_review,
        }
        if name not in allowed:
            raise ValueError(f"Unknown tool: {name}")
        return allowed[name](**kwargs)
