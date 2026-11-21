"""Cấu hình pipeline: một chỗ duy nhất quyết định đường dẫn file và vùng dữ liệu.

Mở rộng sang thành phố khác = tạo PipelineConfig mới (city, bbox); các bước không đổi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

NHA_TRANG_BBOX: tuple[float, float, float, float] = (12.10, 109.08, 12.38, 109.38)


@dataclass(frozen=True)
class PipelineConfig:
    city: str = "nhatrang"
    bbox: tuple[float, float, float, float] = NHA_TRANG_BBOX
    data_dir: Path = Path("data")
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL"))

    # ---- file trung gian giữa các bước ----
    @property
    def raw_path(self) -> Path:
        return self.data_dir / "raw" / f"osm_{self.city}.json"

    @property
    def places_path(self) -> Path:
        return self.data_dir / "processed" / f"places_{self.city}.jsonl"

    @property
    def clean_report_path(self) -> Path:
        return self.data_dir / "processed" / f"clean_report_{self.city}.json"

    # survey/ chứa công sức nhập tay → nên commit vào git (không nằm trong .gitignore)
    @property
    def survey_path(self) -> Path:
        return self.data_dir / "survey" / f"tier1_{self.city}.csv"

    @property
    def survey_report_path(self) -> Path:
        return self.data_dir / "survey" / f"tier1_{self.city}.ingest_report.json"
