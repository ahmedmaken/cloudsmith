"""Tests for the API endpoints."""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src import database


@pytest.fixture
def client():
    """Create a test client with fresh in-memory database."""
    # Override to use in-memory database
    import duckdb
    database._conn = duckdb.connect(":memory:")
    database.init_schema(database._conn)
    
    with TestClient(app) as client:
        yield client
    
    database._conn.close()
    database._conn = None


@pytest.fixture
def client_with_data(client, sample_events):
    """Create a test client with pre-populated data."""
    # Create temp file with events
    with tempfile.NamedTemporaryFile(mode='w', suffix=".jsonl", delete=False) as f:
        for event in sample_events:
            f.write(json.dumps(event) + "\n")
        file_path = f.name
    
    try:
        # Ingest the events
        response = client.post(f"/ingest?file_path={file_path}")
        assert response.status_code == 200
        yield client
    finally:
        os.unlink(file_path)


def test_health_check(client):
    """Test health check returns healthy status."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "events_count" in data


def test_ingest_events(client, sample_events):
    """Test ingesting events via API."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".jsonl", delete=False) as f:
        for event in sample_events:
            f.write(json.dumps(event) + "\n")
        file_path = f.name
    
    try:
        response = client.post(f"/ingest?file_path={file_path}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["ingested"] == 4
    finally:
        os.unlink(file_path)


def test_ingest_file_not_found(client):
    """Test ingestion with non-existent file."""
    response = client.post("/ingest?file_path=/nonexistent/file.jsonl")
    assert response.status_code == 404


def test_query_events_requires_tenant_id(client):
    """Test that tenant_id is required."""
    response = client.get("/events")
    assert response.status_code == 422  # Validation error


def test_query_events_by_tenant(client_with_data):
    """Test querying events by tenant."""
    response = client_with_data.get("/events?tenant_id=tenant_a")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # 3 events for tenant_a
    assert all(e["tenant_id"] == "tenant_a" for e in data["events"])


def test_query_events_tenant_isolation(client_with_data):
    """Test that tenant_a cannot see tenant_b's data."""
    response = client_with_data.get("/events?tenant_id=tenant_a")
    data = response.json()
    
    # Should not include tenant_b's event
    assert all(e["tenant_id"] == "tenant_a" for e in data["events"])


def test_query_events_filter_by_action(client_with_data):
    """Test filtering events by action type."""
    response = client_with_data.get("/events?tenant_id=tenant_a&action=download")
    
    assert response.status_code == 200
    data = response.json()
    assert all(e["action"] == "download" for e in data["events"])


def test_query_events_filter_by_package(client_with_data):
    """Test filtering events by package."""
    response = client_with_data.get("/events?tenant_id=tenant_a&package=requests")
    
    assert response.status_code == 200
    data = response.json()
    assert all(e["package"] == "requests" for e in data["events"])


def test_query_events_invalid_action(client):
    """Test that invalid action returns error."""
    response = client.get("/events?tenant_id=tenant_a&action=invalid")
    assert response.status_code == 400
