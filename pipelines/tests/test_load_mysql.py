"""Integration test với MySQL thật. Bỏ qua nếu không có TEST_DATABASE_URL.

    TEST_DATABASE_URL=mysql+pymysql://planner:planner@localhost:3306/planner_test pytest
"""

import os

import pytest

from itinerary_pipelines.common import write_jsonl
from itinerary_pipelines.load import mysql

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="cần TEST_DATABASE_URL")


def place(pid, name, lat, lon, **kw):
    return {"place_id": pid, "source": "osm", "osm_type": "node", "osm_id": int(pid[5:]),
            "name": name, "name_en": None, "name_norm": name.lower(), "category": "beach",
            "group": "tham_quan", "lat": lat, "lon": lon, "osm_tags": {"name": name},
            "merged_from": [], "license": "ODbL", "fetched_at": "2026-11-21T07:31:19+00:00",
            "osm_base": "2026-11-21T07:30:06Z", **kw}


@pytest.fixture
def conn():
    c = mysql.connect(URL)
    with c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS place_survey")
        cur.execute("DROP TABLE IF EXISTS place")
    c.commit()
    yield c
    c.close()


def test_load_upsert_deactivate_and_coords(tmp_path, conn):
    f = tmp_path / "p.jsonl"
    write_jsonl(f, [place("osm:n1", "Hòn Chồng", 12.2700, 109.2050),
                    place("osm:n2", "Bãi Dài", 12.0500, 109.2000)])
    r1 = mysql.run(str(f), database_url=URL)
    assert (r1.stats["inserted"], r1.stats["active"]) == (2, 2)

    # lần 2: n1 đổi tên, n2 biến mất, n3 mới
    write_jsonl(f, [place("osm:n1", "Hòn Chồng (mới)", 12.2700, 109.2050),
                    place("osm:n3", "Hòn Tằm", 12.1800, 109.2400)])
    r2 = mysql.run(str(f), database_url=URL)
    assert r2.stats["inserted"] == 1 and r2.stats["updated"] == 1 and r2.stats["deactivated"] == 1

    with conn.cursor() as cur:
        cur.execute("SELECT place_id, name, is_active, ST_Latitude(location), ST_Longitude(location) "
                    "FROM place ORDER BY place_id")
        rows = cur.fetchall()
    assert [(r[0], r[2]) for r in rows] == [("osm:n1", 1), ("osm:n2", 0), ("osm:n3", 1)]
    assert rows[0][1] == "Hòn Chồng (mới)"
    assert (round(rows[0][3], 4), round(rows[0][4], 4)) == (12.27, 109.205)  # đúng trục lat/lon


def test_spatial_radius_query(tmp_path, conn):
    f = tmp_path / "p.jsonl"
    write_jsonl(f, [place("osm:n1", "Gần", 12.2400, 109.1960),
                    place("osm:n2", "Xa", 12.3000, 109.1960)])
    mysql.run(str(f), database_url=URL)
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM place WHERE ST_Distance_Sphere(location, "
                    "ST_SRID(POINT(%s, %s), 4326)) <= %s", (109.1950, 12.2388, 3000))
        assert [r[0] for r in cur.fetchall()] == ["Gần"]


def test_refuses_empty_input(tmp_path):
    f = tmp_path / "empty.jsonl"
    write_jsonl(f, [])
    with pytest.raises(RuntimeError):
        mysql.run(str(f), database_url=URL)


def test_survey_import_roundtrip(tmp_path, conn):
    import csv

    from itinerary_pipelines.survey import export, ingest

    places = tmp_path / "p.jsonl"
    write_jsonl(places, [place("osm:n1", "Hòn Chồng", 12.27, 109.205),
                         place("osm:n2", "Bãi Dài", 12.05, 109.20)])
    mysql.run(str(places), database_url=URL)
    survey = tmp_path / "s.csv"
    export.run(str(places), str(survey))

    with open(survey, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["place_id"] == "osm:n1":
            r.update(include="y", intensity="1", price_adult_vnd="22000", source_note="hỏi tại quầy",
                     surveyed_at="2026-11-25")
        else:
            r.update(include="y", intensity="9")  # lỗi
    with open(survey, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=export.COLUMNS)
        w.writeheader()
        w.writerows(rows)

    report = tmp_path / "r.json"
    r1 = ingest.run(str(survey), str(report), database_url=URL)
    assert (r1.stats["loaded"], r1.stats["errors"]) == (1, 1)
    r2 = ingest.run(str(survey), str(report), database_url=URL)  # idempotent
    assert r2.stats == r1.stats
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, intensity, price_adult_vnd FROM place_survey")
        assert cur.fetchall() == (("osm:n1", 1, 22000),)

    with pytest.raises(ValueError):
        ingest.run(str(survey), str(report), database_url=URL, strict=True)
