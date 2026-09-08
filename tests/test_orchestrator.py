import json
from pathlib import Path

from finance_assistant.data import DataRepository
from finance_assistant.orchestrator import Assistant
from finance_assistant.tools import FinanceTools


class UnavailableModels:
    def generate_content(self, **kwargs):
        raise RuntimeError("503 UNAVAILABLE: high demand; secret=not-present")


class UnavailableClient:
    models = UnavailableModels()


class MultipleCallResponse:
    function_calls = [object(), object()]
    usage_metadata = None


class MultipleCallModels:
    def generate_content(self, **kwargs):
        return MultipleCallResponse()


def test_503_is_sanitized_traced_and_not_a_financial_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    tools = FinanceTools(DataRepository(Path(__file__).parents[1]))
    assistant = Assistant(tools, trace_dir=tmp_path, client_factory=lambda **kwargs: UnavailableClient())
    output = assistant.run("What was total consolidated spend in Q3, in USD?")
    assert output.result.status == "provider_unavailable"
    assert output.result.data == []
    assert output.trace["events"][-1]["category"] == "provider_unavailable"
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert saved["result_status"] == "provider_unavailable"
    assert "api_key" not in json.dumps(saved).lower()


def test_multiple_calls_are_rejected_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    tools = FinanceTools(DataRepository(Path(__file__).parents[1]))
    client = type("Client", (), {"models": MultipleCallModels()})()
    output = Assistant(tools, trace_dir=tmp_path, client_factory=lambda **kwargs: client).run("question")
    assert output.result.status == "configuration_error"
    assert output.result.data == []
    assert "exactly one" in output.result.warnings[0]
