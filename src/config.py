"""Configuration settings for the Audit Service."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""
    
    # Database settings
    database_path: str = os.getenv("DATABASE_PATH", "audit_events.duckdb")
    
    # Retention policy (in days)
    retention_days: int = int(os.getenv("RETENTION_DAYS", "90"))
    
    # Event file path
    events_file_path: str = os.getenv("EVENTS_FILE_PATH", "events.jsonl")
    
    # API settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))


config = Config()
