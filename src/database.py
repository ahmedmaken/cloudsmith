"""Database layer using DuckDB for tenant-isolated event storage."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import duckdb

from src.config import config
from src.models import AuditEvent, EventQuery

logger = logging.getLogger(__name__)


class EventDatabase:
    """DuckDB-based storage for audit events with tenant isolation."""
    
    def __init__(self, db_path: str = None):
        """Initialize the database connection."""
        self.db_path = db_path or config.database_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
    
    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
            self._init_schema()
        return self._conn
    
    def _init_schema(self):
        """Initialize the database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id VARCHAR NOT NULL,
                tenant_id VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                package VARCHAR NOT NULL,
                version VARCHAR NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                actor VARCHAR NOT NULL,
                ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, event_id)
            )
        """)
        
        # Create indexes for efficient querying
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_timestamp 
            ON audit_events (tenant_id, timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_action 
            ON audit_events (tenant_id, action)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_package 
            ON audit_events (tenant_id, package)
        """)
    
    def insert_event(self, event: AuditEvent) -> bool:
        """
        Insert an event into the database.
        
        Returns True if inserted, False if duplicate.
        Uses tenant_id + event_id as the primary key for tenant isolation.
        """
        try:
            # Check if event already exists
            exists = self.conn.execute("""
                SELECT 1 FROM audit_events 
                WHERE tenant_id = ? AND event_id = ?
            """, [event.tenant_id, event.event_id]).fetchone()
            
            if exists:
                return False  # Duplicate
            
            # Insert the new event
            self.conn.execute("""
                INSERT INTO audit_events (
                    event_id, tenant_id, action, package, version, timestamp, actor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                event.event_id,
                event.tenant_id,
                event.action,
                event.package,
                event.version,
                event.timestamp,
                event.actor
            ])
            return True
        except duckdb.ConstraintException:
            # Duplicate event (race condition)
            return False
    
    def query_events(self, query: EventQuery) -> tuple[list[dict], int]:
        """
        Query events with tenant isolation and filtering.
        
        Always requires tenant_id for proper isolation.
        Returns (events, total_count).
        """
        # Build WHERE clause with tenant isolation as mandatory first filter
        conditions = ["tenant_id = ?"]
        params = [query.tenant_id]
        
        if query.start_time:
            conditions.append("timestamp >= ?")
            params.append(query.start_time)
        
        if query.end_time:
            conditions.append("timestamp <= ?")
            params.append(query.end_time)
        
        if query.action:
            conditions.append("action = ?")
            params.append(query.action.value if hasattr(query.action, 'value') else query.action)
        
        if query.package:
            conditions.append("package = ?")
            params.append(query.package)
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM audit_events WHERE {where_clause}"
        total = self.conn.execute(count_query, params).fetchone()[0]
        
        # Get paginated results
        data_query = f"""
            SELECT event_id, tenant_id, action, package, version, 
                   timestamp, actor
            FROM audit_events 
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([query.limit, query.offset])
        
        result = self.conn.execute(data_query, params).fetchall()
        
        events = [
            {
                "event_id": row[0],
                "tenant_id": row[1],
                "action": row[2],
                "package": row[3],
                "version": row[4],
                "timestamp": row[5].isoformat() if row[5] else None,
                "actor": row[6]
            }
            for row in result
        ]
        
        return events, total
    
    def apply_retention_policy(self, retention_days: int = None) -> int:
        """
        Delete events older than the retention period.
        
        Returns the number of deleted events.
        """
        days = retention_days or config.retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Count events to be deleted
        count = self.conn.execute("""
            SELECT COUNT(*) FROM audit_events WHERE timestamp < ?
        """, [cutoff_date]).fetchone()[0]
        
        # Delete old events
        self.conn.execute("""
            DELETE FROM audit_events WHERE timestamp < ?
        """, [cutoff_date])
        
        logger.info(f"Retention policy applied: {count} events deleted older than {days} days")
        return count
    
    def get_event_count(self) -> int:
        """Get total number of events in the database."""
        return self.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    
    def get_tenants(self) -> list[str]:
        """Get list of all tenant IDs."""
        result = self.conn.execute("""
            SELECT DISTINCT tenant_id FROM audit_events ORDER BY tenant_id
        """).fetchall()
        return [row[0] for row in result]
    
    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global database instance
_db: Optional[EventDatabase] = None


def get_database() -> EventDatabase:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        _db = EventDatabase()
    return _db


def reset_database():
    """Reset the global database instance (for testing)."""
    global _db
    if _db:
        _db.close()
    _db = None
