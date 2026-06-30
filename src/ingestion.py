"""Simple event ingestion from JSONL files."""

import json
from datetime import datetime

from src.database import get_connection, insert_event

VALID_ACTIONS = {"download", "upload", "delete"}
REQUIRED_FIELDS = {"event_id", "tenant_id", "action", "package", "version", "timestamp", "actor"}


def validate_event(data):
    """
    Validate event data. Returns (is_valid, error_message).
    """
    # Check data is a dict
    if not isinstance(data, dict):
        return False, "Event must be a JSON object"
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            return False, f"Missing field: {field}"
    
    # Check action type
    if data["action"] not in VALID_ACTIONS:
        return False, f"Invalid action: {data['action']}"
    
    # Check timestamp is not empty
    if not data["timestamp"]:
        return False, "Empty timestamp"
    
    # Try to parse timestamp
    try:
        if isinstance(data["timestamp"], str):
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except ValueError as e:
        return False, f"Invalid timestamp: {e}"
    
    return True, None


def ingest_events(file_path="events.jsonl"):
    """
    Ingest events from a JSONL file.
    
    Returns a dict with stats: {
        "total": int,
        "ingested": int,
        "duplicates": int,
        "malformed": int,
        "errors": list
    }
    """
    conn = get_connection()
    
    stats = {
        "total": 0,
        "ingested": 0,
        "duplicates": 0,
        "malformed": 0,
        "errors": []
    }
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stats["total"] += 1
            line = line.strip()
            
            if not line:
                continue
            
            # Parse JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                stats["malformed"] += 1
                stats["errors"].append(f"Line {line_num}: Invalid JSON - {e}")
                continue
            
            # Validate event
            is_valid, error = validate_event(data)
            if not is_valid:
                stats["malformed"] += 1
                stats["errors"].append(f"Line {line_num}: {error}")
                continue
            
            # Insert event
            if insert_event(conn, data):
                stats["ingested"] += 1
            else:
                stats["duplicates"] += 1
    
    return stats
