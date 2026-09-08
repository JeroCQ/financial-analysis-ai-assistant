from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Period(BaseModel):
    start: str
    end: str


class ToolResult(BaseModel):
    status: Literal["supported", "partial", "needs_clarification", "insufficient_data", "provider_unavailable", "configuration_error"]
    summary: str
    data: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    conventions: dict[str, str] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PeriodArguments(Arguments):
    year: int = Field(ge=2000, le=2100)
    quarter: int = Field(ge=1, le=4)


class TravelArguments(Arguments):
    year: int = Field(default=2024, ge=2000, le=2100)
    quarter: int | None = Field(default=None, ge=1, le=4)


class LimitArguments(Arguments):
    limit: int = Field(default=10, ge=1, le=50)


class BudgetArguments(PeriodArguments):
    limit: int = Field(default=10, ge=1, le=50)


class EmptyArguments(Arguments):
    pass


class ClarifyArguments(Arguments):
    rationale: str = Field(min_length=1, max_length=240)
