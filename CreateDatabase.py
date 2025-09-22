# # This is a python script that will create the required database tasks table.
# # DO NOT RUN THIS SCRIPT IF THE DATABASE ALREADY EXISTS. IT WILL DELETE THE EXISTING DATABASE AND CREATE A NEW ONE.

# COMPLETIONS_PER_TASK = 10  # Number of times each task should be completed by different participants
# NUMBER_OF_TASKS = 60  # Number of tasks to create in the database

# import sqlite3
# from uuid import uuid4



# # Creates the DB file if it doesn't exist, and creates the tables if they don't exist.
# def initDatabase():
#     # Connect to SQLite database (or create it if it doesn't exist)
#     conn = sqlite3.connect('database.db')
#     # Create a cursor object using the cursor() method
#     cursor = conn.cursor()
#     # Define the schema for the 'tasks' table
#     create_tasks_table = '''
# CREATE TABLE IF NOT EXISTS tasks (
#     id TEXT PRIMARY KEY,
#     task_number INTEGER,
#     prolific_id TEXT,
#     time_allocated TEXT,
#     session_id TEXT,
#     status TEXT CHECK( status IN ('allocated', 'waiting', 'completed') )
# );
# '''

#     # Define the schema for the 'results' table
#     create_results_table = '''
# CREATE TABLE IF NOT EXISTS results (
#     id TEXT PRIMARY KEY,
#     json_string TEXT,
#     prolific_id TEXT
# );
# '''
#     # Execute the SQL commands to create tables
#     cursor.execute(create_tasks_table)
#     cursor.execute(create_results_table)
#     # Commit the changes and close the connection
#     conn.commit()
#     conn.close()

# def initTasks(num_tasks, db_file='database.db'):
#     """
#     Initializes a specified number of tasks in the 'tasks' table with default values.
#     Each task will have multiple entries (as defined by COMPLETIONS_PER_TASK) with unique IDs but the same task number.

#     :param num_tasks: The number of tasks to initialize.
#     :param db_file: The SQLite database file.
#     """
#     # Connect to the SQLite database
#     conn = sqlite3.connect(db_file)
#     cursor = conn.cursor()

#     # Default status for new tasks
#     default_status = 'waiting'

#     # Prepare the SQL query for inserting a new task
#     insert_task_query = '''
#     INSERT INTO tasks (id, task_number, prolific_id, time_allocated, session_id, status)
#     VALUES (?, ?, NULL, NULL, NULL, ?);
#     '''

#     # Insert the specified number of tasks, repeated according to COMPLETIONS_PER_TASK
#     for task_number in range(1, num_tasks + 1):
#         for _ in range(COMPLETIONS_PER_TASK):
#             # Generate a unique ID for the task
#             task_id = str(uuid4())
#             # Execute the SQL query
#             cursor.execute(insert_task_query, (task_id, task_number, default_status))

#     # Commit the changes and close the connection
#     conn.commit()
#     conn.close()



# # --------------------------------------------------

# initDatabase()
# initTasks(NUMBER_OF_TASKS)

# This is a python script that will create the required database tasks table.
# DO NOT RUN THIS SCRIPT IF THE DATABASE ALREADY EXISTS. IT WILL DELETE THE EXISTING DATABASE AND CREATE A NEW ONE.

# /// script
# dependencies = [
#   "apscheduler",
#   "sqlalchemy",
#   "psycopg2-binary",
#   "uuid",
#   "python-dotenv",
# ]
# ///

COMPLETIONS_PER_TASK = (
    10  # Number of times each task should be completed by different participants
)
NUMBER_OF_TASKS = 60  # Number of tasks to create in the database

import sqlite3
import psycopg2
import os
import time
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()


