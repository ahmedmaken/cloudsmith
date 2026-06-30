"""Test fixtures for pytest."""

import json
import os
import tempfile

import pytest
import duckdb

from src import database


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    # Use in-memory database
    conn = duckdb.connect(":memory:")
    database.init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_events():
    """Sample valid events for testing."""
    return [
        {
            "event_id": "evt_001",
            "tenant_id": "tenant_a",
            "action": "download",
            "package": "requests",
            "version": "2.28.0",
            "timestamp": "2025-03-15T10:00:00+00:00",
            "actor": "user-1"
        },
        {
            "event_id": "evt_002",
            "tenant_id": "tenant_a",
            "action": "upload",
            "package": "numpy",
            "version": "1.24.0",
            "timestamp": "2025-03-15T11:00:00+00:00",
            "actor": "user-2"
        },
        {
            "event_id": "evt_003",
            "tenant_id": "tenant_b",
            "action": "delete",
            "package": "flask",
            "version": "2.0.0",
            "timestamp": "2025-03-15T12:00:00+00:00",
            "actor": "user-3"
        },
        {
            "event_id": "evt_004",
            "tenant_id": "tenant_a",
            "action": "download",
            "package": "requests",
            "version": "2.28.1",
            "timestamp": "2025-03-14T09:00:00+00:00",
            "actor": "user-1"
        }
    ]


@pytest.fixture
def temp_events_file(sample_events):
    """Create a temp file with sample events."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".jsonl", delete=False) as f:
        for event in sample_events:
            f.write(json.dumps(event) + "\n")
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def temp_events_file_with_issues():
    """Create a temp file with some malformed events."""
    events = [
        '{"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"}',
        '{invalid json',  # Malformed
        '{"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"}',  # Duplicate
        '{"event_id": "evt_002", "tenant_id": "tenant_a", "action": "download", "package": "pkg2", "version": "1.0", "timestamp": "", "actor": "user2"}',  # Empty timestamp
        '{"event_id": "evt_003", "tenant_id": "tenant_a", "action": "download", "package": "pkg3", "version": "1.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user3"}'
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix=".jsonl", delete=False) as f:
        for line in events:
            f.write(line + "\n")
        path = f.name
    yield path
    os.unlink(path)
