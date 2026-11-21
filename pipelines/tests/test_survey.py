import csv
import json

from itinerary_pipelines.common import write_jsonl
from itinerary_pipelines.survey import export
from itinerary_pipelines.survey.flags import detect_flags, priority
from itinerary_pipelines.survey.ingest import validate_row


def place(pid, name, category, group="tham_quan", **kw):
    from itinerary_pipelines.common import normalize_name
    return {"place_id": pid, "name": name, "name_norm": normalize_name(name), "name_en": None,
            "category": category, "group": group, "lat": 12.25, "lon": 109.19,
            "osm_tags": kw.pop("osm_tags", {}), "wikipedia": None, "wikidata": None,
            "website": None, "opening_hours_raw": None, **kw}


# ---------- flags ----------

def test_flags_from_real_mistags():
    assert detect_flags(place("osm:n1", "GAS station", "museum")) == [
        "name_suggests_service:station", "museum_name_mismatch"]
    assert "name_suggests_service:showroom" in detect_flags(place("osm:n2", "Showroom", "museum"))
    assert "generic_name" in detect_flags(place("osm:n3", "Nha Trang", "beach"))


def test_quan_am_not_flagged_as_food():
    assert detect_flags(place("osm:n1", "Chùa Quan Âm", "religious")) == []


def test_real_museum_not_flagged():
    assert detect_flags(place("osm:n1", "Bảo tàng Hải dương học Nha Trang", "museum")) == []


def test_dive_center_marked_service_business():
    assert detect_flags(place("osm:n1", "Rainbow Divers dive center", "entertainment")) == [
        "likely_service_business:dive"]


def test_cross_group_flag():
    assert detect_flags(place("osm:n1", "Hòn Chồng", "museum", wikipedia="vi:x"), {"osm:n1"}) == [
        "same_name_other_category_nearby"]


def test_priority_order():
    po_nagar = place("osm:w1", "Tháp Po Nagar", "historic", wikipedia="vi:Tháp Po Nagar",
                     name_en="Po Nagar")
    statue = place("osm:n2", "MiG-21", "historic", osm_tags={"historic": "aircraft"})
    assert priority(po_nagar, []) > priority(statue, [])


# ---------- export ----------

def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_export_preserves_manual_columns_and_marks_stale(tmp_path):
    places = tmp_path / "places.jsonl"
    out = tmp_path / "survey" / "tier1.csv"
    write_jsonl(places, [
        place("osm:w1", "Tháp Po Nagar", "historic", wikipedia="vi:Tháp Po Nagar"),
        place("osm:n2", "GAS station", "museum"),
        place("osm:n3", "Quán A", "restaurant", group="an_uong"),
    ])
    r = export.run(str(places), str(out))
    rows = _read(out)
    assert [x["place_id"] for x in rows] == ["osm:w1", "osm:n2"]   # chỉ tham_quan, ưu tiên cao trước
    assert rows[0]["suggested"] == "y" and rows[1]["suggested"] == ""
    assert r.stats["flagged"] == 1
    assert [x["place_id"] for x in _read(tmp_path / "survey" / "tier1.flagged.csv")] == ["osm:n2"]

    # người khảo sát điền
    rows[0].update(include="y", intensity="2", description_vi="Tháp Chăm cổ.")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=export.COLUMNS)
        w.writeheader()
        w.writerows(rows)

    # dữ liệu nguồn đổi: n2 biến mất
    write_jsonl(places, [place("osm:w1", "Tháp Po Nagar", "historic", wikipedia="vi:Tháp Po Nagar")])
    r2 = export.run(str(places), str(out))
    rows2 = {x["place_id"]: x for x in _read(out)}
    assert rows2["osm:w1"]["intensity"] == "2"
    assert rows2["osm:w1"]["description_vi"] == "Tháp Chăm cổ."
    assert rows2["osm:n2"]["status"] == "stale"
    assert r2.stats["rows_with_manual_data_preserved"] == 1


def test_export_writes_meta(tmp_path):
    places = tmp_path / "p.jsonl"
    write_jsonl(places, [place("osm:w1", "Hòn Mun", "island")])
    export.run(str(places), str(tmp_path / "t.csv"))
    meta = json.loads((tmp_path / "t.csv.meta.json").read_text(encoding="utf-8"))
    assert meta["step"] == "survey_export" and meta["stats"]["rows"] == 1


# ---------- ingest validation ----------

BASE = {"place_id": "osm:w1", "status": "active"}


def test_undecided_rows_skipped():
    assert validate_row({**BASE, "include": ""}) == (None, [])


def test_excluded_row_kept_minimal():
    assert validate_row({**BASE, "include": "n"}) == ({"place_id": "osm:w1", "include": 0}, [])


def test_valid_full_row():
    rec, errs = validate_row({**BASE, "include": "y", "opening_hours": "Mo-Su 06:00-17:30",
                              "price_adult_vnd": "30.000", "intensity": "2",
                              "typical_duration_min": "60", "kid_friendly": "y",
                              "source_url": "https://example.vn/po-nagar",
                              "surveyed_at": "2026-11-25"})
    assert errs == []
    assert rec["price_adult_vnd"] == 30000 and rec["intensity"] == 2 and rec["kid_friendly"] == 1


def test_price_requires_source():
    _, errs = validate_row({**BASE, "include": "y", "price_adult_vnd": "30000",
                            "surveyed_at": "2026-11-25"})
    assert any("source_url" in e for e in errs)


def test_fact_requires_surveyed_at():
    _, errs = validate_row({**BASE, "include": "y", "intensity": "2"})
    assert any("surveyed_at" in e for e in errs)


def test_invalid_values_collected():
    rec, errs = validate_row({**BASE, "include": "y", "intensity": "5", "kid_friendly": "có",
                              "category_fix": "zzz", "opening_hours": "sáng",
                              "source_url": "example.vn", "surveyed_at": "25/11/2026"})
    assert rec is None and len(errs) == 6


def test_stale_row_cannot_be_included():
    _, errs = validate_row({**BASE, "status": "stale", "include": "y"})
    assert any("stale" in e for e in errs)
