"""Tests for data models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import ActionType, AuditEvent, EventQuery


class TestAuditEvent:
    """Tests for the AuditEvent model."""
    
    def test_valid_event(self):
        """Test creating a valid event."""
        event = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp="2025-03-15T10:00:00+00:00",
            actor="user-1"
        )
        
        assert event.event_id == "evt_001"
        assert event.tenant_id == "tenant_a"
        assert event.action == "download"
        assert event.package == "requests"
        assert event.version == "2.28.0"
        assert event.actor == "user-1"
    
    def test_event_with_datetime_timestamp(self):
        """Test creating an event with datetime object."""
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id="evt_001",
            tenant_id="tenant_a",
            action="download",
            package="requests",
            version="2.28.0",
            timestamp=now,
            actor="user-1"
        )
        
        assert event.timestamp == now
    
    def test_event_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                # Missing package
                version="2.28.0",
                timestamp="2025-03-15T10:00:00+00:00",
                actor="user-1"
            )
    
    def test_event_invalid_action(self):
        """Test that invalid action type raises validation error."""
        with pytest.raises(ValidationError):
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="invalid_action",
                package="requests",
                version="2.28.0",
                timestamp="2025-03-15T10:00:00+00:00",
                actor="user-1"
            )
    
    def test_event_empty_timestamp(self):
        """Test that empty timestamp raises validation error."""
        with pytest.raises(ValidationError):
            AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action="download",
                package="requests",
                version="2.28.0",
                timestamp="",
                actor="user-1"
            )
    
    def test_event_all_action_types(self):
        """Test that all action types are valid."""
        for action in ["download", "upload", "delete"]:
            event = AuditEvent(
                event_id="evt_001",
                tenant_id="tenant_a",
                action=action,
                package="requests",
                version="2.28.0",
                timestamp="2025-03-15T10:00:00+00:00",
                actor="user-1"
            )
            assert event.action == action


class TestActionType:
    """Tests for the ActionType enum."""
    
    def test_action_type_values(self):
        """Test ActionType enum values."""
        assert ActionType.DOWNLOAD.value == "download"
        assert ActionType.UPLOAD.value == "upload"
        assert ActionType.DELETE.value == "delete"
    
    def test_action_type_from_string(self):
        """Test creating ActionType from string."""
        assert ActionType("download") == ActionType.DOWNLOAD
        assert ActionType("upload") == ActionType.UPLOAD
        assert ActionType("delete") == ActionType.DELETE


class TestEventQuery:
    """Tests for the EventQuery model."""
    
    def test_valid_query_minimal(self):
        """Test creating a minimal valid query."""
        query = EventQuery(tenant_id="tenant_a")
        
        assert query.tenant_id == "tenant_a"
        assert query.limit == 100
        assert query.offset == 0
    
    def test_valid_query_full(self):
        """Test creating a full query with all parameters."""
        query = EventQuery(
            tenant_id="tenant_a",
            start_time="2025-03-01T00:00:00+00:00",
            end_time="2025-03-31T23:59:59+00:00",
            action="download",
            package="requests",
            limit=50,
            offset=10
        )
        
        assert query.tenant_id == "tenant_a"
        assert query.action == "download"
        assert query.package == "requests"
        assert query.limit == 50
        assert query.offset == 10
    
    def test_query_missing_tenant_id(self):
        """Test that missing tenant_id raises validation error."""
        with pytest.raises(ValidationError):
            EventQuery()
    
    def test_query_limit_bounds(self):
        """Test limit validation bounds."""
        # Valid minimum
        query = EventQuery(tenant_id="test", limit=1)
        assert query.limit == 1
        
        # Valid maximum
        query = EventQuery(tenant_id="test", limit=1000)
        assert query.limit == 1000
        
        # Invalid: below minimum
        with pytest.raises(ValidationError):
            EventQuery(tenant_id="test", limit=0)
        
        # Invalid: above maximum
        with pytest.raises(ValidationError):
            EventQuery(tenant_id="test", limit=1001)
    
    def test_query_offset_bounds(self):
        """Test offset validation bounds."""
        # Valid minimum
        query = EventQuery(tenant_id="test", offset=0)
        assert query.offset == 0
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            EventQuery(tenant_id="test", offset=-1)
