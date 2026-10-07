
import httpx
import pytest

from app.runner import execute_case, summarize
from app.target import call_target


@pytest.mark.asyncio
async def test_invalid_field_keeps_raw_output_and_independent_field_metrics(
    team_client, monkeypatch
):
    client, _ = team_client

    async def target(*args, **kwargs):
        return {"subject": ["math"], "level": {"bad": "shape"}}

    monkeypatch.setattr("app.runner.call_target", target)
    saved = {
        "service": {"kind": "demo"},
        "criteria": [],
        "plan": {
            "fields": [
                {"name": "subject", "reference_path": "/subject", "output_path": "/subject"},
                {"name": "level", "reference_path": "/level", "output_path": "/level"},
            ]
        },
    }
    case = {"id": "one", "input": {}, "reference": {"subject": ["math"], "level": ["primary"]}}
    result = await execute_case(client.app, saved, case)
    assert result["output"] == {"subject": ["math"], "level": {"bad": "shape"}}
    assert result["field_errors"].keys() == {"level"}
    metrics = summarize([result], saved)["reference"]
    assert metrics[0]["micro"]["f1"] == 1
    assert metrics[1]["fn"] == 1
    saved["plan"]["fields"] = [saved["plan"]["fields"][0]]
    repaired = await execute_case(client.app, saved, case, reused=result)
    assert repaired["status"] == "success"
    assert repaired["field_errors"] == {}


@pytest.mark.asyncio
async def test_schema_error_retains_the_received_response(team_client):
    client, _ = team_client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"title": "received"}))
    service = {
        "kind": "http",
        "url": "https://api.openai.com/example",
        "method": "POST",
        "mapping": {"$input": ""},
        "response_schema": {"type": "object", "required": ["subject"]},
    }
    with pytest.raises(ValueError) as raised:
        await call_target(service, {}, client.app.state.settings, transport=transport)
    assert raised.value.output == {"title": "received"}


def test_incremental_summary_matches_documented_multilabel_semantics():
    from app.aggregation import SummaryAccumulator

    saved = {
        "plan": {
            "fields": [{"name": "subject", "output_path": "/subject", "reference_path": "/subject"}]
        },
        "criteria": [],
    }
    results = [
        {
            "status": "success",
            "reference": {"subject": ["a", "b"]},
            "output": {"subject": ["a", "x"]},
            "judges": [],
        },
        {"status": "target_error", "reference": {"subject": ["b"]}, "output": None, "judges": []},
        {"status": "success", "reference": {}, "output": {"subject": ["x"]}, "judges": []},
    ]
    accumulator = SummaryAccumulator(saved)
    for row in results:
        accumulator.add(row)
    actual = accumulator.summary()
    assert actual == summarize(results, saved)
    field = actual["reference"][0]
    assert (field["tp"], field["fp"], field["fn"]) == (1, 1, 2)
    assert field["coverage"] == 2 / 3
    assert field["micro"]["f1"] == 0.4


def test_high_cardinality_is_bounded():
    from app.aggregation import SummaryAccumulator

    saved = {
        "plan": {
            "fields": [
                {"name": "keywords", "output_path": "/keywords", "reference_path": "/keywords"}
            ]
        },
        "criteria": [],
    }
    accumulator = SummaryAccumulator(saved)
    with pytest.raises(ValueError, match="label budget"):
        accumulator.add(
            {
                "status": "success",
                "reference": {"keywords": []},
                "output": {"keywords": [str(i) for i in range(10001)]},
                "judges": [],
            }
        )
