import sqlite3
from pathlib import Path

def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE, size INTEGER, mtime REAL, ext TEXT
        )
    """)
    return conn

def insert_files(conn, rows):
    conn.executemany("INSERT OR REPLACE INTO files (path, size, mtime, ext) VALUES (?, ?, ?, ?)", rows)
    conn.commit()

def clear_db(conn):
    conn.execute("DELETE FROM files")
    conn.commit()

def get_top_files(conn, limit=20):
    return conn.execute("SELECT path, size FROM files ORDER BY size DESC LIMIT ?", (limit,)).fetchall()

def get_all_files(conn, path_filter=None):
    if path_filter:
        return conn.execute("SELECT path, size FROM files WHERE path LIKE ?", (f"{path_filter}%",)).fetchall()
    return conn.execute("SELECT path, size FROM files").fetchall()

def get_extension_usage(conn, path_filter=None):
    query = "SELECT ext, SUM(size) FROM files"
    params = []
    if path_filter:
        query += " WHERE path LIKE ?"
        params.append(f"{path_filter}%")
    query += " GROUP BY ext ORDER BY SUM(size) DESC"
    return conn.execute(query, params).fetchall()
