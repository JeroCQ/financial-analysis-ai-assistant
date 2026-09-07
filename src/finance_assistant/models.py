from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Period(BaseModel):
    start: str
    end: str


class ToolResult(BaseModel):
    status: Literal["supported", "partial", "needs_clarification", "insufficient_data"]
    summary: str
    data: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    conventions: dict[str, str] = Field(default_factory=dict)


class Route(BaseModel):
    tool: Literal[
        "operating_expenses", "travel_comparison", "consolidated_spend",
        "largest_vendors", "budget_variance", "travel_policy_review",
        "headcount_cost_per_fte", "duplicate_payment_review", "clarify"
    ]
    year: int | None = None
    quarter: int | None = Field(default=None, ge=1, le=4)
    limit: int = Field(default=10, ge=1, le=50)
    rationale: str = Field(max_length=240)

