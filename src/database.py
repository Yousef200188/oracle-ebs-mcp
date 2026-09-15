"""
Database connection pool and execution layer for Oracle EBS MCP Server.
Utilizes the official Python 'oracledb' driver in thin mode.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple
try:
    import oracledb
except ImportError:
    oracledb = None

from .config import OracleEBSConfig, get_config
from .security import mask_secrets

logger = logging.getLogger("oracle_ebs_mcp.database")

# Module-level connection pool instance
_pool: Optional[Any] = None


class DatabaseError(Exception):
    """Base exception for Oracle database execution issues."""
    pass


class QueryTimeoutError(DatabaseError):
    """Raised when an Oracle query exceeds the configured timeout."""
    pass


class RowLimitExceededWarning(Warning):
    """Warning emitted when results are truncated by the maximum row limit."""
    pass


def init_pool(config: Optional[OracleEBSConfig] = None) -> Any:
    """Initialize the Oracle connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    if oracledb is None:
        raise DatabaseError(
            "Oracle driver 'oracledb' is not installed. Please run: pip install -r requirements.txt"
        )

    cfg = config or get_config()
    logger.info("Initializing Oracle connection pool for %s (pool: %d-%d)", cfg.safe_dsn, cfg.oracle_pool_min, cfg.oracle_pool_max)

    try:
        # Default oracledb runs in Thin Mode (pure Python, no Instant Client binaries needed)
        _pool = oracledb.create_pool(
            user=cfg.oracle_user,
            password=cfg.oracle_password,
            dsn=cfg.dsn,
            min=cfg.oracle_pool_min,
            max=cfg.oracle_pool_max,
            increment=cfg.oracle_pool_increment,
            timeout=60,
            wait_timeout=10,
        )
        logger.info("Oracle connection pool initialized successfully.")
        return _pool
    except oracledb.Error as e:
        error_obj, = e.args
        safe_msg = mask_secrets(str(error_obj.message))
        logger.error("Failed to initialize Oracle connection pool: %s", safe_msg)
        raise DatabaseError(f"Database connection initialization failed: {safe_msg}") from e


def close_pool() -> None:
    """Close the connection pool cleanly."""
    global _pool
    if _pool is not None:
        try:
            _pool.close()
            logger.info("Oracle connection pool closed.")
        except Exception as e:
            logger.warning("Error while closing connection pool: %s", e)
        finally:
            _pool = None


@contextmanager
def get_connection(config: Optional[OracleEBSConfig] = None) -> Generator[Any, None, None]:
    """
    Context manager yielding a pooled database connection with safety timeouts.
    Ensures safe return to pool and rollback of any uncommitted changes.
    """
    cfg = config or get_config()
    pool = init_pool(cfg)

    conn = None
    try:
        conn = pool.acquire()
        # Set call_timeout in milliseconds for query timeout enforcement
        conn.call_timeout = cfg.query_timeout_seconds * 1000
        yield conn
    except oracledb.OperationalError as e:
        error_obj, = e.args
        safe_msg = mask_secrets(str(error_obj.message))
        if "DPI-1067" in safe_msg or "timeout" in safe_msg.lower():
            raise QueryTimeoutError(f"Query timed out after {cfg.query_timeout_seconds} seconds.") from e
        raise DatabaseError(f"Database operational error: {safe_msg}") from e
    except oracledb.Error as e:
        error_obj, = e.args
        safe_msg = mask_secrets(str(error_obj.message))
        raise DatabaseError(f"Oracle error: {safe_msg}") from e
    finally:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                pool.release(conn)
            except Exception as e:
                logger.warning("Failed to release connection back to pool: %s", e)


def convert_oracle_value(val: Any) -> Any:
    """Convert Oracle specific types (LOBs, Timestamps, Dates) to JSON-safe primitives."""
    if val is None:
        return None
    if oracledb is not None and isinstance(val, (oracledb.LOB,)):
        try:
            return val.read()
        except Exception:
            return str(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def execute_query(
    sql_query: str,
    params: Optional[Dict[str, Any]] = None,
    max_rows: Optional[int] = None,
    config: Optional[OracleEBSConfig] = None,
) -> Dict[str, Any]:
    """
    Execute a parameterized read-only SQL query and return structured results.
    
    Returns:
        dict containing:
            - columns: list of column names
            - rows: list of dicts (column -> value)
            - row_count: number of rows returned
            - truncated: boolean indicating if max_rows was reached
    """
    cfg = config or get_config()
    limit = min(max_rows or cfg.max_query_rows, cfg.max_query_rows)
    bind_params = params or {}

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(sql_query, bind_params)
            except oracledb.OperationalError as e:
                error_obj, = e.args
                safe_msg = mask_secrets(str(error_obj.message))
                if "DPI-1067" in safe_msg or "timeout" in safe_msg.lower():
                    raise QueryTimeoutError(f"Query execution timed out after {cfg.query_timeout_seconds}s.") from e
                raise DatabaseError(f"Database error executing query: {safe_msg}") from e
            except oracledb.Error as e:
                error_obj, = e.args
                safe_msg = mask_secrets(str(error_obj.message))
                raise DatabaseError(f"SQL execution error: {safe_msg}") from e

            if not cursor.description:
                return {"columns": [], "rows": [], "row_count": 0, "truncated": False}

            columns = [col[0].upper() for col in cursor.description]

            # Fetch limit + 1 to detect truncation
            fetched_rows = cursor.fetchmany(limit + 1)
            is_truncated = len(fetched_rows) > limit
            result_rows = fetched_rows[:limit]

            formatted_rows: List[Dict[str, Any]] = []
            for row in result_rows:
                row_dict = {}
                for col_name, val in zip(columns, row):
                    row_dict[col_name] = convert_oracle_value(val)
                formatted_rows.append(row_dict)

            return {
                "columns": columns,
                "rows": formatted_rows,
                "row_count": len(formatted_rows),
                "truncated": is_truncated,
            }


def init_ebs_session(
    cursor: Any,
    user_id: int = 0,
    resp_id: int = 20420,
    resp_appl_id: int = 800,
) -> None:
    """
    Initialize Oracle EBS apps context via FND_GLOBAL.APPS_INITIALIZE.
    Required before calling EBS APIs like FND_REQUEST.SUBMIT_REQUEST.
    Defaults to SYSADMIN / System Administrator.
    """
    try:
        cursor.execute(
            """
            BEGIN
                FND_GLOBAL.APPS_INITIALIZE(
                    user_id      => :user_id,
                    resp_id      => :resp_id,
                    resp_appl_id => :resp_appl_id
                );
            END;
            """,
            {"user_id": user_id, "resp_id": resp_id, "resp_appl_id": resp_appl_id},
        )
    except oracledb.Error as e:
        error_obj, = e.args
        raise DatabaseError(f"Failed to initialize Oracle EBS context: {error_obj.message}") from e
