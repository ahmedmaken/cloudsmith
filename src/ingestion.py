"""Event ingestion module for processing events.jsonl files."""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.config import config
from src.database import EventDatabase, get_database
from src.models import AuditEvent, IngestionStats

logger = logging.getLogger(__name__)


class EventIngester:
    """Handles ingestion of audit events from JSONL files."""
    
    def __init__(self, db: Optional[EventDatabase] = None):
        """Initialize the ingester with a database connection."""
        self.db = db or get_database()
    
    def ingest_file(self, file_path: str = None) -> IngestionStats:
        """
        Ingest events from a JSONL file.
        
        Handles:
        - Duplicate events (skipped based on tenant_id + event_id)
        - Malformed JSON entries (skipped with error logging)
        - Events arriving out of order (stored as-is, queries sort by timestamp)
        - Empty/invalid timestamps (skipped with error logging)
        
        Returns statistics about the ingestion process.
        """
        path = Path(file_path or config.events_file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Events file not found: {path}")
        
        stats = IngestionStats(
            total_processed=0,
            successfully_ingested=0,
            duplicates_skipped=0,
            malformed_skipped=0,
            errors=[]
        )
        
        logger.info(f"Starting ingestion from {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                stats.total_processed += 1
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    # Parse JSON
                    data = json.loads(line)
                    
                    # Validate and create event model
                    event = AuditEvent(**data)
                    
                    # Insert into database
                    if self.db.insert_event(event):
                        stats.successfully_ingested += 1
                    else:
                        stats.duplicates_skipped += 1
                        logger.debug(f"Line {line_num}: Duplicate event {event.event_id}")
                
                except json.JSONDecodeError as e:
                    stats.malformed_skipped += 1
                    error_msg = f"Line {line_num}: Invalid JSON - {str(e)}"
                    stats.errors.append(error_msg)
                    logger.warning(error_msg)
                
                except ValidationError as e:
                    stats.malformed_skipped += 1
                    error_msg = f"Line {line_num}: Validation error - {str(e)}"
                    stats.errors.append(error_msg)
                    logger.warning(error_msg)
                
                except Exception as e:
                    stats.malformed_skipped += 1
                    error_msg = f"Line {line_num}: Unexpected error - {str(e)}"
                    stats.errors.append(error_msg)
                    logger.error(error_msg)
        
        logger.info(
            f"Ingestion complete: {stats.successfully_ingested} ingested, "
            f"{stats.duplicates_skipped} duplicates, "
            f"{stats.malformed_skipped} malformed"
        )
        
        return stats


def ingest_events(file_path: str = None) -> IngestionStats:
    """
    Convenience function to ingest events from a file.
    
    Uses the global database instance.
    """
    ingester = EventIngester()
    return ingester.ingest_file(file_path)
