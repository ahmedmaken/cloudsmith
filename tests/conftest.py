"""Test fixtures and configuration for pytest."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from src.database import EventDatabase, reset_database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create a temp file name but delete the file so DuckDB can create it fresh
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    
    # Delete the empty file - DuckDB needs to create it fresh
    os.unlink(db_path)
    
    db = EventDatabase(db_path)
    yield db
    
    db.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass
    # Also clean up any WAL files
    try:
        os.unlink(db_path + ".wal")
    except OSError:
        pass


@pytest.fixture
def sample_events():
    """Sample events for testing."""
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
    """Create a temporary events file for testing."""
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
    ) as f:
        for event in sample_events:
            f.write(json.dumps(event) + "\n")
        file_path = f.name
    
    yield file_path
    
    try:
        os.unlink(file_path)
    except OSError:
        pass


@pytest.fixture
def temp_events_file_with_issues():
    """Create a temporary events file with malformed entries and duplicates."""
    events = [
        '{"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"}',
        '{malformed json',  # Malformed
        '{"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"}',  # Duplicate
        '{"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", "package": "pkg2", "version": "1.0", "timestamp": "", "actor": "user2"}',  # Empty timestamp
        '{"event_id": "evt_003", "tenant_id": "tenant_b", "action": "download", "package": "pkg3", "version": "2.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user3"}',
    ]
    
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
    ) as f:
        for event in events:
            f.write(event + "\n")
        file_path = f.name
    
    yield file_path
    
    try:
        os.unlink(file_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def cleanup_database():
    """Clean up the global database after each test."""
    yield
    reset_database()
