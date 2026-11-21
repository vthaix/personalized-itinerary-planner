"""Bước `load`: `places.jsonl` → bảng `place` trong MySQL.

Idempotent: upsert theo `place_id`; bản ghi cùng nguồn không còn xuất hiện trong lần nạp
này bị đánh dấu `is_active = 0` (không xoá, để giữ liên kết với đánh giá của người dùng).

    from itinerary_pipelines.load import mysql
    mysql.run("data/processed/places_nhatrang.jsonl")            # dùng DATABASE_URL
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from importlib.resources import files
from urllib.parse import unquote, urlparse

import pymysql

from ..common import StepResult, read_jsonl, utc_now

_COLUMNS = [
    "place_id", "source", "osm_type", "osm_id", "name", "name_en", "name_norm",
    "category", "category_group", "lat", "lon", "address", "opening_hours_raw",
    "website", "phone", "wikidata", "wikipedia", "wikimedia_commons",
    "osm_tags", "merged_from", "license", "fetched_at", "osm_base", "is_active", "last_seen_run",
]
_UPDATABLE = [c for c in _COLUMNS if c != "place_id"] + ["location"]

_UPSERT_SQL = (
    f"INSERT INTO place ({', '.join(_COLUMNS)}, location) "
    f"VALUES ({', '.join(['%s'] * len(_COLUMNS))}, ST_SRID(POINT(%s, %s), 4326)) AS new "
    f"ON DUPLICATE KEY UPDATE {', '.join(f'{c} = new.{c}' for c in _UPDATABLE)}"
)


def connect(database_url: str | None = None) -> pymysql.connections.Connection:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL (vd. mysql+pymysql://user:pass@localhost:3306/planner)")
    u = urlparse(url)
    if not u.scheme.startswith("mysql"):
        raise ValueError(f"DATABASE_URL không phải MySQL: {u.scheme}")
    return pymysql.connect(
        host=u.hostname or "localhost", port=u.port or 3306,
        user=unquote(u.username or ""), password=unquote(u.password or ""),
        database=u.path.lstrip("/"), charset="utf8mb4", autocommit=False,
    )


def ensure_schema(conn: pymysql.connections.Connection) -> None:
    ddl = files("itinerary_pipelines.load").joinpath("schema.sql").read_text(encoding="utf-8")
    # bỏ dòng chú thích trước khi tách câu (chú thích có thể chứa ';')
    ddl = "\n".join(line for line in ddl.splitlines() if not line.lstrip().startswith("--"))
    with conn.cursor() as cur:
        for stmt in (s.strip() for s in ddl.split(";")):
            if stmt:
                cur.execute(stmt)
    conn.commit()


def _to_mysql_dt(iso: str | None) -> str | None:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)  # Python ≥ 3.11 hiểu hậu tố "Z"
    if dt.tzinfo:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _row(p: dict, run_id: str) -> tuple:
    values = {
        **p,
        "category_group": p["group"],
        "osm_tags": json.dumps(p.get("osm_tags") or {}, ensure_ascii=False),
        "merged_from": json.dumps(p.get("merged_from") or []),
        "fetched_at": _to_mysql_dt(p.get("fetched_at")),
        "osm_base": _to_mysql_dt(p.get("osm_base")),
        "is_active": 1,
        "last_seen_run": run_id,
    }
    return (*(values.get(c) for c in _COLUMNS), p["lon"], p["lat"])  # POINT(lon, lat) — ADR 0004


def run(
    input_path: str,
    database_url: str | None = None,
    source: str = "osm",
    min_rows: int = 1,
    batch_size: int = 500,
) -> StepResult:
    places = [p for p in read_jsonl(input_path) if p.get("source") == source]
    if len(places) < min_rows:
        # Tránh trường hợp file rỗng/lỗi làm vô hiệu hoá toàn bộ dữ liệu cũ
        raise RuntimeError(f"Chỉ có {len(places)} bản ghi nguồn '{source}' (< min_rows={min_rows}); dừng nạp")

    run_id = f"{utc_now()}#{uuid.uuid4().hex[:8]}"
    conn = connect(database_url)
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT place_id FROM place WHERE source = %s", (source,))
            existing = {r[0] for r in cur.fetchall()}
            rows = [_row(p, run_id) for p in places]
            for i in range(0, len(rows), batch_size):
                cur.executemany(_UPSERT_SQL, rows[i:i + batch_size])
            cur.execute(
                "UPDATE place SET is_active = 0 WHERE source = %s AND last_seen_run <> %s AND is_active = 1",
                (source, run_id))
            deactivated = cur.rowcount
            cur.execute("SELECT COUNT(*) FROM place WHERE source = %s AND is_active = 1", (source,))
            active = cur.fetchone()[0]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    ids = {p["place_id"] for p in places}
    return StepResult(
        step="load",
        outputs=["mysql:place"],
        stats={"input": len(places), "inserted": len(ids - existing),
               "updated": len(ids & existing), "deactivated": deactivated,
               "active": active, "run_id": run_id},
    )
