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
