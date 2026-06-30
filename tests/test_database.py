"""Tests for the database layer."""

from datetime import datetime, timedelta, timezone

import pytest

from src.database import EventDatabase
from src.models import AuditEvent, EventQuery


class TestEventDatabase:
    """Tests for EventDatabase functionality."""
    
    def test_insert_event(self, temp_db):
        """Test inserting a single event."""
        event = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-1"
        )
        
        result = temp_db.insert_event(event)
        assert result is True
        assert temp_db.get_event_count() == 1
    
    def test_insert_duplicate_event(self, temp_db):
        """Test that duplicate events are handled correctly."""
        event = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-1"
        )
        
        # Insert first time
        temp_db.insert_event(event)
        
        # Insert duplicate - should not increase count
        result = temp_db.insert_event(event)
        assert result is False
        assert temp_db.get_event_count() == 1
    
    def test_tenant_isolation_same_event_id_different_tenant(self, temp_db):
        """Test that same event_id can exist for different tenants."""
        event_a = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-1"
        )
        
        event_b = AuditEvent(
            event_id="evt_001",  # Same event_id
            tenant_id="tenant_b",  # Different tenant
            action="upload",
            package="numpy",
            version="1.24.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-2"
        )
        
        temp_db.insert_event(event_a)
        temp_db.insert_event(event_b)
        
        # Both should be inserted
        assert temp_db.get_event_count() == 2
    
    def test_query_events_tenant_isolation(self, temp_db):
        """Test that queries only return events for the specified tenant."""
        # Insert events for two tenants
        event_a = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-1"
        )
        
        event_b = AuditEvent(
            event_id="evt_002",
            tenant_id="tenant_b",
            action="upload",
            package="numpy",
            version="1.24.0",
            timestamp=datetime.now(timezone.utc),
            actor="user-2"
        )
        
        temp_db.insert_event(event_a)
        temp_db.insert_event(event_b)
        
        # Query for tenant_a
        query = EventQuery(tenant_id="tenant_a")
        events, total = temp_db.query_events(query)
        
        assert total == 1
        assert len(events) == 1
        assert events[0]["tenant_id"] == "tenant_a"
        assert events[0]["event_id"] == "evt_001"
    
    def test_query_events_by_action(self, temp_db):
        """Test filtering events by action type."""
        events = [
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-1"
            ),
            AuditEvent(
                event_id="evt_002",
                tenant_id="tenant_a",
                action="upload",
                package="numpy",
                version="1.24.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-2"
            ),
            AuditEvent(
                event_id="evt_003",
                tenant_id="tenant_a",
                action="download",
                package="flask",
                version="2.0.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-3"
            )
        ]
        
        for event in events:
            temp_db.insert_event(event)
        
        query = EventQuery(tenant_id="tenant_a", action="download")
        results, total = temp_db.query_events(query)
        
        assert total == 2
        assert all(e["action"] == "download" for e in results)
    
    def test_query_events_by_time_range(self, temp_db):
        """Test filtering events by time range."""
        now = datetime.now(timezone.utc)
        
        events = [
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp=now - timedelta(days=5),
                actor="user-1"
            ),
            AuditEvent(
                event_id="evt_002",
                tenant_id="tenant_a",
                action="upload",
                package="numpy",
                version="1.24.0",
                timestamp=now - timedelta(days=2),
                actor="user-2"
            ),
            AuditEvent(
                event_id="evt_003",
                tenant_id="tenant_a",
                action="download",
                package="flask",
                version="2.0.0",
                timestamp=now,
                actor="user-3"
            )
        ]
        
        for event in events:
            temp_db.insert_event(event)
        
        # Query for events in the last 3 days
        query = EventQuery(
            tenant_id="tenant_a",
            start_time=now - timedelta(days=3)
        )
        results, total = temp_db.query_events(query)
        
        assert total == 2  # evt_002 and evt_003
    
    def test_query_events_by_package(self, temp_db):
        """Test filtering events by package name."""
        events = [
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-1"
            ),
            AuditEvent(
                event_id="evt_002",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.1",
                timestamp=datetime.now(timezone.utc),
                actor="user-2"
            ),
            AuditEvent(
                event_id="evt_003",
                tenant_id="tenant_a",
                action="download",
                package="numpy",
                version="1.24.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-3"
            )
        ]
        
        for event in events:
            temp_db.insert_event(event)
        
        query = EventQuery(tenant_id="tenant_a", package="requests")
        results, total = temp_db.query_events(query)
        
        assert total == 2
        assert all(e["package"] == "requests" for e in results)
    
    def test_query_events_pagination(self, temp_db):
        """Test pagination of query results."""
        # Insert 10 events
        for i in range(10):
            event = AuditEvent(
                event_id=f"evt_{i:03d}",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version=f"2.{i}.0",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                actor="user-1"
            )
            temp_db.insert_event(event)
        
        # Get first page
        query = EventQuery(tenant_id="tenant_a", limit=3, offset=0)
        results, total = temp_db.query_events(query)
        
        assert total == 10
        assert len(results) == 3
        
        # Get second page
        query = EventQuery(tenant_id="tenant_a", limit=3, offset=3)
        results2, _ = temp_db.query_events(query)
        
        assert len(results2) == 3
        # Verify no overlap
        result_ids = [e["event_id"] for e in results + results2]
        assert len(result_ids) == len(set(result_ids))
    
    def test_retention_policy(self, temp_db):
        """Test that retention policy deletes old events."""
        now = datetime.now(timezone.utc)
        
        events = [
            AuditEvent(
                event_id="evt_old",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp=now - timedelta(days=100),
                actor="user-1"
            ),
            AuditEvent(
                event_id="evt_new",
                tenant_id="tenant_a",
                action="upload",
                package="numpy",
                version="1.24.0",
                timestamp=now - timedelta(days=10),
                actor="user-2"
            )
        ]
        
        for event in events:
            temp_db.insert_event(event)
        
        assert temp_db.get_event_count() == 2
        
        # Apply 30-day retention
        deleted = temp_db.apply_retention_policy(30)
        
        assert deleted == 1
        assert temp_db.get_event_count() == 1
        
        # Verify correct event remains
        query = EventQuery(tenant_id="tenant_a")
        results, _ = temp_db.query_events(query)
        assert results[0]["event_id"] == "evt_new"
    
    def test_get_tenants(self, temp_db):
        """Test listing all tenant IDs."""
        events = [
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-1"
            ),
            AuditEvent(
                event_id="evt_002",
                tenant_id="tenant_b",
                action="upload",
                package="numpy",
                version="1.24.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-2"
            ),
            AuditEvent(
                event_id="evt_003",
                tenant_id="tenant_a",
                action="delete",
                package="flask",
                version="2.0.0",
                timestamp=datetime.now(timezone.utc),
                actor="user-3"
            )
        ]
        
        for event in events:
            temp_db.insert_event(event)
        
        tenants = temp_db.get_tenants()
        
        assert len(tenants) == 2
        assert "tenant_a" in tenants
        assert "tenant_b" in tenants