def create_connection(db_file="database.db"):
    """create a database connection to PostgreSQL (Supabase) or SQLite"""
    # Fixed connection parameters
    USER = os.getenv("DB_USER")
    PASSWORD = os.getenv("DB_PASSWORD")
    HOST = os.getenv("DB_HOST")
    PORT = os.getenv("DB_PORT")
    DBNAME = os.getenv("DB_NAME")

    if USER and PASSWORD and HOST and PORT and DBNAME:
        # Use Supabase PostgreSQL with retry logic
        for attempt in range(3):
            try:
                conn = psycopg2.connect(
                    user=USER,
                    password=PASSWORD,
                    host=HOST,
                    port=PORT,
                    dbname=DBNAME,
                    connect_timeout=10,
                )
                # Test the connection
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                print(f"PostgreSQL connected successfully on attempt {attempt + 1}")
                return conn
            except psycopg2.Error as e:
                print(f"PostgreSQL connection attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)

        print("All PostgreSQL connection attempts failed, falling back to SQLite")
        return sqlite3.connect(db_file)
    else:
        # Use SQLite for local development
        return sqlite3.connect(db_file)


# Creates the DB file if it doesn't exist, and creates the tables if they don't exist.
def initDatabase():
    conn = create_connection()
    cursor = conn.cursor()
    is_postgres = hasattr(conn, "server_version")

    if is_postgres:
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
        create_results_table = """
CREATE TABLE IF NOT EXISTS results (
    id VARCHAR(255) PRIMARY KEY,
    json_string TEXT,
    prolific_id VARCHAR(255)
);
"""
        # Add consent table for PostgreSQL
        create_consent_table = """
CREATE TABLE IF NOT EXISTS consent (
    id VARCHAR(255) PRIMARY KEY,
    prolific_id VARCHAR(255),
    session_id VARCHAR(255),
    consent_given BOOLEAN,
    consent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);
"""
        print("Creating PostgreSQL tables...")
    else:
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
        create_results_table = """
CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    json_string TEXT,
    prolific_id TEXT
);
"""
        # Add consent table for SQLite
        create_consent_table = """
CREATE TABLE IF NOT EXISTS consent (
    id TEXT PRIMARY KEY,
    prolific_id TEXT,
    session_id TEXT,
    consent_given BOOLEAN,
    consent_timestamp TEXT,
    ip_address TEXT
);
"""
        print("Creating SQLite tables...")

    cursor.execute(create_tasks_table)
    cursor.execute(create_results_table)
    cursor.execute(create_consent_table)

    conn.commit()
    conn.close()
    print("Database tables created successfully!")


def initTasks(num_tasks):
    """
    Initializes a specified number of tasks in the 'tasks' table with default values.
    Each task will have multiple entries (as defined by COMPLETIONS_PER_TASK) with unique IDs but the same task number.

    :param num_tasks: The number of tasks to initialize.
    """
    # Connect to the database
    conn = create_connection()
    cursor = conn.cursor()

    # Check if we're using PostgreSQL or SQLite
    is_postgres = hasattr(conn, "server_version")
    placeholder = "%s" if is_postgres else "?"

    # Default status for new tasks
    default_status = "waiting"

    # Prepare the SQL query for inserting a new task
    insert_task_query = f"""
    INSERT INTO tasks (id, task_number, prolific_id, time_allocated, session_id, status)
    VALUES ({placeholder}, {placeholder}, NULL, NULL, NULL, {placeholder});
    """

    print(f"Initializing {num_tasks * COMPLETIONS_PER_TASK} task entries...")

    # Insert the specified number of tasks, repeated according to COMPLETIONS_PER_TASK
    for task_number in range(1, num_tasks + 1):
        for _ in range(COMPLETIONS_PER_TASK):
            # Generate a unique ID for the task
            task_id = str(uuid4())
            # Execute the SQL query
            cursor.execute(insert_task_query, (task_id, task_number, default_status))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print(f"Successfully created {num_tasks * COMPLETIONS_PER_TASK} task entries!")


# --------------------------------------------------

if __name__ == "__main__":
    print("Starting database initialization...")
    initDatabase()
    initTasks(NUMBER_OF_TASKS)
    print("Database initialization complete!")