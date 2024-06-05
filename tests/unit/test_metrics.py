from fastapi import FastAPI
from fastapi.testclient import TestClient

from grug.metrics import initialize_metrics


def test_initialize_metrics():
    app = FastAPI()
    initialize_metrics(app)
    client = TestClient(app)

    response = client.get("/metrics")
    assert response.status_code == 200
