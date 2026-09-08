from __future__ import annotations

from pathlib import Path
from decimal import Decimal

import pandas as pd


REQUIRED = {
    "gl_transactions.csv": {"txn_id", "posting_date", "accrual_date", "entity", "cost_centre", "account_code", "amount", "currency", "vendor_id", "doc_ref", "approval_ref", "memo"},
    "chart_of_accounts.csv": {"account_code", "account_name", "parent_name", "statement_line", "valid_from", "valid_to"},
    "budget.csv": {"entity", "cost_centre", "account_code", "period_month", "budget_amount", "currency"},
    "fx_rates.csv": {"period_month", "currency", "rate_to_usd"},
    "vendors.csv": {"vendor_id", "vendor_name", "category", "country"},
}

DOCUMENTS = {
    "board_memo_2024_q2.md",
    "contract_kestrel.md",
    "contract_northgate_advisory.md",
    "travel_expense_policy.md",
}


class DataRepository:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self._validate()

    def _read(self, name: str) -> pd.DataFrame:
        return pd.read_csv(self.folder / name, dtype={"account_code": str})

    def _validate(self) -> None:
        for name, columns in REQUIRED.items():
            path = self.folder / name
            if not path.is_file():
                raise ValueError(f"Missing file: {name}")
            actual = set(pd.read_csv(path, nrows=0).columns)
            if missing := columns - actual:
                raise ValueError(f"{name} missing columns: {sorted(missing)}")

    @property
    def gl(self) -> pd.DataFrame:
        frame = self._read("gl_transactions.csv")
        frame["posting_date"] = pd.to_datetime(frame["posting_date"], errors="raise")
        frame["accrual_date"] = pd.to_datetime(frame["accrual_date"], errors="raise")
        frame["amount"] = frame["amount"].map(lambda value: Decimal(str(value)))
        return frame

    @property
    def coa(self) -> pd.DataFrame:
        frame = self._read("chart_of_accounts.csv")
        frame["valid_from"] = pd.to_datetime(frame["valid_from"], format="%Y-%m-%d", errors="raise")
        frame["valid_to"] = pd.to_datetime(frame["valid_to"], format="%Y-%m-%d", errors="coerce").fillna(pd.Timestamp.max.normalize())
        return frame

    @property
    def budget(self) -> pd.DataFrame:
        frame = self._read("budget.csv")
        frame["budget_amount"] = frame["budget_amount"].map(lambda value: Decimal(str(value)))
        return frame

    @property
    def fx(self) -> pd.DataFrame:
        frame = self._read("fx_rates.csv")
        frame["rate_to_usd"] = frame["rate_to_usd"].map(lambda value: Decimal(str(value)))
        return frame

    @property
    def vendors(self) -> pd.DataFrame:
        return self._read("vendors.csv")

    def documents(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for directory in (self.folder, self.folder / "docs"):
            for name in DOCUMENTS:
                path = directory / name
                if path.is_file():
                    found[name] = path.read_text(encoding="utf-8")
        return dict(sorted(found.items()))

    def document_excerpt(self, name: str, heading: str) -> dict[str, str] | None:
        text = self.documents().get(name)
        if text is None:
            return None
        marker = f"## {heading}"
        start = text.find(marker)
        if start < 0:
            return {"source": name, "section": "full document", "text": text}
        end = text.find("\n## ", start + len(marker))
        return {"source": name, "section": heading, "text": text[start:end if end >= 0 else None].strip()}
