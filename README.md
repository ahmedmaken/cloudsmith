# Artifact Access Audit Service

A Python service that ingests artifact access events, stores them with proper tenant isolation, and exposes a query API.

## Overview

This service processes audit events from a JSONL file, stores them in a DuckDB database with tenant isolation, and provides a REST API for querying events with various filters.

### Features

- **Event Ingestion**: Reads events from JSONL files, handling duplicates and malformed entries
- **Tenant Isolation**: Events are partitioned by tenant; one tenant cannot see another's data
- **Query API**: Filter events by tenant (required), time range, action type, and package name
- **Retention Policy**: Configurable cleanup of old events
- **Persistent Storage**: DuckDB database for efficient storage and querying

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd cloudsmith

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Service

```bash
# Start the API server
python -m src.main serve

# Or with custom host/port
python -m src.main serve --host 127.0.0.1 --port 8080
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Ingesting Events

```bash
# Ingest from default events.jsonl
python -m src.main ingest

# Ingest from custom file
python -m src.main ingest --file /path/to/events.jsonl
```

Or via API:
```bash
curl -X POST "http://localhost:8000/ingest"
```

### Querying Events

```bash
# Query all events for a tenant
curl "http://localhost:8000/events?tenant_id=acme_corp"

# Filter by action type
curl "http://localhost:8000/events?tenant_id=acme_corp&action=download"

# Filter by package
curl "http://localhost:8000/events?tenant_id=acme_corp&package=numpy"

# Filter by time range
curl "http://localhost:8000/events?tenant_id=acme_corp&start_time=2025-03-14T00:00:00Z&end_time=2025-03-15T00:00:00Z"

# With pagination
curl "http://localhost:8000/events?tenant_id=acme_corp&limit=50&offset=0"
```

### Applying Retention Policy

```bash
# Via CLI (default 90 days)
python -m src.main retention

# With custom retention period
python -m src.main retention --days 30

# Via API
curl -X POST "http://localhost:8000/retention/apply?retention_days=30"
```

## Docker

### Build and Run

```bash
# Build the image
docker build -t audit-service .

# Run the container
docker run -p 8000:8000 -v $(pwd)/events.jsonl:/app/events.jsonl audit-service

# Run with custom configuration
docker run -p 8000:8000 \
  -e RETENTION_DAYS=30 \
  -e DATABASE_PATH=/data/audit.duckdb \
  -v $(pwd)/data:/data \
  -v $(pwd)/events.jsonl:/app/events.jsonl \
  audit-service
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ingest` | POST | Ingest events from file |
| `/events` | GET | Query events with filters |
| `/tenants` | GET | List all tenant IDs |
| `/retention/config` | GET | Get retention configuration |
| `/retention/apply` | POST | Apply retention policy |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `audit_events.duckdb` | Path to DuckDB database file |
| `RETENTION_DAYS` | `90` | Days to retain events |
| `EVENTS_FILE_PATH` | `events.jsonl` | Default events file path |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_database.py -v
```

## Approach and Key Decisions

### Database Choice: DuckDB

I chose DuckDB for several reasons:
- **Embedded**: No external database server required, simplifying deployment
- **SQL Support**: Full SQL capabilities for complex queries
- **Performance**: Column-oriented storage is efficient for analytical queries
- **Simplicity**: Single file database, easy to manage

### Tenant Isolation

Tenant isolation is enforced at multiple levels:
1. **Primary Key**: `(tenant_id, event_id)` ensures events are unique per tenant
2. **Query Enforcement**: `tenant_id` is a required parameter for all queries
3. **No Cross-Tenant Access**: The API design makes it impossible to query across tenants

### Duplicate Handling

Duplicates are detected using the combination of `tenant_id` and `event_id`. If an event with the same key exists, the duplicate is silently skipped. This allows the same event file to be ingested multiple times without issues.

### Malformed Entry Handling

Malformed entries (invalid JSON or missing required fields) are logged and counted but don't stop the ingestion process. The ingestion returns detailed statistics about what was processed.

### Out-of-Order Events

Events are stored as they arrive, regardless of chronological order. Queries sort by timestamp descending (newest first), so the display order is always correct.

## Trade-offs and Shortcuts

1. **In-Process Database**: Using DuckDB means the database is tied to the application process. For production, a separate database server (PostgreSQL, etc.) would be more appropriate for horizontal scaling.

2. **Single File Ingestion**: The current implementation reads the entire file. For very large files, streaming or chunked processing would be better.

3. **No Authentication**: The API doesn't implement authentication. In production, you'd add API keys or OAuth.

4. **Simple Retention**: Retention is applied on-demand rather than scheduled. A production system would use a background job.

5. **Limited Query Operators**: Package filtering uses exact match only. Wildcards or partial matching would be useful additions.

## What I Would Do With More Time

1. **Authentication & Authorization**: Add JWT-based auth with tenant-specific API keys
2. **Background Jobs**: Scheduled retention policy execution using Celery or APScheduler
3. **Streaming Ingestion**: Support for real-time event streaming (Kafka, webhooks)
4. **Enhanced Querying**: Full-text search, wildcard matching, aggregations
5. **Monitoring**: Prometheus metrics, structured logging with correlation IDs
6. **Database Migrations**: Proper schema versioning with Alembic or similar
7. **Rate Limiting**: Prevent API abuse
8. **Caching**: Redis cache for frequently accessed queries
9. **Async Processing**: Async database operations for better concurrency
10. **Data Export**: Endpoints to export filtered events as CSV/JSON

## Project Structure

```
cloudsmith/
├── src/
│   ├── __init__.py
│   ├── api.py          # FastAPI application and endpoints
│   ├── config.py       # Configuration settings
│   ├── database.py     # DuckDB database layer
│   ├── ingestion.py    # Event ingestion logic
│   ├── main.py         # CLI entry point
│   └── models.py       # Pydantic data models
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Test fixtures
│   ├── test_api.py     # API endpoint tests
│   ├── test_database.py # Database layer tests
│   ├── test_ingestion.py # Ingestion tests
│   └── test_models.py  # Model validation tests
├── events.jsonl        # Sample event data
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
└── README.md          # This file
```
