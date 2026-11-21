"""Bước `survey_import`: CSV khảo sát đã điền → kiểm tra → bảng `place_survey` (MySQL).

- Dòng chưa quyết định (`include` trống) bị bỏ qua; `include = n` được lưu để biết đã loại.
- Dòng lỗi không được nạp, ghi vào báo cáo; `strict=True` thì dừng nếu có lỗi.
- CSV là nguồn chuẩn của dữ liệu khảo sát: mỗi lần nạp thay toàn bộ nội dung bảng
  trong một transaction (idempotent).
"""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from ..clean.taxonomy import CATEGORIES
from ..common import StepResult, write_json

_BOOL = {"y": 1, "n": 0, "": None}
_FACT_FIELDS = ("opening_hours", "price_adult_vnd", "price_child_vnd",
                "typical_duration_min", "intensity")


def _int(row: dict, col: str, lo: int, hi: int, errors: list[str]) -> int | None:
    v = row.get(col, "").strip().replace(".", "").replace(",", "")
    if not v:
        return None
    if not v.isdigit() or not lo <= int(v) <= hi:
        errors.append(f"{col}={row[col]!r} phải là số nguyên trong [{lo}, {hi}]")
        return None
    return int(v)


def _bool(row: dict, col: str, errors: list[str]) -> int | None:
    v = row.get(col, "").strip().lower()
    if v not in _BOOL:
        errors.append(f"{col}={row[col]!r} phải là y/n hoặc trống")
        return None
    return _BOOL[v]


def validate_row(row: dict) -> tuple[dict | None, list[str]]:
    """Trả (bản ghi để nạp | None nếu bỏ qua, danh sách lỗi)."""
    include = row.get("include", "").strip().lower()
    if include == "":
        return None, []
    if include not in ("y", "n"):
        return None, [f"include={row['include']!r} phải là y/n"]
    pid = row["place_id"]
    if include == "n":
        return {"place_id": pid, "include": 0}, []

    errors: list[str] = []
    if row.get("status") == "stale":
        errors.append("địa điểm không còn trong dữ liệu OSM (status=stale)")

    cat_fix = row.get("category_fix", "").strip()
    if cat_fix and cat_fix not in CATEGORIES and cat_fix != "remove":
        errors.append(f"category_fix={cat_fix!r} không hợp lệ (dùng một trong {CATEGORIES} hoặc 'remove')")

    oh = row.get("opening_hours", "").strip()
    if oh and oh != "24/7" and not re.search(r"\d{1,2}:\d{2}", oh):
        errors.append(f"opening_hours={oh!r} cần dạng giờ HH:MM (vd 'Mo-Su 06:00-17:30') hoặc '24/7'")

    rec = {
        "place_id": pid, "include": 1, "category_override": cat_fix or None,
        "opening_hours": oh or None,
        "price_adult_vnd": _int(row, "price_adult_vnd", 0, 10_000_000, errors),
        "price_child_vnd": _int(row, "price_child_vnd", 0, 10_000_000, errors),
        "price_note": row.get("price_note", "").strip() or None,
        "typical_duration_min": _int(row, "typical_duration_min", 5, 720, errors),
        "intensity": _int(row, "intensity", 1, 3, errors),
        "kid_friendly": _bool(row, "kid_friendly", errors),
        "elderly_friendly": _bool(row, "elderly_friendly", errors),
        "indoor": _bool(row, "indoor", errors),
        "best_time": row.get("best_time", "").strip() or None,
        "description_vi": row.get("description_vi", "").strip() or None,
        "source_url": row.get("source_url", "").strip() or None,
        "source_note": row.get("source_note", "").strip() or None,
        "surveyed_at": None,
        "surveyor": row.get("surveyor", "").strip() or None,
        "notes": row.get("notes", "").strip() or None,
    }

    if rec["source_url"] and not re.match(r"https?://", rec["source_url"]):
        errors.append("source_url phải bắt đầu bằng http:// hoặc https://")

    has_fact = any(row.get(c, "").strip() for c in _FACT_FIELDS)
    has_price_or_hours = any(row.get(c, "").strip()
                             for c in ("opening_hours", "price_adult_vnd", "price_child_vnd"))
    if has_price_or_hours and not (rec["source_url"] or rec["source_note"]):
        errors.append("điền giờ/giá thì phải có source_url hoặc source_note (nguyên tắc kiểm chứng được)")

    sa = row.get("surveyed_at", "").strip()
    if sa:
        try:
            rec["surveyed_at"] = date.fromisoformat(sa).isoformat()
        except ValueError:
            errors.append(f"surveyed_at={sa!r} phải dạng YYYY-MM-DD")
    elif has_fact:
        errors.append("có dữ liệu khảo sát thì phải có surveyed_at")

    return (None if errors else rec), errors


def read_rows(csv_path: str | Path) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


_COLUMNS = ["place_id", "include", "category_override", "opening_hours", "price_adult_vnd",
            "price_child_vnd", "price_note", "typical_duration_min", "intensity", "kid_friendly",
            "elderly_friendly", "indoor", "best_time", "description_vi", "source_url",
            "source_note", "surveyed_at", "surveyor", "notes"]


def run(
    survey_path: str,
    report_path: str,
    database_url: str | None = None,
    strict: bool = False,
) -> StepResult:
    from ..load.mysql import (  # import muộn: validate không cần DB
        connect,
        ensure_schema,
    )

    records: list[dict] = []
    errors: list[dict] = []
    skipped = 0
    for i, row in enumerate(read_rows(survey_path), start=2):  # dòng 1 là header
        rec, errs = validate_row(row)
        if errs:
            errors.append({"line": i, "place_id": row.get("place_id"), "name": row.get("name"),
                           "errors": errs})
        elif rec is None:
            skipped += 1
        else:
            records.append(rec)

    conn = connect(database_url)
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT place_id FROM place")
            known = {r[0] for r in cur.fetchall()}
            unknown = [r for r in records if r["place_id"] not in known]
            for r in unknown:
                errors.append({"line": None, "place_id": r["place_id"], "name": None,
                               "errors": ["place_id không có trong bảng place"]})
            records = [r for r in records if r["place_id"] in known]

            if strict and errors:
                raise ValueError(f"{len(errors)} dòng lỗi, xem {report_path}")

            cur.execute("DELETE FROM place_survey")
            if records:
                cur.executemany(
                    f"INSERT INTO place_survey ({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(_COLUMNS))})",
                    [tuple(r.get(c) for c in _COLUMNS) for r in records])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        stats = {"loaded": len(records), "included": sum(r["include"] for r in records),
                 "excluded": sum(1 for r in records if not r["include"]),
                 "skipped_undecided": skipped, "errors": len(errors)}
        write_json(report_path, {"stats": stats, "errors": errors})

    return StepResult(step="survey_import", outputs=["mysql:place_survey", report_path], stats=stats)
