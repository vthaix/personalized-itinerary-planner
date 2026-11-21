"""Bước `coverage`: báo cáo mức phủ thẻ OSM theo nhóm loại hình (đọc file thô)."""

from __future__ import annotations

from collections import Counter, defaultdict

from ..clean.taxonomy import classify
from ..common import StepResult, read_json

TAGS = ["name", "name:vi", "name:en", "opening_hours", "website", "phone",
        "wikidata", "wikipedia", "fee", "charge", "cuisine", "description",
        "addr:street", "stars", "image"]


def run(input_path: str) -> StepResult:
    data = read_json(input_path)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for el in data["elements"]:
        tags = el.get("tags", {})
        c = classify(tags)
        by_group[c.group if c else "(loại bỏ)"].append(tags)

    coverage = {
        g: {"count": len(items),
            **{t: round(100 * sum(t in x for x in items) / len(items), 1) for t in TAGS}}
        for g, items in sorted(by_group.items())
    }
    return StepResult(
        step="coverage",
        stats={"total": len(data["elements"]), "osm_base": data.get("osm_base"),
               "by_group": coverage},
    )


def format_report(result: StepResult) -> str:
    s = result.stats
    lines = [f"Tổng: {s['total']} phần tử | OSM base: {s['osm_base']}", ""]
    header = f"{'Nhóm':<12}{'SL':>6}" + "".join(f"{t[:10]:>11}" for t in TAGS)
    lines += [header, "-" * len(header)]
    for g, row in s["by_group"].items():
        lines.append(f"{g:<12}{row['count']:>6}" + "".join(f"{row[t]:>10.0f}%" for t in TAGS))
    return "\n".join(lines)


def top_kinds(input_path: str, n: int = 25) -> list[tuple[str, int]]:
    kinds: Counter[str] = Counter()
    for el in read_json(input_path)["elements"]:
        t = el.get("tags", {})
        for k in ("tourism", "historic", "leisure", "natural", "amenity", "shop", "place"):
            if k in t:
                kinds[f"{k}={t[k]}"] += 1
                break
    return kinds.most_common(n)
