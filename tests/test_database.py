"""Tests for the database module."""

from datetime import datetime, timedelta, timezone

import pytest

from src.database import insert_event, query_events, get_event_count


def test_insert_event(temp_db):
    """Test inserting a single event."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-1"
    }
    
    result = insert_event(temp_db, event)
    assert result is True
    assert get_event_count(temp_db) == 1


def test_insert_duplicate_event(temp_db):
    """Test that duplicate events are rejected."""
    event = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-1"
    }
    
    # First insert succeeds
    assert insert_event(temp_db, event) is True
    
    # Duplicate fails
    assert insert_event(temp_db, event) is False
    assert get_event_count(temp_db) == 1


def test_same_event_id_different_tenants(temp_db):
    """Test that same event_id is allowed for different tenants."""
    event_a = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-1"
    }
    
    event_b = {
        "event_id": "evt_001",  # Same event_id
        "tenant_id": "tenant_b",  # Different tenant
        "action": "upload",
        "package": "numpy",
        "version": "1.24.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-2"
    }
    
    assert insert_event(temp_db, event_a) is True
    assert insert_event(temp_db, event_b) is True
    assert get_event_count(temp_db) == 2


def test_query_events_tenant_isolation(temp_db):
    """Test that queries only return events for the specified tenant."""
    event_a = {
        "event_id": "evt_001",
        "tenant_id": "tenant_a",
        "action": "download",
        "package": "requests",
        "version": "2.28.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-1"
    }
    
    event_b = {
        "event_id": "evt_002",
        "tenant_id": "tenant_b",
        "action": "upload",
        "package": "numpy",
        "version": "1.24.0",
        "timestamp": datetime.now(timezone.utc),
        "actor": "user-2"
    }
    
    insert_event(temp_db, event_a)
    insert_event(temp_db, event_b)
    
    # Query for tenant_a - should only get their event
    events, total = query_events(temp_db, tenant_id="tenant_a")
    assert total == 1
    assert len(events) == 1
    assert events[0]["tenant_id"] == "tenant_a"
    
    # Query for tenant_b - should only get their event
    events, total = query_events(temp_db, tenant_id="tenant_b")
    assert total == 1
    assert len(events) == 1
    assert events[0]["tenant_id"] == "tenant_b"


def test_query_events_filter_by_action(temp_db):
    """Test filtering events by action type."""
    events_data = [
        {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "pkg1", "version": "1.0", "timestamp": datetime.now(timezone.utc), "actor": "user1"},
        {"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", "package": "pkg2", "version": "1.0", "timestamp": datetime.now(timezone.utc), "actor": "user1"},
        {"event_id": "evt_003", "tenant_id": "tenant_a", "action": "download", "package": "pkg3", "version": "1.0", "timestamp": datetime.now(timezone.utc), "actor": "user1"},
    ]
    
    for e in events_data:
        insert_event(temp_db, e)
    
    events, total = query_events(temp_db, tenant_id="tenant_a", action="download")
    assert total == 2


def test_query_events_filter_by_package(temp_db):
    """Test filtering events by package name."""
    events_data = [
        {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", "package": "requests", "version": "1.0", "timestamp": datetime.now(timezone.utc), "actor": "user1"},
        {"event_id": "evt_002", "tenant_id": "tenant_a", "action": "download", "package": "numpy", "version": "1.0", "timestamp": datetime.now(timezone.utc), "actor": "user1"},
    ]
    
    for e in events_data:
        insert_event(temp_db, e)
    
    events, total = query_events(temp_db, tenant_id="tenant_a", package="requests")
    assert total == 1
    assert events[0]["package"] == "requests"
