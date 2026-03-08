from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_end_to_end_event_report_workflow(client) -> None:
    document_upload = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "sample_safety_sop.md",
                (REPO_ROOT / "datasets/documents/sample_safety_sop.md").read_bytes(),
                "text/markdown",
            )
        },
        data={"title": "SOP-12"},
    )
    assert document_upload.status_code == 201
    assert document_upload.json()["chunk_count"] >= 1

    source_upload = client.post(
        "/api/v1/sources/files",
        files={"file": ("fall_demo.mp4", b"fake mp4 bytes", "video/mp4")},
        data={"source_name": "fall_demo"},
    )
    assert source_upload.status_code == 201
    source_id = source_upload.json()["source_id"]

    inference_job = client.post(
        "/api/v1/inference/jobs",
        json={
            "source_id": source_id,
            "model_name": "demo-fall-detector",
            "model_version": "v1",
            "backend_type": "demo",
            "threshold": 0.65,
        },
    )
    assert inference_job.status_code == 201
    job_id = inference_job.json()["job_id"]

    job_detail = client.get(f"/api/v1/inference/jobs/{job_id}")
    assert job_detail.status_code == 200
    assert job_detail.json()["threshold"] == 0.65

    events_response = client.get("/api/v1/events")
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert len(events) == 1
    assert events[0]["event_type"] == "fall"
    assert events[0]["risk_level"] == "high"
    event_id = events[0]["event_id"]

    report_response = client.post("/api/v1/reports/generate", json={"event_id": event_id})
    assert report_response.status_code == 201
    report_payload = report_response.json()
    assert report_payload["summary"]
    assert report_payload["risk_level"] == "high"
    assert "SOP-12" in report_payload["policy_refs"]
    assert report_payload["recommended_actions"]

    detail_response = client.get(f"/api/v1/events/{event_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["report"]["summary"]
    assert detail["evidence"]
    assert detail["raw_detections"]
    assert detail["trace"]["states"]

    review_response = client.patch(
        f"/api/v1/events/{event_id}",
        json={"status": "reviewed", "operator_feedback": "validated by operator"},
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["status"] == "reviewed"
    assert reviewed["operator_feedback"] == "validated by operator"

    metrics_response = client.get("/api/v1/metrics/summary")
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert metrics["sources_total"] == 1
    assert metrics["jobs_total"] == 1
    assert metrics["events_total"] == 1
    assert metrics["raw_detections_total"] == 1
    assert metrics["reports_total"] == 1

