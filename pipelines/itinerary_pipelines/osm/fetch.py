"""Bước `fetch`: lấy POI từ OpenStreetMap qua Overpass API, lưu file thô.

Dữ liệu © OpenStreetMap contributors, giấy phép ODbL.
Dùng khung toạ độ thay vì ranh giới hành chính vì địa giới đã thay đổi sau
sắp xếp năm 2025; khung mặc định bao cả các đảo trong vịnh Nha Trang.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

from ..common import OSM_LICENSE, StepResult, utc_now, write_json, write_meta

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "itinerary-planner-research/0.1"


AMENITY = (
    "restaurant|cafe|fast_food|bar|pub|food_court|ice_cream|marketplace|"
    "hospital|clinic|pharmacy|atm|bank|bus_station|ferry_terminal|"
    "place_of_worship|theatre|cinema|arts_centre"
)


def build_query(bbox: tuple[float, float, float, float]) -> str:
    b = ",".join(str(x) for x in bbox)
    return f"""
[out:json][timeout:180];
(
  nwr["tourism"]({b});
  nwr["historic"]({b});
  nwr["leisure"~"park|water_park|beach_resort|garden|marina|sports_centre|amusement_arcade"]({b});
  nwr["natural"~"beach|peak|cape|bay|hot_spring"]({b});
  nwr["amenity"~"^({AMENITY})$"]({b});
  nwr["shop"~"^(mall|department_store|seafood|souvenir|gift)$"]({b});
  nwr["place"="island"]({b});
);
out center tags;
"""


def _post(query: str, url: str, retries: int) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                return json.load(resp)
        except Exception as e:  # mạng lỗi / Overpass quá tải (429, 504)
            if attempt == retries:
                raise
            wait = 30 * attempt
            print(f"[fetch] lỗi lần {attempt}: {e}; thử lại sau {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def run(
    out_path: str,
    bbox: tuple[float, float, float, float],
    overpass_url: str = OVERPASS_URL,
    retries: int = 3,
) -> StepResult:
    raw = _post(build_query(bbox), overpass_url, retries)
    payload = {
        "source": "OpenStreetMap via Overpass API",
        "license": OSM_LICENSE,
        "fetched_at": utc_now(),
        "bbox": list(bbox),
        "osm_base": raw.get("osm3s", {}).get("timestamp_osm_base"),
        "elements": raw.get("elements", []),
    }
    write_json(out_path, payload)
    result = StepResult(
        step="fetch",
        outputs=[out_path],
        stats={"elements": len(payload["elements"]), "osm_base": payload["osm_base"]},
    )
    write_meta(out_path, result, source=payload["source"], license=OSM_LICENSE, bbox=list(bbox))
    return result
