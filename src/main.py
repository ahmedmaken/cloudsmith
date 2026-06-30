"""Main entry point for the Artifact Access Audit Service."""

import argparse
import logging
import sys

import uvicorn

from src.api import app
from src.config import config
from src.database import get_database
from src.ingestion import ingest_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_server():
    """Run the FastAPI server."""
    logger.info(f"Starting server on {config.api_host}:{config.api_port}")
    uvicorn.run(
        "src.api:app",
        host=config.api_host,
        port=config.api_port,
        reload=False
    )


def run_ingestion(file_path: str = None):
    """Run the ingestion process."""
    logger.info("Running ingestion process")
    try:
        stats = ingest_events(file_path)
        logger.info(f"Ingestion complete: {stats}")
        return stats
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)


def run_retention(days: int = None):
    """Apply retention policy."""
    logger.info("Applying retention policy")
    db = get_database()
    deleted = db.apply_retention_policy(days)
    logger.info(f"Deleted {deleted} old events")
    return deleted


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Artifact Access Audit Service"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the API server")
    server_parser.add_argument(
        "--host", default=config.api_host, help="Host to bind to"
    )
    server_parser.add_argument(
        "--port", type=int, default=config.api_port, help="Port to bind to"
    )
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest events from file")
    ingest_parser.add_argument(
        "--file", "-f", default=config.events_file_path,
        help="Path to events.jsonl file"
    )
    
    # Retention command
    retention_parser = subparsers.add_parser(
        "retention", help="Apply retention policy"
    )
    retention_parser.add_argument(
        "--days", "-d", type=int, default=config.retention_days,
        help="Number of days to retain events"
    )
    
    args = parser.parse_args()
    
    if args.command == "serve":
        config.api_host = args.host
        config.api_port = args.port
        run_server()
    elif args.command == "ingest":
        run_ingestion(args.file)
    elif args.command == "retention":
        run_retention(args.days)
    else:
        # Default: run server
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
