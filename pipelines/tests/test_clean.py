import json

from itinerary_pipelines import clean
from itinerary_pipelines.clean.dedup import deduplicate
from itinerary_pipelines.clean.normalize import to_record
from itinerary_pipelines.clean.taxonomy import classify
from itinerary_pipelines.common import normalize_name, read_jsonl


def el(id_, tags, lat=12.25, lon=109.19, type_="node"):
    e = {"type": type_, "id": id_, "tags": tags}
    if type_ == "node":
        e.update(lat=lat, lon=lon)
    else:
        e["center"] = {"lat": lat, "lon": lon}
    return e


def rec(*args, **kw):
    r, reason = to_record(el(*args, **kw), "2026-11-21T07:31:19+00:00", "2026-11-21T07:30:06Z")
    assert reason is None, reason
    return r


# ---------- taxonomy ----------

def test_lodging_wins_over_restaurant():
    assert classify({"tourism": "hotel", "amenity": "restaurant"}).group == "luu_tru"


def test_place_of_worship_wins_over_historic():
    assert classify({"amenity": "place_of_worship", "historic": "yes"}).category == "religious"


def test_po_nagar_is_historic():
    c = classify({"historic": "archaeological_site", "religion": "hindu"})
    assert (c.category, c.group) == ("historic", "tham_quan")


def test_unclassified_and_no():
    assert classify({"tourism": "information"}) is None
    assert classify({"historic": "no"}) is None


# ---------- normalize ----------

def test_normalize_name_vietnamese():
    assert normalize_name("  Chùa  Long Sơn ") == "chua long son"
    assert normalize_name("Đầm") == "dam"


def test_drop_reasons():
    def reason(tags):
        return to_record(el(1, tags), None, None)[1]
    assert reason({"amenity": "cafe"}) == "no_name"
    assert reason({"amenity": "cafe", "name": "CF"}) == "generic_name"
    assert reason({"amenity": "cafe", "name": "123"}) == "bad_name"
    assert reason({"tourism": "information", "name": "Bảng tin"}) == "unclassified"


def test_prefers_name_vi_and_way_center():
    r = rec(5, {"name": "Long Son Pagoda", "name:vi": "Chùa Long Sơn",
                "amenity": "place_of_worship"}, type_="way", lat=12.2512, lon=109.1805)
    assert r["name"] == "Chùa Long Sơn" and r["place_id"] == "osm:w5"
    assert (r["lat"], r["lon"]) == (12.2512, 109.1805)


# ---------- dedup ----------

def test_merges_node_and_way_same_place():
    a = rec(1, {"name": "Ventana Hotel", "tourism": "hotel"}, lat=12.2400, lon=109.1950)
    b = rec(2, {"name": "Ventana Hotel", "tourism": "hotel", "website": "https://x.vn",
                "addr:street": "Trần Phú"}, type_="way", lat=12.24005, lon=109.19505)
    out, report = deduplicate([a, b])
    assert len(out) == 1
    assert out[0]["place_id"] == "osm:w2"          # nhiều thẻ hơn
    assert out[0]["merged_from"] == ["osm:n1"]
    assert report["merged_groups"][0]["kept"] == "osm:w2"


def test_merge_fills_missing_fields():
    a = rec(1, {"name": "Chợ Đầm", "amenity": "marketplace", "opening_hours": "05:00-18:00",
                "a": "1", "b": "2"})
    b = rec(2, {"name": "Chợ Đầm", "amenity": "marketplace", "website": "https://cho.vn"},
            lat=12.2501)
    out, _ = deduplicate([a, b])
    assert len(out) == 1
    assert out[0]["opening_hours_raw"] == "05:00-18:00" and out[0]["website"] == "https://cho.vn"


def test_chain_far_apart_not_merged():
    a = rec(1, {"name": "KFC", "amenity": "fast_food"}, lat=12.24)
    b = rec(2, {"name": "KFC", "amenity": "fast_food"}, lat=12.27)
    out, _ = deduplicate([a, b])
    assert len(out) == 2


def test_same_name_different_group_not_merged_but_reported():
    cafe = rec(1, {"name": "Hòn Chồng", "amenity": "cafe"}, lat=12.2700, lon=109.2050)
    sight = rec(2, {"name": "Hòn Chồng", "tourism": "museum"}, lat=12.27015, lon=109.2051)
    out, report = deduplicate([cafe, sight])
    assert len(out) == 2
    assert len(report["review_cross_group_same_name"]) == 1


def test_large_feature_uses_wider_radius():
    a = rec(1, {"name": "Bãi Dài", "natural": "beach"}, lat=12.000, lon=109.200)
    b = rec(2, {"name": "Bãi Dài", "natural": "beach"}, type_="way", lat=12.008, lon=109.200)  # ~890 m
    assert len(deduplicate([a, b])[0]) == 1


def test_fuzzy_names_only_reported():
    a = rec(1, {"name": "Nhà hàng Hải Sản 1", "amenity": "restaurant"}, lat=12.2500)
    b = rec(2, {"name": "Nhà hàng Hải Sản 2", "amenity": "restaurant"}, lat=12.2501)
    out, report = deduplicate([a, b])
    assert len(out) == 2
    assert len(report["review_fuzzy_names"]) == 1


def test_dedup_is_order_independent():
    rs = [rec(i, {"name": "Ventana Hotel", "tourism": "hotel"}, lat=12.24 + i * 1e-5) for i in range(4)]
    out1, _ = deduplicate(rs)
    out2, _ = deduplicate(list(reversed(rs)))
    assert out1 == out2


# ---------- run (file → file) ----------

def test_run_end_to_end(tmp_path):
    raw = {
        "source": "test", "license": "ODbL", "fetched_at": "2026-11-21T07:31:19+00:00",
        "osm_base": "2026-11-21T07:30:06Z",
        "elements": [
            el(1, {"name": "Ventana Hotel", "tourism": "hotel"}),
            el(2, {"name": "Ventana Hotel", "tourism": "hotel", "x": "y"}, type_="way", lat=12.25001),
            el(3, {"amenity": "cafe"}),
            el(4, {"tourism": "information", "name": "Bảng"}),
        ],
    }
    src = tmp_path / "raw.json"
    src.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "places.jsonl"

    r1 = clean.run(str(src), str(out))
    first = out.read_text(encoding="utf-8")
    assert r1.stats["output"] == 1
    assert r1.stats["dropped"] == {"no_name": 1, "unclassified": 1}
    assert (tmp_path / "places.jsonl.meta.json").exists()
    assert (tmp_path / "clean_report.json").exists()
    assert next(iter(read_jsonl(out)))["merged_from"] == ["osm:n1"]

    clean.run(str(src), str(out))
    assert out.read_text(encoding="utf-8") == first  # idempotent
