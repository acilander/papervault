import sqlite3
import threading
from contextlib import contextmanager

_local = threading.local()

def _connect():
    import db
    # If this thread does not have an active database connection, OR
    # if the database path has changed (which happens between individual unit tests),
    # close the old connection and open a new one.
    if not hasattr(_local, "conn") or getattr(_local, "db_path", None) != db.DB_PATH:
        # Close previous connection if exists to prevent leaks
        if hasattr(_local, "conn"):
            try:
                _local.conn.close()
            except Exception:
                pass

        conn = sqlite3.connect(db.DB_PATH, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _local.db_path = db.DB_PATH
    return _local.conn

@contextmanager
def get_conn():
    conn = _connect()
    if not hasattr(_local, "nesting_depth"):
        _local.nesting_depth = 0

    _local.nesting_depth += 1
    try:
        yield conn
        if _local.nesting_depth == 1:
            conn.commit()
    except Exception:
        if _local.nesting_depth == 1:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        _local.nesting_depth -= 1
    # Note: We do NOT close the connection here. It remains alive in thread-local storage
    # to be reused in subsequent queries, fully eliminating connection overhead!
