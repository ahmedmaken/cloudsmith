"""Tests for the FastAPI application."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.database import EventDatabase, get_database, reset_database
from src.models import AuditEvent


@pytest.fixture
def client():
    """Create a test client."""
    # Use in-memory database for testing
    reset_database()
    with TestClient(app) as client:
        yield client
    reset_database()


@pytest.fixture
def populated_client(client, sample_events):
    """Create a test client with pre-populated data."""
    # Create a temp file with events
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
    ) as f:
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


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "events_count" in data


class TestIngestionEndpoint:
    """Tests for the ingestion endpoint."""
    
    def test_ingest_events(self, client, sample_events):
        """Test ingesting events via API."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")
            file_path = f.name
        
        try:
            response = client.post(f"/ingest?file_path={file_path}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_processed"] == 4
            assert data["successfully_ingested"] == 4
        finally:
            os.unlink(file_path)
    
    def test_ingest_file_not_found(self, client):
        """Test ingestion with non-existent file."""
        response = client.post("/ingest?file_path=/nonexistent/file.jsonl")
        
        assert response.status_code == 404


class TestEventsEndpoint:
    """Tests for the events query endpoint."""
    
    def test_query_events_requires_tenant_id(self, client):
        """Test that tenant_id is required."""
        response = client.get("/events")
        
        assert response.status_code == 422  # Validation error
    
    def test_query_events_by_tenant(self, populated_client):
        """Test querying events by tenant."""
        response = populated_client.get("/events?tenant_id=tenant_a")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3  # tenant_a has 3 events
        assert all(e["tenant_id"] == "tenant_a" for e in data["events"])
    
    def test_query_events_tenant_isolation(self, populated_client):
        """Test that tenant_a cannot see tenant_b's events."""
        response = populated_client.get("/events?tenant_id=tenant_a")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify no tenant_b events are returned
        tenant_ids = [e["tenant_id"] for e in data["events"]]
        assert "tenant_b" not in tenant_ids
    
    def test_query_events_by_action(self, populated_client):
        """Test filtering by action type."""
        response = populated_client.get(
            "/events?tenant_id=tenant_a&action=download"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Two download events for tenant_a
        assert all(e["action"] == "download" for e in data["events"])
    
    def test_query_events_by_package(self, populated_client):
        """Test filtering by package name."""
        response = populated_client.get(
            "/events?tenant_id=tenant_a&package=requests"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Two requests events for tenant_a
        assert all(e["package"] == "requests" for e in data["events"])
    
    def test_query_events_by_time_range(self, populated_client):
        """Test filtering by time range."""
        response = populated_client.get(
            "/events?tenant_id=tenant_a"
            "&start_time=2025-03-15T00:00:00Z"
            "&end_time=2025-03-15T23:59:59Z"
        )
        
        assert response.status_code == 200
        data = response.json()
        # evt_004 is from March 14, should be excluded
        assert data["total"] == 2
    
    def test_query_events_pagination(self, populated_client):
        """Test pagination of results."""
        # Get first page
        response = populated_client.get(
            "/events?tenant_id=tenant_a&limit=2&offset=0"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0
        
        # Get second page
        response = populated_client.get(
            "/events?tenant_id=tenant_a&limit=2&offset=2"
        )
        
        data = response.json()
        assert len(data["events"]) == 1
    
    def test_query_events_invalid_action(self, client):
        """Test that invalid action type returns validation error."""
        response = client.get("/events?tenant_id=test&action=invalid")
        
        assert response.status_code == 422


class TestTenantsEndpoint:
    """Tests for the tenants endpoint."""
    
    def test_list_tenants(self, populated_client):
        """Test listing all tenants."""
        response = populated_client.get("/tenants")
        
        assert response.status_code == 200
        data = response.json()
        assert "tenant_a" in data
        assert "tenant_b" in data


class TestRetentionEndpoint:
    """Tests for the retention policy endpoint."""
    
    def test_get_retention_config(self, client):
        """Test getting retention configuration."""
        response = client.get("/retention/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "retention_days" in data
    
    def test_apply_retention(self, client, sample_events):
        """Test applying retention policy."""
        # First ingest some events
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")
            file_path = f.name
        
        try:
            client.post(f"/ingest?file_path={file_path}")
            
            # Apply retention (all events are from March 2025, they're old)
            response = client.post("/retention/apply?retention_days=30")
            
            assert response.status_code == 200
            data = response.json()
            assert "deleted_count" in data
            assert data["retention_days"] == 30
        finally:
            os.unlink(file_path)
