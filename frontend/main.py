from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    logger.info("Starting FastAPI server")


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "data" / "news.db"


def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/news")
async def get_news(
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if category:
            where_clauses.append("c.category = ?")
            params.append(category)
        if source:
            where_clauses.append("r.source = ?")
            params.append(source)
        if start_date:
            where_clauses.append("r.time >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("r.time <= ?")
            params.append(end_date)

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        offset = (page - 1) * page_size

        count_sql = f"SELECT COUNT(*) FROM raw_news r LEFT JOIN classified_news c ON r.id = c.raw_id{where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        sql = f"""
            SELECT r.id, r.title, r.time, r.source, r.url, r.content,
                   c.category, c.analysis_report, r.created_at
            FROM raw_news r
            LEFT JOIN classified_news c ON r.id = c.raw_id
            {where_sql}
            ORDER BY r.time DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(sql, params + [page_size, offset])
        rows = cursor.fetchall()
    finally:
        if conn:
            conn.close()

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "title": row["title"],
            "time": row["time"],
            "source": row["source"],
            "url": row["url"],
            "content": row["content"],
            "category": row["category"] or "",
            "analysis_report": row["analysis_report"] or "",
            "created_at": row["created_at"],
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/stats")
async def get_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM raw_news")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COALESCE(c.category, '未分类'), COUNT(*)
            FROM raw_news r
            LEFT JOIN classified_news c ON r.id = c.raw_id
            GROUP BY c.category
        """)
        categories = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT source, COUNT(*) FROM raw_news GROUP BY source")
        sources = {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        if conn:
            conn.close()

    return {"total": total, "categories": categories, "sources": sources}


app.mount("/static", StaticFiles(directory="static"), name="static")
