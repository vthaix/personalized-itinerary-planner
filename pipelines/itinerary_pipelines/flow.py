"""Luồng pipeline: **nơi duy nhất** khai báo các bước và phụ thuộc giữa chúng.

CLI (`python -m itinerary_pipelines`), Makefile và DAG Airflow sau này đều đọc từ `STEPS`,
nên thêm/sửa một bước chỉ cần sửa ở đây.

    fetch ─┬─ coverage
           └─ clean ─┬─ load ───────────┐
                     └─ survey_export ──┴─ survey_import   (người khảo sát điền CSV ở giữa)

Ví dụ Airflow (Advanced):

    for s in flow.STEPS:
        tasks[s.name] = PythonOperator(task_id=s.name,
                                       python_callable=flow.run_step, op_args=[s.name])
    for s in flow.STEPS:
        for d in s.depends_on:
            tasks[d] >> tasks[s.name]
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .common import StepResult
from .config import PipelineConfig


@dataclass(frozen=True)
class Step:
    name: str
    func: Callable[[PipelineConfig], StepResult]
    depends_on: tuple[str, ...]
    description: str
    human_input: bool = False  # cần người điền dữ liệu trước (Airflow: dùng sensor/trigger tay)


def _fetch(c: PipelineConfig) -> StepResult:
    from .osm import fetch
    return fetch.run(out_path=str(c.raw_path), bbox=c.bbox)


def _coverage(c: PipelineConfig) -> StepResult:
    from .osm import coverage
    r = coverage.run(str(c.raw_path))
    print(coverage.format_report(r))
    return r


def _clean(c: PipelineConfig) -> StepResult:
    from . import clean
    return clean.run(str(c.raw_path), str(c.places_path), str(c.clean_report_path))


def _load(c: PipelineConfig) -> StepResult:
    from .load import mysql
    return mysql.run(str(c.places_path), database_url=c.database_url)


def _survey_export(c: PipelineConfig) -> StepResult:
    from .survey import export
    return export.run(str(c.places_path), str(c.survey_path), str(c.clean_report_path))


def _survey_import(c: PipelineConfig) -> StepResult:
    from .survey import ingest
    return ingest.run(str(c.survey_path), str(c.survey_report_path), database_url=c.database_url)


STEPS: list[Step] = [
    Step("fetch", _fetch, (), "Lấy POI từ OSM qua Overpass API"),
    Step("coverage", _coverage, ("fetch",), "Báo cáo mức phủ thẻ OSM"),
    Step("clean", _clean, ("fetch",), "Chuẩn hoá loại hình, bỏ điểm không tên, gộp trùng"),
    Step("load", _load, ("clean",), "Nạp địa điểm vào MySQL (upsert)"),
    Step("survey_export", _survey_export, ("clean",),
         "Sinh/cập nhật CSV khảo sát tầng 1 (giữ phần đã điền) + danh sách nghi gắn thẻ sai"),
    Step("survey_import", _survey_import, ("load", "survey_export"),
         "Kiểm tra CSV đã điền, nạp bảng place_survey", human_input=True),
]
_BY_NAME = {s.name: s for s in STEPS}


def get(name: str) -> Step:
    if name not in _BY_NAME:
        raise KeyError(f"Không có bước '{name}'. Các bước: {', '.join(_BY_NAME)}")
    return _BY_NAME[name]


def topo_order(names: list[str] | None = None) -> list[str]:
    """Thứ tự chạy hợp lệ. `names=None` → toàn bộ; ngược lại chỉ các bước được chọn
    (không tự kéo theo bước phụ thuộc — đầu vào của chúng phải có sẵn)."""
    selected = set(names) if names is not None else set(_BY_NAME)
    for n in selected:
        get(n)
    order: list[str] = []
    visiting: set[str] = set()

    def visit(n: str) -> None:
        if n in order:
            return
        if n in visiting:
            raise ValueError(f"Phụ thuộc vòng tại '{n}'")
        visiting.add(n)
        for d in get(n).depends_on:
            visit(d)
        visiting.discard(n)
        order.append(n)

    for s in STEPS:  # giữ thứ tự khai báo khi không có ràng buộc
        visit(s.name)
    return [n for n in order if n in selected]


def downstream(start: str) -> list[str]:
    """`start` và mọi bước phụ thuộc (trực tiếp hay gián tiếp) vào nó."""
    get(start)
    result = {start}
    changed = True
    while changed:
        changed = False
        for s in STEPS:
            if s.name not in result and any(d in result for d in s.depends_on):
                result.add(s.name)
                changed = True
    return topo_order(sorted(result))


def run_step(name: str, config: PipelineConfig | None = None) -> StepResult:
    return get(name).func(config or PipelineConfig())


def run_flow(
    config: PipelineConfig | None = None,
    only: list[str] | None = None,
    from_step: str | None = None,
    on_result: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Chạy luồng. Mặc định toàn bộ; `from_step` = bước đó và các bước sau nó;
    `only` = đúng các bước liệt kê."""
    if only and from_step:
        raise ValueError("Chỉ dùng một trong only / from_step")
    names = downstream(from_step) if from_step else topo_order(only)
    cfg = config or PipelineConfig()
    results = []
    for n in names:
        r = run_step(n, cfg)
        results.append(r)
        if on_result:
            on_result(r)
    return results
