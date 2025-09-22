import sqlite3
import psycopg2
import os
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
# TODO: Race conditions should be investigated - handled by using transactions and locking
# TODO: What happens when a worker returns results that have not been allocated to them?


def create_connection(db_file="database.db"):
    """create a database connection to PostgreSQL (Supabase) or SQLite"""
    # Check if we have Supabase credentials in environment variables
    # supabase_host = os.getenv("DB_HOST")
    # supabase_password = os.getenv("DB_PASSWORD")

    # replace above with below to use env variables
    USER = os.getenv("DB_USER")
    PASSWORD = os.getenv("DB_PASSWORD")
    HOST = os.getenv("DB_HOST")
    PORT = os.getenv("DB_PORT")
    DBNAME = os.getenv("DB_NAME")
    if USER and PASSWORD and HOST and PORT and DBNAME:
        # Use Supabase PostgreSQL
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
            print(f"PostgreSQL connection failed, falling back to SQLite: {e}")
            # Fall back to SQLite
            return sqlite3.connect(db_file)
    else:
        # Use SQLite for local development
        return sqlite3.connect(db_file)


def allocate_task(prolific_id, session_id):
    """
    Allocates a task to a participant based on given criteria.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()

            # Use %s for PostgreSQL, ? for SQLite
            placeholder = "%s" if hasattr(conn, "server_version") else "?"

            # Check if the participant has an incomplete allocated task
            cursor.execute(
                f"SELECT id, task_number FROM tasks WHERE prolific_id={placeholder} AND status!='completed'",
                (prolific_id,),
            )
            allocated_tasks = cursor.fetchall()
            if allocated_tasks:
                return allocated_tasks[0]

            # Find a task that hasn't been assigned to this participant and has been assigned less than three times
            cursor.execute(
                f"""
                SELECT id, task_number FROM tasks 
                WHERE status='waiting' AND task_number NOT IN (
                    SELECT task_number FROM tasks WHERE prolific_id={placeholder} AND status='completed'
                )
            """,
                (prolific_id,),
            )
            waiting_tasks = cursor.fetchall()
            for task_id, task_number in waiting_tasks:
                cursor.execute(
                    f"SELECT COUNT(*) FROM tasks WHERE task_number={placeholder} AND status='allocated'",
                    (task_number,),
                )
                num_allocated = cursor.fetchone()[0]
                if num_allocated < 3:
                    cursor.execute(
                        f"UPDATE tasks SET status='allocated', prolific_id={placeholder}, time_allocated={placeholder}, session_id={placeholder} WHERE id={placeholder}",
                        (prolific_id, datetime.utcnow(), session_id, task_id),
                    )
                    conn.commit()
                    return task_id, task_number
            return None

    except (sqlite3.Error, psycopg2.Error) as e:
        return f"Database Error - {e}", -1


def expire_tasks(time_limit=3600):
    """
    Expires tasks that have been allocated for longer than a specified time limit.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now()

            placeholder = "%s" if hasattr(conn, "server_version") else "?"

            cursor.execute(
                "SELECT id, time_allocated FROM tasks WHERE status='allocated'"
            )
            allocated_tasks = cursor.fetchall()

            for task_id, time_allocated in allocated_tasks:
                print(task_id, time_allocated)

                if time_allocated is None:
                    print("Uh oh... time_allocated is None")
                    continue

                # Handle different datetime formats (PostgreSQL vs SQLite)
                if isinstance(time_allocated, str):
                    time_diff = (
                        current_time
                        - datetime.strptime(time_allocated, "%Y-%m-%d %H:%M:%S.%f")
                    ).total_seconds()
                else:
                    # PostgreSQL returns datetime objects directly
                    time_diff = (current_time - time_allocated).total_seconds()

                if time_diff > time_limit:
                    cursor.execute(
                        f"UPDATE tasks SET status='waiting', prolific_id = NULL, time_allocated = NULL, session_id = NULL WHERE id={placeholder}",
                        (task_id,),
                    )

            conn.commit()
    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred trying to expire tasks: {e}")


def complete_task(id, json_string, prolific_id):
    """
    Completes a task assigned to a participant and records the result.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()

            placeholder = "%s" if hasattr(conn, "server_version") else "?"

            cursor.execute(
                f"SELECT id FROM tasks WHERE id={placeholder} AND prolific_id={placeholder}",
                (id, prolific_id),
            )
            task = cursor.fetchone()
            if task is None:
                print("Task not allocated to participant... not completing tasks.")
                return -1

            cursor.execute(
                f"UPDATE tasks SET status='completed' WHERE id={placeholder}", (id,)
            )
            cursor.execute(
                f"INSERT INTO results (id, json_string, prolific_id) VALUES ({placeholder}, {placeholder}, {placeholder})",
                (id, json_string, prolific_id),
            )

            conn.commit()

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred trying to complete a task.: {e}")


def get_all_tasks():
    """
    Retrieves all tasks from the tasks table in the database.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks")
            tasks = cursor.fetchall()
            return tasks
    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred: {e}")
        return None


def get_specific_result(result_id):
    """
    Retrieves a specific result from the results table based on the result ID.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()

            placeholder = "%s" if hasattr(conn, "server_version") else "?"

            cursor.execute(
                f"SELECT * FROM results WHERE id={placeholder}", (result_id,)
            )
            result = cursor.fetchone()
            return result
    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred: {e}")
        return None

def store_consent(prolific_id, session_id, consent_given=True, ip_address=None):
    """
    Store consent information in the consent table.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()
            placeholder = "%s" if hasattr(conn, "server_version") else "?"
            is_postgres = hasattr(conn, "server_version")

            consent_id = str(uuid4())

            if is_postgres:
                cursor.execute(
                    f"INSERT INTO consent (id, prolific_id, session_id, consent_given, consent_timestamp, ip_address) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP, {placeholder})",
                    (consent_id, prolific_id, session_id, consent_given, ip_address),
                )
            else:
                cursor.execute(
                    f"INSERT INTO consent (id, prolific_id, session_id, consent_given, consent_timestamp, ip_address) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (
                        consent_id,
                        prolific_id,
                        session_id,
                        consent_given,
                        datetime.utcnow().isoformat(),
                        ip_address,
                    ),
                )

            conn.commit()
            return consent_id

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred storing consent: {e}")
        return None


def check_consent(prolific_id, session_id):
    """
    Check if consent has already been given for this participant/session.
    """
    try:
        with create_connection() as conn:
            cursor = conn.cursor()
            placeholder = "%s" if hasattr(conn, "server_version") else "?"

            cursor.execute(
                f"SELECT consent_given FROM consent WHERE prolific_id={placeholder} AND session_id={placeholder} ORDER BY consent_timestamp DESC LIMIT 1",
                (prolific_id, session_id),
            )
            result = cursor.fetchone()

            return result[0] if result else False

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred checking consent: {e}")
        return False

#expire_tasks()
#complete_task('9f28d264-434b-433d-abcf-4124bb97c019', '{"test": 1}', '1234')


# Allocate a task to a new participant
#result = allocate_task("dummy11", "session1")
#print("Test 1 Result:", result)

# Attempt to allocate a task to a participant who already has an allocated but not completed task
#id, task = allocate_task("dummy12", "session1")
#complete_task(id, '{"test": 1}', 'dummy12')
#print("Test 2 Result:", id)

#print(get_specific_result('8cc2c7b2-83e3-4a7d-aeb2-0efc0ce9cf39'))