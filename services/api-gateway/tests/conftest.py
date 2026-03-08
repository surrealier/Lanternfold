from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_default_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_default_app(
        database_url=f"sqlite:///{(tmp_path / 'eventops.db').as_posix()}",
        storage_root=tmp_path / "storage",
        seed_sample_data=False,
        notification_mode="record",
    )
    with TestClient(app) as test_client:
        yield test_client