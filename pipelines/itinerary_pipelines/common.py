"""Tiện ích dùng chung cho mọi bước pipeline.

Hợp đồng một bước (thiết kế mục 8.1): hàm `run(...) -> StepResult`, tham số tường minh,
đầu ra là file (kèm `*.meta.json`) hoặc MySQL, chạy lại không đổi kết quả.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OSM_LICENSE = "ODbL 1.0 — © OpenStreetMap contributors"


@dataclass
class StepResult:
    step: str
    outputs: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    finished_at: str = field(default_factory=lambda: utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------- file I/O ----------

def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def read_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def write_meta(output_path: str | Path, result: StepResult, **extra: Any) -> Path:
    """Ghi `<output>.meta.json` cạnh file đầu ra."""
    p = Path(output_path)
    return write_json(p.with_name(p.name + ".meta.json"), {**result.to_dict(), **extra})


# ---------- văn bản ----------

def normalize_name(s: str) -> str:
    """Khoá so khớp: chữ thường, bỏ dấu tiếng Việt, đ→d, chỉ giữ chữ-số, gộp khoảng trắng."""
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def clean_display_name(s: str) -> str:
    """Tên hiển thị: chuẩn Unicode NFC, gộp khoảng trắng."""
    return " ".join(unicodedata.normalize("NFC", s).split())


# ---------- địa lý ----------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- cấu hình ----------

def load_dotenv(path: str | Path = ".env") -> None:
    """Nạp biến từ .env nếu có (không ghi đè biến đã đặt). Airflow sẽ tự cấp biến môi trường."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
