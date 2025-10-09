# Database Migration: SQLite to PostgreSQL

This document outlines the changes made when migrating the Flask Prolific application from SQLite to PostgreSQL (Supabase).

## Overview of Changes

The codebase has been updated to support both SQLite (for local development) and PostgreSQL (for production deployment). The system automatically determines which database to use based on environment variables.

## Key Changes

### 1. Database Connection Logic

```python
def create_connection(db_file="database.db"):
    """create a database connection to PostgreSQL (Supabase) or SQLite"""
    # Check for environment variables
    USER = os.getenv("DB_USER")
    PASSWORD = os.getenv("DB_PASSWORD")
    HOST = os.getenv("DB_HOST")
    PORT = os.getenv("DB_PORT")
    DBNAME = os.getenv("DB_NAME")
    
    if USER and PASSWORD and HOST and PORT and DBNAME:
        # Use PostgreSQL
        try:
            conn = psycopg2.connect(
                user=USER,
                password=PASSWORD,
                host=HOST,
                port=PORT,
                dbname=DBNAME
            )
            return conn
        except psycopg2.Error as e:
            # Fall back to SQLite
            print(f"PostgreSQL connection failed: {e}")
            return sqlite3.connect(db_file)
    else:
        # Use SQLite for local development
        return sqlite3.connect(db_file)
```

### 2. Database-Specific SQL Syntax

The codebase now dynamically uses the correct SQL syntax depending on the database type:

```python
# Example of parameterized query adaptation
placeholder = "%s" if hasattr(conn, "server_version") else "?"
cursor.execute(
    f"SELECT * FROM results WHERE id={placeholder}", (result_id,)
)
```

### 3. Schema Differences

Different data types are used in table creation:

```python
# PostgreSQL schema
create_tasks_table = """
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(255) PRIMARY KEY,
    task_number INTEGER,
    prolific_id VARCHAR(255),
    time_allocated TIMESTAMP,
    session_id VARCHAR(255),
    status VARCHAR(50) CHECK( status IN ('allocated', 'waiting', 'completed') )
);
"""

# vs. SQLite schema
create_tasks_table = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    task_number INTEGER,
    prolific_id TEXT,
    time_allocated TEXT,
    session_id TEXT,
    status TEXT CHECK( status IN ('allocated', 'waiting', 'completed') )
);
"""
```

### 4. Timestamp Handling

PostgreSQL and SQLite handle timestamps differently:

```python
if is_postgres:
    cursor.execute(
        f"INSERT INTO consent (...) VALUES (..., CURRENT_TIMESTAMP, ...)",
        (...)
    )
else:
    cursor.execute(
        f"INSERT INTO consent (...) VALUES (..., {placeholder}, ...)",
        (..., datetime.utcnow().isoformat(), ...)
    )
```

### 5. Transaction Safety Improvements

Improved the safety of database transactions:

```python
# Update with WHERE conditions to ensure atomicity
cursor.execute(
    f"""
    UPDATE tasks 
    SET status='allocated', 
        prolific_id={placeholder}, 
        time_allocated={placeholder}, 
        session_id={placeholder} 
    WHERE id={placeholder} 
    AND status='waiting' 
    AND prolific_id IS NULL
    """,
    (prolific_id, datetime.utcnow(), session_id, task_id),
)

# Verify the update succeeded (prevents race conditions)
if cursor.rowcount > 0:
    conn.commit()
    return task_id, task_number
```

### 6. Connection Retry Logic

Added retry logic for more robust PostgreSQL connections:

```python
for attempt in range(3):
    try:
        conn = psycopg2.connect(...)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return conn
    except psycopg2.Error as e:
        print(f"PostgreSQL connection attempt {attempt + 1} failed: {e}")
        if attempt < 2:
            time.sleep(2)
```

### 7. Environment Configuration

Added support for .env file to configure database connections:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Additional Improvements

Beyond the SQLite-to-PostgreSQL migration, we made these enhancements:

1. **Better Error Handling**: More comprehensive error handling throughout database operations
2. **Race Condition Prevention**: Added WHERE clauses and rowcount checks to prevent race conditions
3. **Connection Pooling**: Proper connection handling with context managers
4. **Consistent Timestamps**: Standardized on UTC timestamps across the application
5. **Type Checking**: Added more robust type checking for database values

## How to Configure

### Local Development (SQLite)

No special configuration needed - will automatically use database.db file.

### Production Deployment (PostgreSQL/Supabase)

Create a .env file with:

```
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=your_host.supabase.co
DB_PORT=5432
DB_NAME=postgres
```

The application will automatically detect these settings and use PostgreSQL.

## Testing Changes

We thoroughly tested both database options to ensure backward compatibility with SQLite while enabling PostgreSQL for production scaling.
