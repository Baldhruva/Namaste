import pytest
from fastapi.testclient import TestClient

import os
import sys
from pathlib import Path

# Ensure we import the app from this project's directory, not any top-level main.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_icd11_found():
    resp = client.get("/search_icd11", params={"keyword": "diabetes"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any("diabetes" in item["title"].lower() for item in data)


def test_search_icd11_not_found():
    resp = client.get("/search_icd11", params={"keyword": "zzzzzz"})
    assert resp.status_code == 404


def test_namaste_mapping():
    resp = client.post("/map_namaste", json={"namaste_code": "NAM-AYU-001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["icd11_code"] == "5A11"


def test_ehr_integration_requires_auth():
    # Without token
    resp = client.post("/ehr_integration", json={
        "name": "John Doe", "age": 40, "gender": "male", "diagnosis": "Diabetes", "icd11_code": "5A11"
    })
    assert resp.status_code in (401, 403)


def test_ehr_integration_with_auth():
    # Login
    login = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Call endpoint
    resp = client.post(
        "/ehr_integration",
        json={
            "name": "Jane Doe",
            "age": 35,
            "gender": "female",
            "diagnosis": "Headache",
            "icd11_code": "MG30.0",
            "namaste_code": "NAM-AYU-003",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient"]["name"] == "Jane Doe"
    assert data["fhir"]["resourceType"] == "Bundle"
