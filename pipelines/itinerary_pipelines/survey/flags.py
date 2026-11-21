"""Phát hiện địa điểm nghi gắn thẻ sai và chấm điểm ưu tiên khảo sát.

Các luật ở đây chỉ **gợi ý** để người khảo sát xem trước; không tự sửa hay loại dữ liệu.
Luật được rút ra từ lỗi thật trong dữ liệu Nha Trang ("GAS station", "Showroom" gắn là bảo tàng…).
"""

from __future__ import annotations

import re

# Cụm từ (đã bỏ dấu) cho thấy đây là cơ sở kinh doanh/dịch vụ, không phải điểm tham quan
_SERVICE_PHRASES = [
    "dive", "diving", "tour", "tours", "travel", "rental", "rent", "agency", "office",
    "cong ty", "cty", "spa", "massage", "showroom", "store", "shop", "cua hang",
    "station", "gas", "xang dau", "motobikes", "motorbikes", "photo studio",
]
# Cụm từ cho thấy là quán ăn/lưu trú (không dùng "quan" đơn lẻ vì trùng "Quan Âm")
_FOOD_LODGING_PHRASES = [
    "cafe", "coffee", "ca phe", "restaurant", "nha hang", "quan an", "quan com", "quan nhau",
    "hotel", "khach san", "homestay", "hostel", "resort", "villa",
]
_MUSEUM_WORDS = ["bao tang", "museum", "gallery", "trien lam", "nha trung bay", "exhibition", "aquarium"]
_GENERIC_NAMES = {"nha trang", "beach", "bai bien", "park", "cong vien", "museum", "bao tang",
                  "temple", "pagoda", "chua", "church", "nha tho", "statue", "tuong"}

# Đối tượng nhỏ (tượng, bia, máy bay trưng bày…): không sai, nhưng ít khi là điểm đến riêng
_MINOR_TAGS = {
    ("tourism", "artwork"), ("historic", "memorial"), ("historic", "wayside_shrine"),
    ("historic", "wayside_cross"), ("historic", "boundary_stone"), ("historic", "aircraft"),
    ("historic", "tank"), ("historic", "cannon"), ("historic", "monument"),
}

_CATEGORY_BASE = {
    "island": 6, "beach": 6, "theme_park": 6, "museum": 5, "nature": 4, "historic": 4,
    "viewpoint": 4, "religious": 3, "attraction": 3, "park": 2, "marina": 2, "entertainment": 2,
}


def _has_phrase(name_norm: str, phrases: list[str]) -> str | None:
    for p in phrases:
        if re.search(rf"(^| ){re.escape(p)}( |$)", name_norm):
            return p
    return None


def detect_flags(place: dict, cross_group_ids: set[str] | None = None) -> list[str]:
    """Danh sách cờ nghi vấn, dạng 'mã:chi tiết'."""
    flags: list[str] = []
    n = place["name_norm"]
    cat = place["category"]

    if n in _GENERIC_NAMES:
        flags.append("generic_name")
    if (p := _has_phrase(n, _SERVICE_PHRASES)) and cat != "entertainment":
        flags.append(f"name_suggests_service:{p}")
    elif p and cat == "entertainment":
        flags.append(f"likely_service_business:{p}")
    if (p := _has_phrase(n, _FOOD_LODGING_PHRASES)) and place["group"] == "tham_quan":
        flags.append(f"name_suggests_food_or_lodging:{p}")
    if cat == "museum" and not place.get("wikipedia") and not _has_phrase(n, _MUSEUM_WORDS):
        flags.append("museum_name_mismatch")
    if cross_group_ids and place["place_id"] in cross_group_ids:
        flags.append("same_name_other_category_nearby")
    return flags


def is_minor(place: dict) -> bool:
    tags = place.get("osm_tags", {})
    return any(tags.get(k) == v for k, v in _MINOR_TAGS)


def priority(place: dict, flags: list[str]) -> int:
    s = _CATEGORY_BASE.get(place["category"], 1)
    if place.get("wikipedia") or place.get("wikidata"):
        s += 3
    if place.get("name_en"):
        s += 1
    if place.get("website"):
        s += 1
    if place.get("opening_hours_raw"):
        s += 1
    if is_minor(place):
        s -= 3
    if flags:
        s -= 4
    return s
