"""Gộp bản ghi trùng.

Chỉ tự động gộp khi **cùng tên chuẩn hoá + cùng nhóm loại hình + trong bán kính** theo loại.
Lý do (từ dữ liệu Nha Trang thật):
- Chuỗi cửa hàng (KFC, Highlands…) cùng tên nhưng cách xa nhau → không gộp nhờ bán kính.
- Cùng tên, gần nhau nhưng khác nhóm (quán cà phê "Hòn Chồng" cạnh điểm tham quan Hòn Chồng,
  bến tàu và khách sạn "Ninh Vân Bay") là các địa điểm khác nhau → không gộp, chỉ báo cáo.
- Tên gần giống (so khớp mờ) dễ gộp nhầm ("Nhà hàng Hải sản 1" / "… 2") → không gộp, chỉ báo cáo.
"""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from ..common import haversine_m

# Bán kính gộp (m) theo category; địa điểm diện rộng có tâm lệch nhiều giữa bản điểm và bản vùng
MERGE_RADIUS_M: dict[str, float] = {
    "beach": 1500, "island": 1500, "nature": 1000, "park": 500, "theme_park": 800,
    "religious": 300, "historic": 300, "museum": 300, "attraction": 300,
    "viewpoint": 200, "marina": 500, "entertainment": 200, "market": 300, "mall": 300,
    "hotel": 200, "homestay": 150, "camp_site": 300,
}
DEFAULT_RADIUS_M = 100.0
REVIEW_RADIUS_M = 150.0
FUZZY_THRESHOLD = 0.85

_TYPE_RANK = {"relation": 2, "way": 1, "node": 0}
_FILL_FIELDS = ("name_en", "address", "opening_hours_raw", "website", "phone",
                "wikidata", "wikipedia", "wikimedia_commons")


class _DSU:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _radius(r: dict) -> float:
    return MERGE_RADIUS_M.get(r["category"], DEFAULT_RADIUS_M)


def _dist(a: dict, b: dict) -> float:
    return haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])


def _primary_key(r: dict) -> tuple:
    # nhiều thẻ hơn → giàu thông tin hơn; ưu tiên vùng (way/relation) hơn điểm; cuối cùng ổn định theo id
    return (-len(r["osm_tags"]), -_TYPE_RANK[r["osm_type"]], r["place_id"])


def _merge(cluster: list[dict]) -> dict:
    cluster = sorted(cluster, key=_primary_key)
    primary = dict(cluster[0])
    tags = dict(primary["osm_tags"])
    for other in cluster[1:]:
        for f in _FILL_FIELDS:
            if not primary.get(f) and other.get(f):
                primary[f] = other[f]
        for k, v in other["osm_tags"].items():
            tags.setdefault(k, v)
    primary["osm_tags"] = tags
    primary["merged_from"] = sorted(r["place_id"] for r in cluster[1:])
    return primary


def deduplicate(records: list[dict]) -> tuple[list[dict], dict]:
    """Trả (bản ghi sau gộp, báo cáo). Kết quả xác định (không phụ thuộc thứ tự đầu vào)."""
    recs = sorted(records, key=lambda r: r["place_id"])
    dsu = _DSU(len(recs))

    by_name: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(recs):
        by_name[r["name_norm"]].append(i)

    cross_group: list[dict] = []
    for idxs in by_name.values():
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                a, b = recs[idxs[x]], recs[idxs[y]]
                d = _dist(a, b)
                if a["group"] == b["group"]:
                    if d <= max(_radius(a), _radius(b)):
                        dsu.union(idxs[x], idxs[y])
                elif d <= REVIEW_RADIUS_M:
                    cross_group.append(_pair(a, b, d))

    # Tên gần giống, cùng nhóm, rất gần nhau → chỉ báo cáo để duyệt tay
    fuzzy: list[dict] = []
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_group[r["group"]].append(r)
    deg = REVIEW_RADIUS_M / 111_000 * 1.5  # loại nhanh theo khung toạ độ
    for items in by_group.values():
        items.sort(key=lambda r: r["lat"])
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if b["lat"] - a["lat"] > deg:
                    break
                if abs(b["lon"] - a["lon"]) > deg or a["name_norm"] == b["name_norm"]:
                    continue
                ratio = SequenceMatcher(None, a["name_norm"], b["name_norm"]).ratio()
                if ratio >= FUZZY_THRESHOLD and (d := _dist(a, b)) <= REVIEW_RADIUS_M:
                    fuzzy.append({**_pair(a, b, d), "similarity": round(ratio, 3)})

    clusters: dict[int, list[dict]] = defaultdict(list)
    for i, r in enumerate(recs):
        clusters[dsu.find(i)].append(r)

    out: list[dict] = []
    merged_groups: list[dict] = []
    for members in clusters.values():
        if len(members) == 1:
            out.append(members[0])
            continue
        m = _merge(members)
        out.append(m)
        merged_groups.append({"kept": m["place_id"], "name": m["name"], "category": m["category"],
                              "merged": m["merged_from"]})

    out.sort(key=lambda r: r["place_id"])
    report = {
        "merged_groups": sorted(merged_groups, key=lambda g: g["kept"]),
        "review_cross_group_same_name": cross_group,
        "review_fuzzy_names": fuzzy,
    }
    return out, report


def _pair(a: dict, b: dict, d: float) -> dict:
    return {"a": a["place_id"], "a_name": a["name"], "a_category": a["category"],
            "b": b["place_id"], "b_name": b["name"], "b_category": b["category"],
            "distance_m": round(d, 1)}
