"""CLI sinh từ `flow.STEPS` — mỗi bước một lệnh, cộng lệnh chạy cả luồng.

    python -m itinerary_pipelines list
    python -m itinerary_pipelines clean                  # một bước
    python -m itinerary_pipelines flow                   # toàn bộ luồng
    python -m itinerary_pipelines flow --from clean      # clean và các bước sau
    python -m itinerary_pipelines flow --only survey_export,survey_import

Tuỳ chọn chung: --city, --data-dir, --database-url.
Mỗi bước in StepResult dạng JSON một dòng (Airflow có thể đọc qua XCom).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import flow
from .common import StepResult, load_dotenv
from .config import PipelineConfig

CITIES = {"nhatrang": PipelineConfig()}


def _print(result: StepResult) -> None:
    print(json.dumps(result.to_dict(), ensure_ascii=False), flush=True)


def _config(args: argparse.Namespace) -> PipelineConfig:
    base = CITIES[args.city]
    return PipelineConfig(city=base.city, bbox=base.bbox, data_dir=Path(args.data_dir),
                          database_url=args.database_url or base.database_url)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--city", default="nhatrang", choices=sorted(CITIES))
    common.add_argument("--data-dir", default="data")
    common.add_argument("--database-url", default=None)

    ap = argparse.ArgumentParser(prog="itinerary_pipelines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="Liệt kê các bước và phụ thuộc")
    for s in flow.STEPS:
        sub.add_parser(s.name, parents=[common], help=s.description)
    p = sub.add_parser("flow", parents=[common], help="Chạy luồng theo thứ tự phụ thuộc")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--from", dest="from_step", choices=[s.name for s in flow.STEPS])
    g.add_argument("--only", default=None, help="danh sách bước, phân tách bằng dấu phẩy")

    args = ap.parse_args(argv)
    if args.cmd == "list":
        for name in flow.topo_order():
            s = flow.get(name)
            dep = ", ".join(s.depends_on) or "—"
            mark = "  [cần người điền dữ liệu]" if s.human_input else ""
            print(f"{s.name:<15} ← {dep:<25} {s.description}{mark}")
        return 0

    cfg = _config(args)
    if args.cmd == "flow":
        only = [x.strip() for x in args.only.split(",")] if args.only else None
        flow.run_flow(cfg, only=only, from_step=args.from_step, on_result=_print)
    else:
        _print(flow.run_step(args.cmd, cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
