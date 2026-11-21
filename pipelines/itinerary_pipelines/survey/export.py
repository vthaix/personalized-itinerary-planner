"""Bước `survey_export`: places.jsonl → CSV khảo sát tầng 1 (điểm tham quan).

Chạy lại an toàn: cột tự động được làm mới, **cột nhập tay được giữ nguyên** theo place_id;
địa điểm không còn trong dữ liệu vẫn giữ dòng nhưng `status = stale`.
CSV ghi UTF-8 có BOM để Excel/Google Sheets mở đúng tiếng Việt.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..common import StepResult, read_json, read_jsonl, write_meta
from .flags import detect_flags, is_minor, priority

AUTO_COLUMNS = [
    "place_id", "status", "priority", "suggested", "flags", "name", "name_en", "category",
    "lat", "lon", "osm_url", "wikipedia", "website", "opening_hours_osm",
]
MANUAL_COLUMNS = [
    "include",               # y / n — đưa vào tầng 1 hay không
    "category_fix",          # category đúng nếu OSM gắn sai; "remove" nếu không phải điểm tham quan
    "opening_hours",         # cú pháp OSM, vd "Mo-Su 06:00-17:30"
    "price_adult_vnd", "price_child_vnd", "price_note",
    "typical_duration_min",  # thời gian tham quan điển hình (phút)
    "intensity",             # 1 nhẹ / 2 vừa / 3 nặng (thang mục 6.2)
    "kid_friendly", "elderly_friendly", "indoor",   # y / n
    "best_time",             # vd "sáng sớm", "hoàng hôn"
    "description_vi",        # 2–4 câu, tự viết
    "source_url", "source_note",  # bắt buộc khi điền giờ/giá
    "surveyed_at",           # YYYY-MM-DD
    "surveyor", "notes",
]
COLUMNS = AUTO_COLUMNS + MANUAL_COLUMNS

_OSM_TYPE = {"n": "node", "w": "way", "r": "relation"}


def _osm_url(place_id: str) -> str:
    code = place_id.split(":", 1)[1]
    return f"https://www.openstreetmap.org/{_OSM_TYPE[code[0]]}/{code[1:]}"


def _read_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["place_id"]: r for r in csv.DictReader(f) if r.get("place_id")}


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)  # ghi nguyên tử: không làm hỏng file đang có công sức nhập tay


def run(
    places_path: str,
    output_path: str,
    clean_report_path: str | None = None,
    group: str = "tham_quan",
    suggest_threshold: int = 6,
) -> StepResult:
    out = Path(output_path)
    cross_ids: set[str] = set()
    if clean_report_path and Path(clean_report_path).exists():
        for p in read_json(clean_report_path).get("review_cross_group_same_name", []):
            cross_ids.update((p["a"], p["b"]))

    existing = _read_existing(out)
    rows: list[dict] = []
    seen: set[str] = set()
    for p in read_jsonl(places_path):
        if p["group"] != group:
            continue
        flags = detect_flags(p, cross_ids)
        prio = priority(p, flags)
        auto = {
            "place_id": p["place_id"], "status": "active", "priority": prio,
            "suggested": "y" if prio >= suggest_threshold and not flags else "",
            "flags": ";".join(flags + (["minor_feature"] if is_minor(p) else [])),
            "name": p["name"], "name_en": p.get("name_en") or "", "category": p["category"],
            "lat": p["lat"], "lon": p["lon"], "osm_url": _osm_url(p["place_id"]),
            "wikipedia": p.get("wikipedia") or "", "website": p.get("website") or "",
            "opening_hours_osm": p.get("opening_hours_raw") or "",
        }
        manual = {c: existing.get(p["place_id"], {}).get(c, "") for c in MANUAL_COLUMNS}
        rows.append({**auto, **manual})
        seen.add(p["place_id"])

    stale = [{**r, "status": "stale"} for pid, r in existing.items() if pid not in seen]
    rows.sort(key=lambda r: (-int(r["priority"]), r["name"], r["place_id"]))
    rows += sorted(stale, key=lambda r: r["place_id"])
    _write_csv(out, rows, COLUMNS)

    flagged = [r for r in rows if r["flags"] and r["flags"] != "minor_feature"]
    flagged_path = out.with_name(out.stem + ".flagged.csv")
    _write_csv(flagged_path, flagged, ["place_id", "flags", "name", "category", "osm_url"])

    manual_filled = sum(1 for r in rows if any(r.get(c) for c in MANUAL_COLUMNS))
    result = StepResult(
        step="survey_export", outputs=[str(out), str(flagged_path)],
        stats={"rows": len(rows), "suggested": sum(r["suggested"] == "y" for r in rows),
               "flagged": len(flagged), "stale": len(stale),
               "rows_with_manual_data_preserved": manual_filled},
    )
    write_meta(out, result, input=places_path, group=group, suggest_threshold=suggest_threshold)
    return result
