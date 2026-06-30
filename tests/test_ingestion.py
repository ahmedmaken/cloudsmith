"""Tests for the ingestion module."""

import json
import tempfile
import os

import pytest

from src.database import EventDatabase
from src.ingestion import EventIngester


class TestEventIngester:
    """Tests for EventIngester functionality."""
    
    def test_ingest_valid_events(self, temp_db, temp_events_file):
        """Test ingesting valid events from a file."""
        ingester = EventIngester(temp_db)
        stats = ingester.ingest_file(temp_events_file)
        
        assert stats.total_processed == 4
        assert stats.successfully_ingested == 4
        assert stats.duplicates_skipped == 0
        assert stats.malformed_skipped == 0
        assert len(stats.errors) == 0
    
    def test_ingest_handles_malformed_json(self, temp_db, temp_events_file_with_issues):
        """Test that malformed JSON entries are skipped."""
        ingester = EventIngester(temp_db)
        stats = ingester.ingest_file(temp_events_file_with_issues)
        
        # Should have: 1 valid, 1 malformed, 1 duplicate, 1 empty timestamp, 1 valid
        assert stats.total_processed == 5
        assert stats.successfully_ingested == 2  # evt_001 and evt_003
        assert stats.duplicates_skipped == 1  # Duplicate evt_001
        assert stats.malformed_skipped == 2  # Malformed JSON + empty timestamp
        assert len(stats.errors) == 2
    
    def test_ingest_handles_duplicates(self, temp_db):
        """Test that duplicate events are skipped."""
        events = [
            {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", 
             "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"},
            {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", 
             "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"},
            {"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", 
             "package": "pkg2", "version": "1.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user2"},
        ]
        
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
            file_path = f.name
        
        try:
            ingester = EventIngester(temp_db)
            stats = ingester.ingest_file(file_path)
            
            assert stats.total_processed == 3
            assert stats.successfully_ingested == 2
            assert stats.duplicates_skipped == 1
        finally:
            os.unlink(file_path)
    
    def test_ingest_handles_out_of_order_events(self, temp_db):
        """Test that out-of-order events are stored correctly."""
        # Events in non-chronological order
        events = [
            {"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", 
             "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T12:00:00+00:00", "actor": "user1"},
            {"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", 
             "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"},
            {"event_id": "evt_003", "tenant_id": "tenant_a", "action": "delete", 
             "package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user1"},
        ]
        
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
            file_path = f.name
        
        try:
            ingester = EventIngester(temp_db)
            stats = ingester.ingest_file(file_path)
            
            assert stats.successfully_ingested == 3
            
            # Query should return events sorted by timestamp (newest first)
            from src.models import EventQuery
            query = EventQuery(tenant_id="tenant_a")
            results, _ = temp_db.query_events(query)
            
            assert len(results) == 3
            # Check ordering (newest first)
            assert results[0]["event_id"] == "evt_002"  # 12:00
            assert results[1]["event_id"] == "evt_003"  # 11:00
            assert results[2]["event_id"] == "evt_001"  # 10:00
        finally:
            os.unlink(file_path)
    
    def test_ingest_file_not_found(self, temp_db):
        """Test that FileNotFoundError is raised for missing files."""
        ingester = EventIngester(temp_db)
        
        with pytest.raises(FileNotFoundError):
            ingester.ingest_file("/nonexistent/path/events.jsonl")
    
    def test_ingest_empty_file(self, temp_db):
        """Test ingesting an empty file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            file_path = f.name
        
        try:
            ingester = EventIngester(temp_db)
            stats = ingester.ingest_file(file_path)
            
            assert stats.total_processed == 0
            assert stats.successfully_ingested == 0
        finally:
            os.unlink(file_path)
    
    def test_ingest_with_empty_lines(self, temp_db):
        """Test that empty lines in the file are handled."""
        events = [
            '{"event_id": "evt_001", "tenant_id": "tenant_a", "action": "download", '
            '"package": "pkg1", "version": "1.0", "timestamp": "2025-03-15T10:00:00+00:00", "actor": "user1"}',
            '',  # Empty line
            '{"event_id": "evt_002", "tenant_id": "tenant_a", "action": "upload", '
            '"package": "pkg2", "version": "1.0", "timestamp": "2025-03-15T11:00:00+00:00", "actor": "user2"}',
            '   ',  # Whitespace line
        ]
        
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=".jsonl", delete=False, encoding='utf-8'
        ) as f:
            for event in events:
                f.write(event + "\n")
            file_path = f.name
        
        try:
            ingester = EventIngester(temp_db)
            stats = ingester.ingest_file(file_path)
            
            # Empty lines should be counted but not cause errors
            assert stats.successfully_ingested == 2
        finally:
            os.unlink(file_path)
