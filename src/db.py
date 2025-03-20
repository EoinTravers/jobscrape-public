import sqlite3
import hashlib
import json
from typing import Optional, Dict, Any

from .typedefs import RawPage


class DB:
    def __init__(self, db_path: str = "data/jobsearch.db"):
        self.db_path: str = db_path
        self.setup_database()

    def setup_database(self) -> None:
        """Initialize SQLite database with required tables"""
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        cursor: sqlite3.Cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                html TEXT,
                metadata TEXT,
                capture_time TIMESTAMP,
                content_hash TEXT,
                UNIQUE(url, content_hash)
            )
        """)
        conn.commit()
        conn.close()

    def save_page(self, page: RawPage) -> None:
        """Save a page to the database"""
        content_hash = hashlib.sha256(page.html.encode()).hexdigest()
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        cursor: sqlite3.Cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO pages 
            (url, title, html, metadata, capture_time, content_hash)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
        """,
            (page.url, page.title, page.html, json.dumps(page.metadata), content_hash),
        )

        conn.commit()
        conn.close()

    def get_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve a page from the database by URL"""
        conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        cursor: sqlite3.Cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, url, title, html, metadata, capture_time, content_hash 
            FROM pages 
            WHERE url = ?
            ORDER BY capture_time DESC 
            LIMIT 1
        """,
            (url,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "url": row[1],
                "title": row[2],
                "html": row[3],
                "metadata": row[4],
                "capture_time": row[5],
                "content_hash": row[6],
            }
        return None


def check_db_contents():
    from .extract import read_from_db
    data = read_from_db()
    print(f"Found {len(data)} pages")
    print("\nLast entry:")
    print(data.iloc[-1])

if __name__ == "__main__":
    check_db_contents()
