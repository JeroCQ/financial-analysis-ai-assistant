from pathlib import Path

import pandas as pd
import pytest

from finance_assistant.data import DataRepository
from finance_assistant.tools import FinanceTools


@pytest.fixture
def tools() -> FinanceTools:
    return FinanceTools(DataRepository(Path(__file__).parents[1]))


def test_classification_respects_effective_date(tools):
    data = tools._classified()
    before = data[(data.account_code == "6230") & (data.accrual_date == pd.Timestamp("2024-06-30"))]
    after = data[(data.account_code == "6230") & (data.accrual_date == pd.Timestamp("2024-07-01"))]
    assert set(before.parent_name) == {"Travel & Entertainment"}
    assert set(after.parent_name) == {"Marketing"}


def test_q2_uses_accrual_date_and_keeps_currencies_separate(tools):
    result = tools.operating_expenses(2024, 2)
    assert result.status == "supported"
    assert len(result.data) == 9
    assert {row["currency"] for row in result.data} == {"CAD", "EUR", "USD"}


def test_missing_fx_makes_consolidation_partial(tools):
    result = tools.consolidated_spend(2024, 3)
    assert result.status == "partial"
    assert "rate_to_usd for EUR in 2024-09" in result.missing


def test_credits_reduce_vendor_spend(tools):
    gl = tools.repo.gl
    vendor = "V1021"
    signed = gl[gl.vendor_id == vendor].amount.sum()
    positive_only = gl[(gl.vendor_id == vendor) & (gl.amount > 0)].amount.sum()
    assert signed < positive_only


def test_ops_rename_is_applied_to_budget(tools):
    result = tools.budget_variance(2024, 3)
    centres = {row["cost_centre"] for row in result.data}
    assert "OPS-AMER" in centres
    assert "OPS-NA" not in centres


def test_policy_does_not_overclaim(tools):
    result = tools.travel_policy_review()
    assert result.status == "partial"
    assert "candidates" in result.summary
    assert "flight duration and cabin class" in result.missing


def test_fte_refusal_names_missing_denominator(tools):
    result = tools.headcount_cost_per_fte()
    assert result.status == "insufficient_data"
    assert "FTE" in result.missing[0]


def test_duplicate_review_is_not_payment_claim(tools):
    result = tools.duplicate_payment_review()
    assert result.status == "partial"
    assert len(result.data) == 9
    assert "payment records" in result.missing[0]


def test_schema_validation_rejects_incomplete_folder(tmp_path):
    with pytest.raises(ValueError, match="Missing file"):
        DataRepository(tmp_path)


def test_dispatch_rejects_invalid_and_unexpected_arguments(tools):
    with pytest.raises(ValueError, match="Invalid arguments"):
        tools.dispatch("operating_expenses", year=2024, quarter=5)
    with pytest.raises(ValueError, match="Invalid arguments"):
        tools.dispatch("largest_vendors", limit=10, sql="drop table")
    with pytest.raises(ValueError, match="Unknown tool"):
        tools.dispatch("run_anything")


def test_period_without_coverage_is_not_supported(tools):
    result = tools.operating_expenses(2030, 1)
    assert result.status == "insufficient_data"
    assert "2030 Q1" in result.missing[0]


def test_latest_complete_year_requires_all_months(tools, monkeypatch):
    incomplete = tools.repo.gl[tools.repo.gl.accrual_date.dt.month != 12]
    monkeypatch.setattr(type(tools.repo), "gl", property(lambda _: incomplete))
    assert tools.latest_complete_year() is None


def test_duplicate_rule_includes_same_document_reference(tools, monkeypatch):
    frame = tools.repo.gl.head(2).copy()
    frame.loc[:, "txn_id"] = ["A", "B"]
    frame.loc[:, "vendor_id"] = "V1001"
    frame.loc[:, "amount"] = 100
    frame.loc[:, "currency"] = "USD"
    frame.loc[:, "doc_ref"] = "INV-1"
    frame.loc[:, "accrual_date"] = pd.to_datetime(["2024-01-01", "2024-01-02"])
    monkeypatch.setattr(type(tools.repo), "gl", property(lambda _: frame))
    result = tools.duplicate_payment_review()
    assert len(result.data) == 1
    assert result.data[0]["candidate_type"] == "repeated_document_reference"


def test_budget_outer_join_keeps_budget_only_and_actual_only(tools, monkeypatch):
    gl = tools.repo.gl
    extra = gl.iloc[[0]].copy()
    extra.loc[:, "txn_id"] = "ACTUAL-ONLY"
    extra.loc[:, "accrual_date"] = pd.Timestamp("2024-07-15")
    extra.loc[:, "posting_date"] = pd.Timestamp("2024-07-15")
    extra.loc[:, "cost_centre"] = "ACTUAL-ONLY"
    extra.loc[:, "account_code"] = "6110"
    extra.loc[:, "currency"] = "USD"
    extra.loc[:, "amount"] = 100
    changed_gl = pd.concat([gl, extra], ignore_index=True)
    budget = tools.repo.budget
    extra_budget = budget.iloc[[0]].copy()
    extra_budget.loc[:, "entity"] = "MI-US"
    extra_budget.loc[:, "cost_centre"] = "BUDGET-ONLY"
    extra_budget.loc[:, "account_code"] = "6110"
    extra_budget.loc[:, "period_month"] = "2024-07"
    extra_budget.loc[:, "budget_amount"] = 50
    changed_budget = pd.concat([budget, extra_budget], ignore_index=True)
    monkeypatch.setattr(type(tools.repo), "gl", property(lambda _: changed_gl))
    monkeypatch.setattr(type(tools.repo), "budget", property(lambda _: changed_budget))
    result = tools.budget_variance(2024, 3, 50)
    centres = {row["cost_centre"]: row for row in result.data}
    assert centres["BUDGET-ONLY"]["known_actual_usd"] == "0.00"
    assert centres["BUDGET-ONLY"]["budget_usd"] == "50.00"
    assert centres["ACTUAL-ONLY"]["budget_usd"] == "0.00"


def test_budget_availability_comes_from_dates(tools, monkeypatch):
    budget = tools.repo.budget.copy()
    budget.loc[:, "period_month"] = budget.period_month.str.replace("2024-", "2025-", regex=False)
    gl = tools.repo.gl.copy()
    gl.loc[:, "accrual_date"] = gl.accrual_date + pd.DateOffset(years=1)
    gl.loc[:, "posting_date"] = gl.posting_date + pd.DateOffset(years=1)
    monkeypatch.setattr(type(tools.repo), "budget", property(lambda _: budget))
    monkeypatch.setattr(type(tools.repo), "gl", property(lambda _: gl))
    assert tools.budget_variance(2025, 3).status in {"supported", "partial"}


def test_budget_rejects_mixed_currency(tools, monkeypatch):
    budget = tools.repo.budget.copy()
    budget.loc[budget.index[0], "currency"] = "CAD"
    monkeypatch.setattr(type(tools.repo), "budget", property(lambda _: budget))
    result = tools.budget_variance(2024, 1)
    assert result.status == "insufficient_data"
    assert "USD" in result.missing[0]
