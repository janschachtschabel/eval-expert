import pytest


@pytest.mark.parametrize(
    "mode,fields,provider,criteria",
    [
        ("reference", [], None, []),
        ("judge", [], None, ["criterion"]),
        ("judge", [], "provider", []),
        ("combined", [], "provider", ["criterion"]),
        (
            "combined",
            [{"name": "subject", "output_path": "/subject", "reference_path": "/subject"}],
            None,
            ["criterion"],
        ),
    ],
)
def test_incomplete_profile_is_rejected_before_persistence(
    team_client, mode, fields, provider, criteria
):
    client, headers = team_client
    demo = client.post("/api/demo", headers=headers).json()
    plan = client.get("/api/catalog/plans/" + demo["plan_id"]).json()
    for kind, data in [
        ("providers", {"name": "Provider", "model": "test"}),
        ("criteria", {"name": "Criterion", "steps": ["Evaluate."]}),
    ]:
        created = client.post("/api/catalog/" + kind, headers=headers, json=data).json()
        if kind == "providers" and provider:
            provider = created["id"]
        if kind == "criteria" and criteria:
            criteria = [created["id"]]
    response = client.post(
        "/api/catalog/plans",
        headers=headers,
        json={
            **plan,
            "name": "Incomplete",
            "mode": mode,
            "fields": fields,
            "provider_id": provider,
            "criterion_ids": criteria,
        },
    )
    assert response.status_code == 422
    assert not any(item["name"] == "Incomplete" for item in client.get("/api/catalog/plans").json())


def test_catalog_validation_does_not_echo_secret_input(team_client):
    client, headers = team_client
    response = client.post(
        "/api/catalog/services",
        headers=headers,
        json={
            "name": "Invalid",
            "url": "https://example.org/",
            "headers": {"Authorization": "private-secret-value"},
        },
    )
    assert response.status_code == 422
    assert "private-secret-value" not in response.text
    assert isinstance(response.json()["detail"], list)
