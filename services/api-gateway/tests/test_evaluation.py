from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_default_app, extract_grounded_actions
from app.services.evaluation import evaluate_answer


REPO_ROOT = Path(__file__).resolve().parents[3]

def test_extract_grounded_actions_prefers_action_sections() -> None:
    actions = extract_grounded_actions(
        """# SOP-12

## Risk Rules
- Do not mark an event high risk without evidence.

## First Actions
1. Call the on-site safety manager.
2. Dispatch the nearest responder.

## Escalation
- Send an alert to the safety operations channel.
"""
    )
    assert actions == [
        "Call the on-site safety manager.",
        "Dispatch the nearest responder.",
        "Send an alert to the safety operations channel.",
    ]


def test_evaluation_harness_scores_expected_terms() -> None:
    score = evaluate_answer(
        "The event is high risk because evidence exists and SOP-12 requires escalation.",
        ["high risk", "SOP-12", "evidence"],
    )
    assert score == 1.0


def test_golden_evaluation_endpoint(client) -> None:
    client.post(
        "/api/v1/documents",
        files={"file": ("policy.md", b"# SOP-12\n1. Call the safety manager immediately.", "text/markdown")},
        data={"title": "SOP-12"},
    )
    source = client.post(
        "/api/v1/sources/files",
        files={"file": ("fall_demo.mp4", b"fake bytes", "video/mp4")},
        data={"source_name": "fall_demo"},
    ).json()
    client.post(
        "/api/v1/inference/jobs",
        json={
            "source_id": source["source_id"],
            "model_name": "demo-fall-detector",
            "model_version": "v1",
            "backend_type": "demo",
        },
    )

    response = client.get("/api/v1/evaluations/golden")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cases"]
    assert payload["average_score"] >= 0.66


def test_document_search_metrics_and_ui_routes(client) -> None:
    doc_resp = client.post(
        "/ui/documents",
        files={"file": ((REPO_ROOT / "datasets/documents/sample_safety_sop.md").name, (REPO_ROOT / "datasets/documents/sample_safety_sop.md").read_bytes(), "text/markdown")},
        data={"title": "SOP-12", "version": "v1"},
        follow_redirects=False,
    )
    assert doc_resp.status_code == 303

    source_resp = client.post(
        "/ui/sources/files",
        files={"file": ("fall_demo.mp4", b"fake bytes", "video/mp4")},
        data={"source_name": "fall_demo"},
        follow_redirects=False,
    )
    assert source_resp.status_code == 303

    sources = client.get("/api/v1/sources").json()["items"]
    assert len(sources) == 1
    source_id = sources[0]["source_id"]

    run_resp = client.post(
        "/ui/inference/jobs",
        data={"source_id": source_id},
        follow_redirects=False,
    )
    assert run_resp.status_code == 303
    event_path = run_resp.headers["location"]
    event_page = client.get(event_path)
    assert event_page.status_code == 200
    assert "Raw Detections" in event_page.text

    event_id = event_path.rsplit("/", 1)[-1]
    report_resp = client.post(f"/ui/events/{event_id}/reports", follow_redirects=False)
    assert report_resp.status_code == 303

    qa_resp = client.post(
        f"/ui/events/{event_id}/qa",
        data={"question": "Why is this event high risk?"},
        follow_redirects=False,
    )
    assert qa_resp.status_code == 303

    search_resp = client.get("/api/v1/documents/search", params={"q": "safety manager", "limit": 2})
    assert search_resp.status_code == 200
    search_payload = search_resp.json()
    assert search_payload["items"]
    assert search_payload["items"][0]["document_title"] == "SOP-12"

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "eventops_http_requests_total" in metrics_resp.text


def test_api_token_protects_api(tmp_path: Path) -> None:
    app = create_default_app(
        database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
        storage_root=tmp_path / "storage",
        seed_sample_data=False,
        notification_mode="record",
        api_token="secret-token",
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/sources").status_code == 401
        assert client.get("/api/v1/sources", headers={"x-api-token": "secret-token"}).status_code == 200

def test_app_bootstraps_legacy_inference_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE inference_jobs (id VARCHAR(40) PRIMARY KEY, source_id VARCHAR(40), model_name VARCHAR(255), model_version VARCHAR(80), backend_type VARCHAR(80), status VARCHAR(30), started_at DATETIME, completed_at DATETIME)"
            )
        )
    app = create_default_app(
        database_url=database_url,
        storage_root=tmp_path / "legacy-storage",
        seed_sample_data=False,
        notification_mode="record",
    )
    with TestClient(app) as client:
        source = client.post(
            "/api/v1/sources/files",
            files={"file": ("fall_demo.mp4", b"fake bytes", "video/mp4")},
            data={"source_name": "fall_demo"},
        )
        assert source.status_code == 201
        source_id = source.json()["source_id"]

        job = client.post(
            "/api/v1/inference/jobs",
            json={
                "source_id": source_id,
                "model_name": "demo-fall-detector",
                "model_version": "v1",
                "backend_type": "demo",
                "threshold": 0.7,
            },
        )
        assert job.status_code == 201

        events = client.get("/api/v1/events")
        assert events.status_code == 200
        assert events.json()["total"] == 1






