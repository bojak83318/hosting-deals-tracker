from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".let-automation" / "data" / "deals.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class DBManager:
    """SQLite manager for deal history and analytics."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current < 1:
                conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                conn.execute("PRAGMA user_version = 1")

            # Graceful migration support for older/partial schemas.
            self._ensure_column(conn, "deals", "deal_key", "TEXT")
            self._ensure_column(conn, "deals", "raw_json", "TEXT")
            self._ensure_column(conn, "providers", "reputation_score", "REAL DEFAULT 0.0")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def upsert_deals(self, deals: list[dict[str, Any]]) -> dict[str, Any]:
        inserted = 0
        updated = 0
        history_added = 0
        inserted_ids: list[int] = []

        now = datetime.now().isoformat()
        with self.connect() as conn:
            for deal in deals:
                deal_key = self._build_deal_key(deal)
                thread_id = deal.get("thread_id")
                existing = conn.execute(
                    "SELECT id, price_monthly, price_yearly FROM deals WHERE deal_key = ?",
                    (deal_key,),
                ).fetchone()

                payload = self._deal_payload(deal, deal_key=deal_key, now=now)

                if existing:
                    conn.execute(
                        """
                        UPDATE deals
                           SET thread_id = :thread_id,
                               url = :url,
                               title = :title,
                               author = :author,
                               provider = :provider,
                               category = :category,
                               cpu = :cpu,
                               ram_gb = :ram_gb,
                               storage_gb = :storage_gb,
                               storage_type = :storage_type,
                               bandwidth = :bandwidth,
                               ipv4_count = :ipv4_count,
                               ipv6 = :ipv6,
                               price_monthly = :price_monthly,
                               price_yearly = :price_yearly,
                               location = :location,
                               status = :status,
                               content_preview = :content_preview,
                               date_posted = :date_posted,
                               date_fetched = :date_fetched,
                               raw_json = :raw_json,
                               updated_at = :updated_at
                         WHERE id = :id
                        """,
                        {**payload, "id": existing["id"]},
                    )
                    updated += 1

                    if self._price_changed(existing, payload):
                        self._insert_price_history(conn, existing["id"], payload["price_monthly"], payload["price_yearly"], now)
                        history_added += 1
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO deals (
                            deal_key, thread_id, url, title, author, provider, category, cpu, ram_gb,
                            storage_gb, storage_type, bandwidth, ipv4_count, ipv6, price_monthly,
                            price_yearly, location, status, content_preview, date_posted, date_fetched,
                            raw_json, created_at, updated_at
                        ) VALUES (
                            :deal_key, :thread_id, :url, :title, :author, :provider, :category, :cpu,
                            :ram_gb, :storage_gb, :storage_type, :bandwidth, :ipv4_count, :ipv6,
                            :price_monthly, :price_yearly, :location, :status, :content_preview,
                            :date_posted, :date_fetched, :raw_json, :created_at, :updated_at
                        )
                        """,
                        payload,
                    )
                    inserted += 1
                    inserted_id = int(cur.lastrowid)
                    inserted_ids.append(inserted_id)
                    self._insert_price_history(conn, inserted_id, payload["price_monthly"], payload["price_yearly"], now)
                    history_added += 1

                provider = (deal.get("provider") or "Unknown").strip()
                if provider:
                    self._upsert_provider(conn, provider, deal.get("category"), now)

        return {
            "inserted": inserted,
            "updated": updated,
            "price_history_added": history_added,
            "inserted_ids": inserted_ids,
        }

    def get_latest(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM deals ORDER BY COALESCE(date_posted, date_fetched) DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_deal_by_id(self, deal_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        return dict(row) if row else None

    def get_by_provider(self, provider: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM deals WHERE provider = ? ORDER BY COALESCE(date_posted, date_fetched) DESC, id DESC LIMIT ?",
                (provider, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def query_deals(
        self,
        search: str | None = None,
        provider: str | None = None,
        category: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        sort: str = "date_desc",
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []

        if search:
            where.append(
                "(COALESCE(title,'') LIKE ? OR COALESCE(provider,'') LIKE ? OR "
                "COALESCE(content_preview,'') LIKE ? OR COALESCE(storage_type,'') LIKE ?)"
            )
            token = f"%{search}%"
            params.extend([token, token, token, token])

        if provider:
            where.append("provider = ?")
            params.append(provider)

        if category:
            where.append("category = ?")
            params.append(category)

        if price_min is not None:
            where.append("COALESCE(price_monthly, 999999999) >= ?")
            params.append(price_min)

        if price_max is not None:
            where.append("COALESCE(price_monthly, 0) <= ?")
            params.append(price_max)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        sort_map = {
            "date_desc": "COALESCE(date_posted, date_fetched) DESC, id DESC",
            "date_asc": "COALESCE(date_posted, date_fetched) ASC, id ASC",
            "price_asc": "COALESCE(price_monthly, 999999999) ASC, id DESC",
            "price_desc": "COALESCE(price_monthly, 0) DESC, id DESC",
        }
        order_by = sort_map.get(sort, sort_map["date_desc"])

        offset = max(page - 1, 0) * per_page

        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM deals {where_sql}", params).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT * FROM deals
                {where_sql}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                [*params, per_page, offset],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def get_price_history(self, deal_id: int | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        if deal_id is None and thread_id is None:
            raise ValueError("deal_id or thread_id is required")

        with self.connect() as conn:
            if deal_id is None:
                row = conn.execute("SELECT id FROM deals WHERE thread_id = ? ORDER BY id DESC LIMIT 1", (thread_id,)).fetchone()
                if not row:
                    return []
                deal_id = int(row["id"])

            rows = conn.execute(
                """
                SELECT ph.id, ph.deal_id, ph.price_monthly, ph.price_yearly, ph.date_recorded
                  FROM price_history ph
                 WHERE ph.deal_id = ?
              ORDER BY ph.date_recorded ASC, ph.id ASC
                """,
                (deal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _build_deal_key(self, deal: dict[str, Any]) -> str:
        thread_id = (deal.get("thread_id") or "").strip()
        url = (deal.get("url") or "").strip()
        title = (deal.get("title") or "").strip().lower()
        provider = (deal.get("provider") or "").strip().lower()

        if thread_id:
            return f"thread:{thread_id}"
        if url:
            return f"url:{url}"
        return f"title:{title}|provider:{provider}"

    def _deal_payload(self, deal: dict[str, Any], deal_key: str, now: str) -> dict[str, Any]:
        return {
            "deal_key": deal_key,
            "thread_id": deal.get("thread_id"),
            "url": deal.get("url"),
            "title": deal.get("title") or "",
            "author": deal.get("author") or "Unknown",
            "provider": deal.get("provider") or "Unknown",
            "category": deal.get("category"),
            "cpu": deal.get("cpu"),
            "ram_gb": deal.get("ram_gb"),
            "storage_gb": deal.get("storage_gb"),
            "storage_type": deal.get("storage_type"),
            "bandwidth": deal.get("bandwidth"),
            "ipv4_count": deal.get("ipv4_count", 1),
            "ipv6": 1 if deal.get("ipv6") else 0,
            "price_monthly": deal.get("price_monthly"),
            "price_yearly": deal.get("price_yearly"),
            "location": deal.get("location"),
            "status": deal.get("status"),
            "content_preview": deal.get("content_preview"),
            "date_posted": deal.get("post_date"),
            "date_fetched": deal.get("fetch_date") or now,
            "raw_json": json.dumps(deal, ensure_ascii=True, default=str),
            "created_at": now,
            "updated_at": now,
        }

    def _price_changed(self, existing: sqlite3.Row, payload: dict[str, Any]) -> bool:
        old_monthly = existing["price_monthly"]
        old_yearly = existing["price_yearly"]
        new_monthly = payload.get("price_monthly")
        new_yearly = payload.get("price_yearly")
        return old_monthly != new_monthly or old_yearly != new_yearly

    def _insert_price_history(
        self,
        conn: sqlite3.Connection,
        deal_id: int,
        price_monthly: float | None,
        price_yearly: float | None,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO price_history (deal_id, price_monthly, price_yearly, date_recorded)
            VALUES (?, ?, ?, ?)
            """,
            (deal_id, price_monthly, price_yearly, now),
        )

    def _upsert_provider(self, conn: sqlite3.Connection, name: str, category: str | None, now: str) -> None:
        existing = conn.execute("SELECT id FROM providers WHERE name = ?", (name,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE providers SET category = COALESCE(?, category), updated_at = ? WHERE id = ?",
                (category, now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO providers (name, category, reputation_score, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (name, category, 0.0, now, now),
            )
