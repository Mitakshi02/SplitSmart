"""
SplitSmart Database Connection & Pool Manager
Utilizes mysql.connector.pooling.MySQLConnectionPool with robust context-managed checkout.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Any, Optional, Tuple, Dict, List, Union

# Load environment configuration from project root explicitly
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")

try:
    from dotenv import load_dotenv
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

import mysql.connector
from mysql.connector import pooling, Error

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Global connection pool instance
_connection_pool: Optional[pooling.MySQLConnectionPool] = None


def get_db_config(include_database: bool = True) -> Dict[str, Any]:
    """Extract database configuration from environment variables."""
    port_env = os.getenv("DB_PORT", "").strip()
    port = int(port_env) if port_env.isdigit() else 3306

    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": port,
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": False,
        "use_pure": True,  # Pure Python implementation ensures consistent Decimal and JSON handling
    }
    if include_database:
        config["database"] = os.getenv("DB_NAME", "splitsmart_db")
    return config


def create_database_if_not_exists() -> None:
    """Connects to MySQL server without database selected and ensures DB_NAME exists."""
    db_name = os.getenv("DB_NAME", "splitsmart_db")
    config_no_db = get_db_config(include_database=False)
    try:
        conn = mysql.connector.connect(**config_no_db)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Database '{db_name}' verified / created successfully.")
    except Error as err:
        logger.warning(f"Could not auto-create database '{db_name}': {err}")


def init_db_pool(pool_name: Optional[str] = None, pool_size: Optional[int] = None) -> pooling.MySQLConnectionPool:
    """
    Initializes or returns the existing MySQL connection pool.
    Thread-safe and reused across requests.
    """
    global _connection_pool
    if _connection_pool is not None:
        return _connection_pool

    # Ensure database exists before pool checkout
    create_database_if_not_exists()

    config = get_db_config(include_database=True)
    p_name = pool_name or os.getenv("DB_POOL_NAME", "splitsmart_pool")
    size_env = os.getenv("DB_POOL_SIZE", "").strip()
    p_size = pool_size or (int(size_env) if size_env.isdigit() else 10)

    try:
        logger.info(f"Initializing MySQL connection pool '{p_name}' (size: {p_size}) for database '{config['database']}' at {config['host']}:{config['port']}...")
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name=p_name,
            pool_size=p_size,
            pool_reset_session=True,
            **config
        )
        logger.info("MySQL connection pool initialized successfully.")
        return _connection_pool
    except Error as err:
        logger.error(f"Failed to initialize MySQL Connection Pool: {err}")
        raise


def get_pool() -> pooling.MySQLConnectionPool:
    """Retrieve the active pool or initialize if not yet established."""
    global _connection_pool
    if _connection_pool is None:
        return init_db_pool()
    return _connection_pool


@contextmanager
def get_db_connection() -> Generator[mysql.connector.connection.MySQLConnection, None, None]:
    """
    Context manager for checking out a raw connection from the pool.
    Commits on successful exit, rolls back on error, and always returns the connection to the pool.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(...)
    """
    pool = get_pool()
    conn = None
    try:
        conn = pool.get_connection()
        yield conn
        conn.commit()
    except Exception as exc:
        if conn is not None and conn.is_connected():
            logger.warning(f"Transaction failed, performing rollback. Reason: {exc}")
            conn.rollback()
        raise exc
    finally:
        if conn is not None and conn.is_connected():
            conn.close()  # Returns connection back to pool


@contextmanager
def get_db_cursor(
    dictionary: bool = True, 
    buffered: bool = True
) -> Generator[Tuple[Any, mysql.connector.connection.MySQLConnection], None, None]:
    """
    Context manager yielding a (cursor, connection) pair.
    
    Usage:
        with get_db_cursor() as (cursor, conn):
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary, buffered=buffered)
        try:
            yield cursor, conn
        finally:
            cursor.close()


def execute_query(
    query: str, 
    params: Optional[Union[Tuple[Any, ...], Dict[str, Any]]] = None, 
    fetchone: bool = False, 
    fetchall: bool = True,
    dictionary: bool = True
) -> Any:
    """
    Helper function to run a SELECT query with safe parameter binding.
    """
    with get_db_cursor(dictionary=dictionary) as (cursor, _):
        cursor.execute(query, params or ())
        if fetchone:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()
        return None


def execute_write(query: str, params: Optional[Union[Tuple[Any, ...], Dict[str, Any]]] = None) -> int:
    """
    Helper function to run an INSERT / UPDATE / DELETE query.
    Returns lastrowid for INSERT or rowcount for UPDATE/DELETE.
    """
    with get_db_cursor() as (cursor, _):
        cursor.execute(query, params or ())
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount


def init_db(schema_path: str = "schema.sql") -> None:
    """
    Utility function to run schema.sql and create tables.
    Works cleanly across both pure-Python and C-extension MySQL connector modes.
    """
    if not os.path.isabs(schema_path):
        schema_path = os.path.join(base_dir, schema_path)

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    # Split statements by semicolon while ignoring comments
    statements = []
    current_chunk = []
    for line in sql_script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current_chunk.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current_chunk))
            current_chunk = []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            for stmt in statements:
                clean_stmt = stmt.strip()
                if clean_stmt:
                    cursor.execute(clean_stmt)
            logger.info("Database schema initialized successfully from %s", schema_path)
        finally:
            cursor.close()


if __name__ == "__main__":
    import sys
    print("Testing SplitSmart Database Connection...")
    try:
        pool = init_db_pool()
        with get_db_cursor() as (cur, conn):
            cur.execute("SELECT 1 AS test_connection")
            res = cur.fetchone()
            print(f"Connection test successful: {res}")
            
            # Check if tables exist
            cur.execute("SHOW TABLES")
            tables = [list(r.values())[0] for r in cur.fetchall()]
            print(f"Current tables in database '{os.getenv('DB_NAME', 'splitsmart_db')}': {tables}")
            
            if not tables:
                print("\nTables not found. Initializing schema now...")
                init_db()
                cur.execute("SHOW TABLES")
                tables = [list(r.values())[0] for r in cur.fetchall()]
                print(f"Tables successfully created: {tables}")
    except Exception as e:
        print(f"\n[Database Connection Error]: {e}")
        db_pwd = os.getenv("DB_PASSWORD", "")
        if not db_pwd:
            print("--> Note: DB_PASSWORD in your .env file is currently EMPTY.")
            print("--> If your MySQL root account has a password, please set DB_PASSWORD=your_password in j:\\python project\\.env")
        else:
            print("--> Please verify your MySQL credentials in j:\\python project\\.env")
        sys.exit(1)
