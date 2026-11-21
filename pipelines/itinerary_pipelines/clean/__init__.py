"""Bước `clean`: file OSM thô → `places.jsonl` đã chuẩn hoá, bỏ điểm không tên, gộp trùng.

    from itinerary_pipelines import clean
    clean.run("data/raw/osm_nhatrang.json", "data/processed/places_nhatrang.jsonl")
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ..common import StepResult, read_json, write_json, write_jsonl, write_meta
from .dedup import deduplicate
from .normalize import to_record

__all__ = ["run"]

_SAMPLES_PER_REASON = 20


def run(
    input_path: str,
    output_path: str,
    report_path: str | None = None,
) -> StepResult:
    raw = read_json(input_path)
    fetched_at, osm_base = raw.get("fetched_at"), raw.get("osm_base")

    kept: list[dict] = []
    dropped: Counter[str] = Counter()
    dropped_samples: dict[str, list[dict]] = defaultdict(list)
    for el in raw["elements"]:
        rec, reason = to_record(el, fetched_at, osm_base)
        if rec is not None:
            kept.append(rec)
            continue
        dropped[reason] += 1
        if len(dropped_samples[reason]) < _SAMPLES_PER_REASON:
            t = el.get("tags", {})
            dropped_samples[reason].append(
                {"id": f"{el.get('type')}/{el.get('id')}", "name": t.get("name"),
                 "tags": {k: v for k, v in t.items() if not k.startswith("name:")}})

    places, dedup_report = deduplicate(kept)

    n = write_jsonl(output_path, places)
    report_path = report_path or str(Path(output_path).with_name("clean_report.json"))
    stats = {
        "input": len(raw["elements"]),
        "after_filter": len(kept),
        "output": n,
        "dropped": dict(dropped.most_common()),
        "merged_groups": len(dedup_report["merged_groups"]),
        "merged_records": sum(len(g["merged"]) for g in dedup_report["merged_groups"]),
        "review_cross_group": len(dedup_report["review_cross_group_same_name"]),
        "review_fuzzy": len(dedup_report["review_fuzzy_names"]),
        "by_group": dict(Counter(p["group"] for p in places).most_common()),
        "by_category": dict(Counter(p["category"] for p in places).most_common()),
    }
    write_json(report_path, {"stats": stats, "dropped_samples": dropped_samples, **dedup_report})

    result = StepResult(step="clean", outputs=[output_path, report_path], stats=stats)
    write_meta(output_path, result, input=input_path, source=raw.get("source"),
               license=raw.get("license"), osm_base=osm_base)
    return result
