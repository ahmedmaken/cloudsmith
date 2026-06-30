"""FastAPI application for the Artifact Access Audit Service."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from src.config import config
from src.database import get_database, reset_database
from src.ingestion import ingest_events
from src.models import (
    ActionType,
    EventQuery,
    EventResponse,
    HealthResponse,
    IngestionStats,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: Initialize database
    logger.info("Starting Artifact Access Audit Service")
    db = get_database()
    logger.info(f"Database initialized: {config.database_path}")
    
    yield
    
    # Shutdown: Close database
    logger.info("Shutting down service")
    reset_database()


app = FastAPI(
    title="Artifact Access Audit Service",
    description="API for ingesting and querying artifact access audit events",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check the health status of the service."""
    try:
        db = get_database()
        count = db.get_event_count()
        return HealthResponse(
            status="healthy",
            database="connected",
            events_count=count
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.post("/ingest", response_model=IngestionStats, tags=["Ingestion"])
async def ingest_events_endpoint(file_path: Optional[str] = None):
    """
    Ingest events from a JSONL file.
    
    If no file path is provided, uses the default events.jsonl file.
    Handles duplicates by skipping them (based on tenant_id + event_id).
    Malformed entries are skipped and reported in the response.
    """
    try:
        stats = ingest_events(file_path or config.events_file_path)
        return stats
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/events", response_model=EventResponse, tags=["Events"])
async def query_events(
    tenant_id: str = Query(..., description="Tenant ID (required for tenant isolation)"),
    start_time: Optional[datetime] = Query(None, description="Start of time range (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End of time range (ISO 8601)"),
    action: Optional[ActionType] = Query(None, description="Filter by action type"),
    package: Optional[str] = Query(None, description="Filter by package name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Query audit events with filtering and pagination.
    
    **Tenant isolation**: The tenant_id is required and ensures that
    only events belonging to the specified tenant are returned.
    
    **Filters**:
    - `tenant_id`: Required - isolates query to a specific tenant
    - `start_time`: Filter events after this timestamp
    - `end_time`: Filter events before this timestamp
    - `action`: Filter by action type (download, upload, delete)
    - `package`: Filter by exact package name
    
    **Pagination**:
    - `limit`: Maximum number of results (default 100, max 1000)
    - `offset`: Number of results to skip
    
    Results are sorted by timestamp in descending order (newest first).
    """
    try:
        db = get_database()
        query = EventQuery(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            action=action,
            package=package,
            limit=limit,
            offset=offset
        )
        
        events, total = db.query_events(query)
        
        return EventResponse(
            events=events,
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/tenants", response_model=list[str], tags=["Events"])
async def list_tenants():
    """
    List all tenant IDs that have events in the system.
    
    This is a utility endpoint for discovering available tenants.
    """
    try:
        db = get_database()
        return db.get_tenants()
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retention/apply", tags=["Retention"])
async def apply_retention(
    retention_days: Optional[int] = Query(
        None, 
        ge=1, 
        description="Number of days to retain events (defaults to configured value)"
    )
):
    """
    Apply the retention policy to delete old events.
    
    Events older than the specified number of days will be deleted.
    If not specified, uses the configured retention period.
    """
    try:
        db = get_database()
        days = retention_days or config.retention_days
        deleted_count = db.apply_retention_policy(days)
        return {
            "deleted_count": deleted_count,
            "retention_days": days,
            "message": f"Deleted {deleted_count} events older than {days} days"
        }
    except Exception as e:
        logger.error(f"Retention policy application failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/retention/config", tags=["Retention"])
async def get_retention_config():
    """Get the current retention policy configuration."""
    return {
        "retention_days": config.retention_days,
        "description": f"Events older than {config.retention_days} days will be deleted when retention is applied"
    }


def create_app() -> FastAPI:
    """Factory function for creating the FastAPI application."""
    return app
