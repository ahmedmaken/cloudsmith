"""Simple FastAPI app for querying audit events."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from src.database import get_connection, query_events, get_event_count, apply_retention, reset_connection
from src.ingestion import ingest_events

app = FastAPI(title="Artifact Access Audit Service")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        conn = get_connection()
        count = get_event_count(conn)
        return {"status": "healthy", "events_count": count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/ingest")
def ingest_endpoint(file_path: Optional[str] = None):
    """Ingest events from a JSONL file."""
    try:
        path = file_path or "events.jsonl"
        stats = ingest_events(path)
        return stats
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events")
def get_events(
    tenant_id: str = Query(..., description="Tenant ID (required)"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    action: Optional[str] = Query(None, description="Action type: download, upload, delete"),
    package: Optional[str] = Query(None, description="Package name"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Query events for a tenant with optional filters."""
    # Validate action if provided
    if action and action not in {"download", "upload", "delete"}:
        raise HTTPException(status_code=400, detail="Invalid action type")
    
    conn = get_connection()
    events, total = query_events(
        conn,
        tenant_id=tenant_id,
        start_time=start_time,
        end_time=end_time,
        action=action,
        package=package,
        limit=limit,
        offset=offset
    )
    
    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.post("/retention/apply")
def apply_retention_endpoint(retention_days: int = Query(90, ge=1)):
    """Apply retention policy - delete events older than specified days."""
    conn = get_connection()
    deleted = apply_retention(conn, retention_days)
    return {"deleted_count": deleted, "retention_days": retention_days}
