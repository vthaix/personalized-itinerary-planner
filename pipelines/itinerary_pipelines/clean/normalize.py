"""Chuyển phần tử OSM thô thành bản ghi địa điểm chuẩn hoá (hoặc lý do loại bỏ)."""

from __future__ import annotations

from typing import Any

from ..common import OSM_LICENSE, clean_display_name, normalize_name
from .taxonomy import classify

_TYPE_CODE = {"node": "n", "way": "w", "relation": "r"}

# Tên không mang thông tin địa điểm (sau normalize_name)
GENERIC_NAMES = {"cf", "cafe", "coffee", "ca phe", "com", "pho", "atm", "wc", "toilet",
                 "nha hang", "quan an", "khach san", "hotel", "parking"}


def place_id(el: dict) -> str:
    return f"osm:{_TYPE_CODE[el['type']]}{el['id']}"


def coords(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c and "lat" in c and "lon" in c:
        return c["lat"], c["lon"]
    return None


def _first(tags: dict, *keys: str) -> str | None:
    for k in keys:
        v = tags.get(k)
        if v and v.strip():
            return v.strip()
    return None


def _address(tags: dict) -> str | None:
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"),
             tags.get("addr:subdistrict") or tags.get("addr:ward"),
             tags.get("addr:city")]
    s = ", ".join(p.strip() for p in parts if p and p.strip())
    return s or _first(tags, "addr:full")


def to_record(el: dict, fetched_at: str | None, osm_base: str | None) -> tuple[dict | None, str | None]:
    """Trả (bản ghi, None) nếu giữ, hoặc (None, lý do) nếu loại."""
    tags: dict[str, str] = el.get("tags", {})
    if el.get("type") not in _TYPE_CODE:
        return None, "unsupported_type"

    raw_name = _first(tags, "name:vi", "name")
    if not raw_name:
        return None, "no_name"
    name = clean_display_name(raw_name)
    name_norm = normalize_name(name)
    if len(name_norm) < 2 or name_norm.replace(" ", "").isdigit():
        return None, "bad_name"
    if name_norm in GENERIC_NAMES:
        return None, "generic_name"

    cat = classify(tags)
    if cat is None:
        return None, "unclassified"

    ll = coords(el)
    if ll is None:
        return None, "no_coords"

    record: dict[str, Any] = {
        "place_id": place_id(el),
        "osm_type": el["type"],
        "osm_id": el["id"],
        "name": name,
        "name_en": _first(tags, "name:en"),
        "name_norm": name_norm,
        "category": cat.category,
        "group": cat.group,
        "lat": round(ll[0], 7),
        "lon": round(ll[1], 7),
        "address": _address(tags),
        "opening_hours_raw": _first(tags, "opening_hours"),
        "website": _first(tags, "website", "contact:website", "url"),
        "phone": _first(tags, "phone", "contact:phone"),
        "wikidata": _first(tags, "wikidata"),
        "wikipedia": _first(tags, "wikipedia"),
        "wikimedia_commons": _first(tags, "wikimedia_commons"),
        "osm_tags": tags,
        "source": "osm",
        "license": OSM_LICENSE,
        "fetched_at": fetched_at,
        "osm_base": osm_base,
        "merged_from": [],
    }
    return record, None
