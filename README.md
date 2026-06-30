# Artifact Access Audit Service

A simple Python service for ingesting artifact access events, storing them with tenant isolation, and querying via REST API.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Service

### Start the API server
```bash
python -m src.main serve
```

Server runs at http://localhost:8000

### Ingest events from file
```bash
python -m src.main ingest events.jsonl
```

### Apply retention policy
```bash
python -m src.main retention 90
```

## API Usage

### Health check
```bash
curl http://localhost:8000/health
```

### Ingest events
```bash
curl -X POST "http://localhost:8000/ingest"
```

### Query events (tenant_id is required)
```bash
# Get all events for a tenant
curl "http://localhost:8000/events?tenant_id=acme_corp"

# Filter by action
curl "http://localhost:8000/events?tenant_id=acme_corp&action=download"

# Filter by package
curl "http://localhost:8000/events?tenant_id=acme_corp&package=numpy"

# Filter by time range
curl "http://localhost:8000/events?tenant_id=acme_corp&start_time=2025-03-14T00:00:00Z&end_time=2025-03-15T00:00:00Z"
```

### Apply retention
```bash
curl -X POST "http://localhost:8000/retention/apply?retention_days=30"
```

## Querying DuckDB Directly

> Stop the server first (`Ctrl+C`) — DuckDB only allows one process at a time.

```bash
# Open interactive DuckDB shell
duckdb audit_events.duckdb

# Useful queries
SELECT * FROM audit_events LIMIT 10;
SELECT tenant_id, COUNT(*) as total FROM audit_events GROUP BY tenant_id;
SELECT * FROM audit_events WHERE tenant_id = 'acme_corp';
SELECT * FROM audit_events WHERE action = 'download' ORDER BY timestamp DESC;
.quit
```

Or via Python:
```bash
python -c "import duckdb; print(duckdb.connect('audit_events.duckdb').execute('SELECT tenant_id, COUNT(*) FROM audit_events GROUP BY tenant_id').df())"
```

Install DuckDB CLI if needed: `brew install duckdb`

## Running Tests

```bash
pytest tests/ -v
```

## Approach & Key Decisions

- **DuckDB**: Used for simple embedded database - no server setup needed, great for analytics queries
- **Simple functions**: No complex class hierarchies - just straightforward functions
- **Tenant isolation**: Composite primary key (tenant_id, event_id) ensures tenant data separation
- **Validation**: Simple validation function checks required fields and valid action types
- **Duplicates**: Handled by checking existence before insert (composite key)
- **Out-of-order events**: Stored as-is, queries sort by timestamp

## Trade-offs / Shortcuts

- No authentication/authorization (would add JWT or API keys in production)
- In-memory database connection (would use proper connection pooling)
- Simple error handling (would add structured logging)
- No indexes beyond primary key (would add for production query patterns)
- Single-file database (would use proper DB service in production)

## What I'd Do With More Time

- Add authentication middleware
- Add structured logging
- Add database connection pooling
- Add more comprehensive test coverage
- Add proper configuration management
- Add metrics/monitoring endpoints
- Add scheduled retention via background job
- Add rate limiting
