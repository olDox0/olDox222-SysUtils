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

def get_all_files(conn):
    return conn.execute("SELECT path, size FROM files").fetchall()

def get_extension_usage(conn):
    return conn.execute("SELECT ext, SUM(size) FROM files GROUP BY ext ORDER BY SUM(size) DESC").fetchall()
