"""Main entry point for the Artifact Access Audit Service."""

import sys
import uvicorn

from src.api import app
from src.database import get_connection, apply_retention
from src.ingestion import ingest_events


def run_server(host="0.0.0.0", port=8000):
    """Run the FastAPI server."""
    print(f"Starting server on {host}:{port}")
    uvicorn.run("src.api:app", host=host, port=port, reload=False)


def run_ingestion(file_path="events.jsonl"):
    """Ingest events from file."""
    print(f"Ingesting from {file_path}...")
    stats = ingest_events(file_path)
    print(f"Done: {stats['ingested']} ingested, {stats['duplicates']} duplicates, {stats['malformed']} malformed")
    return stats


def run_retention(days=90):
    """Apply retention policy."""
    print(f"Applying retention policy ({days} days)...")
    conn = get_connection()
    deleted = apply_retention(conn, days)
    print(f"Deleted {deleted} old events")
    return deleted


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <command>")
        print("Commands: serve, ingest, retention")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "serve":
        run_server()
    elif cmd == "ingest":
        file_path = sys.argv[2] if len(sys.argv) > 2 else "events.jsonl"
        run_ingestion(file_path)
    elif cmd == "retention":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        run_retention(days)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
