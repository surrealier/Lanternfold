def test_operator_qa_is_grounded_and_dashboard_renders(client) -> None:
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
    event_id = client.get("/api/v1/events").json()["items"][0]["event_id"]
    client.post("/api/v1/reports/generate", json={"event_id": event_id})

    qa_response = client.post(
        "/api/v1/qa",
        json={"event_id": event_id, "question": "Why is this event high risk?"},
    )
    assert qa_response.status_code == 200
    qa_payload = qa_response.json()
    assert "high risk" in qa_payload["answer"].lower()
    assert qa_payload["citations"]

    dashboard_response = client.get("/")
    assert dashboard_response.status_code == 200
    assert "Upload Video Source" in dashboard_response.text
    assert "Registered Sources" in dashboard_response.text

    detail_page = client.get(f"/events/{event_id}")
    assert detail_page.status_code == 200
    assert "Recommended Actions" in detail_page.text
    assert "Operator QA" in detail_page.text

