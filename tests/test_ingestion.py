"""Tests for the ingestion module."""

import json
import os
import tempfile

import pytest
import duckdb

from src import database
from src.ingestion import ingest_events, validate_event


@pytest.fixture
def temp_db_for_ingestion():
    """Set up a temp database for ingestion tests."""
    # Use a temp file for database
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    os.unlink(db_path)  # DuckDB needs to create it
    
    # Override the global connection
    database._conn = duckdb.connect(db_path)
    database.init_schema(database._conn)
    
    yield database._conn
    
    database._conn.close()
    database._conn = None
    try:
        os.unlink(db_path)
    except:
        pass


def test_validate_event_valid():
    """Test validation of a valid event."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": "2025-03-15T10:00:00+00:00",
        "actor": "user-1"
    }
    is_valid, error = validate_event(event)
    assert is_valid is True
    assert error is None


def test_validate_event_missing_field():
    """Test validation fails for missing fields."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        # Missing action
        "package": "requests",
        "version": "2.28.0",
        "timestamp": "2025-03-15T10:00:00+00:00",
        "actor": "user-1"
    }
    is_valid, error = validate_event(event)
    assert is_valid is False
    assert "Missing field" in error


def test_validate_event_invalid_action():
    """Test validation fails for invalid action."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "invalid_action",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": "2025-03-15T10:00:00+00:00",
        "actor": "user-1"
    }
    is_valid, error = validate_event(event)
    assert is_valid is False
    assert "Invalid action" in error


def test_validate_event_empty_timestamp():
    """Test validation fails for empty timestamp."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": "",
        "actor": "user-1"
    }
    is_valid, error = validate_event(event)
    assert is_valid is False
    assert "Empty timestamp" in error


def test_ingest_valid_events(temp_db_for_ingestion, temp_events_file):
    """Test ingesting valid events from a file."""
    stats = ingest_events(temp_events_file)
    
    assert stats["total"] == 4
    assert stats["ingested"] == 4
    assert stats["duplicates"] == 0
    assert stats["malformed"] == 0


def test_ingest_handles_malformed_json(temp_db_for_ingestion, temp_events_file_with_issues):
    """Test that malformed JSON entries are skipped."""
    stats = ingest_events(temp_events_file_with_issues)
    
    # File has: 1 valid, 1 malformed JSON, 1 duplicate, 1 empty timestamp, 1 valid
    assert stats["ingested"] == 2
    assert stats["duplicates"] == 1
    assert stats["malformed"] == 2


def test_ingest_handles_duplicates(temp_db_for_ingestion):
    """Test that duplicate events are skipped."""
    events = [
        {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", 
         "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"},
        {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", 
         "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"},
        {"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", 
         "package": "pkg2", "version": "1.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user2"},
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix=".jsonl", delete=False) as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
        file_path = f.name
    
    try:
        stats = ingest_events(file_path)
        
        assert stats["total"] == 3
        assert stats["ingested"] == 2
        assert stats["duplicates"] == 1
    finally:
        os.unlink(file_path)
