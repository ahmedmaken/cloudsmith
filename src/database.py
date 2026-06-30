"""Simple database layer using DuckDB for tenant-isolated event storage."""

import os
from datetime import datetime, timedelta, timezone

import duckdb

# Global connection
_conn = None
DB_PATH = os.getenv("DATABASE_PATH", "audit_events.duckdb")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))


def get_connection(db_path=None):
    """Get or create database connection."""
    global _conn
    if _conn is None:
        _conn = duckdb.connect(db_path or DB_PATH)
        init_schema(_conn)
    return _conn


def close_connection():
    """Close the database connection."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def reset_connection():
    """Reset connection (for testing)."""
    close_connection()


def init_schema(conn):
    """Create the events table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id VARCHAR NOT NULL,
            tenant_id VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            package VARCHAR NOT NULL,
            version VARCHAR NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            actor VARCHAR NOT NULL,
            PRIMARY KEY (tenant_id, event_id)
        )
    """)


def insert_event(conn, event):
    """
    Insert an event dict into the database.
    Returns True if inserted, False if duplicate.
    """
    try:
        exists = conn.execute(
            "SELECT 1 FROM audit_events WHERE tenant_id = ? AND event_id = ?",
            [event["tenant_id"], event["event_id"]]
        ).fetchone()
        
        if exists:
            return False
        
        conn.execute("""
            INSERT INTO audit_events (event_id, tenant_id, action, package, version, timestamp, actor)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            event["event_id"],
            event["tenant_id"],
            event["action"],
            event["package"],
            event["version"],
            event["timestamp"],
            event["actor"]
        ])
        return True
    except duckdb.ConstraintException:
        return False


def query_events(conn, tenant_id, start_time=None, end_time=None, action=None, package=None, limit=100, offset=0):
    """
    Query events with tenant isolation and filtering.
    Returns (events_list, total_count).
    """
    conditions = ["tenant_id = ?"]
    params = [tenant_id]
    
    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)
    
    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)
    
    if action:
        conditions.append("action = ?")
        params.append(action)
    
    if package:
        conditions.append("package = ?")
        params.append(package)
    
    where_clause = " AND ".join(conditions)
    
    # Get total count
    total = conn.execute(
        f"SELECT COUNT(*) FROM audit_events WHERE {where_clause}",
        params
    ).fetchone()[0]
    
    # Get paginated results
    query = f"""
        SELECT event_id, tenant_id, action, package, version, timestamp, actor
        FROM audit_events 
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    
    rows = conn.execute(query, params).fetchall()
    
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
        for row in rows
    ]
    
    return events, total


def apply_retention(conn, retention_days=None):
    """Delete events older than retention period. Returns count of deleted events."""
    days = retention_days or RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    count = conn.execute(
        "SELECT COUNT(*) FROM audit_events WHERE timestamp < ?",
        [cutoff]
    ).fetchone()[0]
    
    conn.execute("DELETE FROM audit_events WHERE timestamp < ?", [cutoff])
    
    return count


def get_event_count(conn):
    """Get total number of events."""
    return conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]

