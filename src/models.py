"""Data models for the Audit Service."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Supported action types for audit events."""
    DOWNLOAD = "download"
    UPLOAD = "upload"
    DELETE = "delete"


class AuditEvent(BaseModel):
    """Represents an artifact access audit event."""
    
    event_id: str = Field(..., description="Unique identifier for the event")
    tenant_id: str = Field(..., description="Tenant identifier")
    action: ActionType = Field(..., description="Type of action performed")
    package: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    timestamp: datetime = Field(..., description="When the event occurred")
    actor: str = Field(..., description="Who performed the action")
    
    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value):
        """Parse and validate timestamp."""
        if isinstance(value, datetime):
            return value
        if not value or value == "":
            raise ValueError("Timestamp cannot be empty")
        return value
    
    model_config = {"use_enum_values": True}


class EventQuery(BaseModel):
    """Query parameters for filtering events."""
    
    tenant_id: str = Field(..., description="Tenant ID (required)")
    start_time: Optional[datetime] = Field(None, description="Start of time range")
    end_time: Optional[datetime] = Field(None, description="End of time range")
    action: Optional[ActionType] = Field(None, description="Filter by action type")
    package: Optional[str] = Field(None, description="Filter by package name")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class EventResponse(BaseModel):
    """Response model for event queries."""
    
    events: list[dict]
    total: int
    limit: int
    offset: int


class IngestionStats(BaseModel):
    """Statistics from the ingestion process."""
    
    total_processed: int
    successfully_ingested: int
    duplicates_skipped: int
    malformed_skipped: int
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    database: str
    events_count: int
