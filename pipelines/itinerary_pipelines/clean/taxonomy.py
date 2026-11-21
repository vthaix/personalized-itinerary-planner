"""Chuẩn hoá loại hình: thẻ OSM → (category, group) của hệ thống.

Luật xét theo thứ tự, luật đầu tiên khớp được dùng. Thứ tự có chủ đích:
- Lưu trú đứng trước ăn uống (khách sạn có gắn kèm `amenity=restaurant` vẫn là lưu trú).
- Nơi thờ tự đứng trước di tích (chùa có thẻ `historic` vẫn là `religious`).
Không khớp luật nào → None (bị loại ở bước làm sạch, có ghi vào báo cáo).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    category: str
    group: str


# group: tham_quan | luu_tru | an_uong | mua_sam | tien_ich | giao_thong
_RULES: list[tuple[str, set[str] | None, str, str]] = [
    # (key, values (None = mọi giá trị), category, group)
    ("tourism", {"hotel", "resort", "motel"}, "hotel", "luu_tru"),
    ("tourism", {"guest_house", "hostel", "apartment", "chalet"}, "homestay", "luu_tru"),
    ("tourism", {"camp_site"}, "camp_site", "luu_tru"),
    ("amenity", {"place_of_worship"}, "religious", "tham_quan"),
    ("tourism", {"museum", "gallery"}, "museum", "tham_quan"),
    ("tourism", {"theme_park", "zoo", "aquarium"}, "theme_park", "tham_quan"),
    ("leisure", {"water_park"}, "theme_park", "tham_quan"),
    ("historic", None, "historic", "tham_quan"),
    ("place", {"island"}, "island", "tham_quan"),
    ("natural", {"beach"}, "beach", "tham_quan"),
    ("leisure", {"beach_resort"}, "beach", "tham_quan"),
    ("natural", {"peak", "cape", "bay", "hot_spring"}, "nature", "tham_quan"),
    ("leisure", {"park", "garden"}, "park", "tham_quan"),
    ("leisure", {"marina"}, "marina", "tham_quan"),
    ("tourism", {"viewpoint"}, "viewpoint", "tham_quan"),
    ("tourism", {"attraction", "artwork"}, "attraction", "tham_quan"),
    ("amenity", {"theatre", "cinema", "arts_centre"}, "entertainment", "tham_quan"),
    ("leisure", {"amusement_arcade", "sports_centre"}, "entertainment", "tham_quan"),
    ("amenity", {"restaurant", "food_court"}, "restaurant", "an_uong"),
    ("amenity", {"fast_food"}, "fast_food", "an_uong"),
    ("amenity", {"cafe", "ice_cream"}, "cafe", "an_uong"),
    ("amenity", {"bar", "pub"}, "nightlife", "an_uong"),
    ("amenity", {"marketplace"}, "market", "mua_sam"),
    ("shop", {"mall", "department_store"}, "mall", "mua_sam"),
    ("shop", {"souvenir", "gift"}, "souvenir", "mua_sam"),
    ("shop", {"seafood"}, "seafood_shop", "mua_sam"),
    ("amenity", {"hospital", "clinic"}, "medical", "tien_ich"),
    ("amenity", {"pharmacy"}, "pharmacy", "tien_ich"),
    ("amenity", {"atm", "bank"}, "finance", "tien_ich"),
    ("amenity", {"bus_station"}, "bus_station", "giao_thong"),
    ("amenity", {"ferry_terminal"}, "ferry_terminal", "giao_thong"),
]

GROUPS = sorted({g for *_, g in _RULES})
CATEGORIES = sorted({c for *_, c, _ in _RULES})


def classify(tags: dict[str, str]) -> Category | None:
    for key, values, category, group in _RULES:
        v = tags.get(key)
        if v is None or v == "no":
            continue
        if values is None or v in values:
            return Category(category, group)
    return None
