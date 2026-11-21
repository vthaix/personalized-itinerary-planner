"""Pipeline chuẩn bị dữ liệu. Mỗi bước là một hàm `run(...)` gọi riêng được.

    from itinerary_pipelines import flow
    flow.run_flow()                         # toàn bộ luồng, cấu hình mặc định (Nha Trang)
    flow.run_step("clean")                  # một bước

hoặc gọi thẳng hàm của từng bước với tham số tường minh:

    from itinerary_pipelines import clean
    clean.run("data/raw/osm_nhatrang.json", "data/processed/places_nhatrang.jsonl")

Danh sách bước và phụ thuộc: xem `flow.STEPS`.
"""

from .common import StepResult

__all__ = ["StepResult"]
