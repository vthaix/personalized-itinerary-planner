# personalized-itinerary-planner

Hệ thống lập kế hoạch du lịch cá nhân hóa (văn bản/giọng nói tiếng Việt → lịch trình theo ngày). Thiết kế đầy đủ: [docs/design.md](docs/design.md). Quyết định kiến trúc: [docs/adr/](docs/adr/).

## Trạng thái
- GĐ 0: khung repo, Docker Compose (MySQL 8.4, OSRM tùy chọn), lược đồ `TripSpec` kèm test.
- GĐ 1 (đang làm): pipeline dữ liệu OSM Nha Trang — fetch, coverage, clean, load MySQL.

## Chạy nhanh
```bash
cp .env.example .env
make up              # MySQL 8.4
make venv            # môi trường Python cho backend
make test            # test lược đồ
```

## Pipeline dữ liệu
Package `pipelines/itinerary_pipelines`. Các bước và phụ thuộc khai báo **một lần** trong [`flow.py`](pipelines/itinerary_pipelines/flow.py); CLI, Makefile (và Airflow sau này) đều dùng danh sách đó.

```
fetch ─┬─ coverage
       └─ clean ─┬─ load ───────────┐
                 └─ survey_export ──┴─ survey_import   (người khảo sát điền CSV ở giữa)
```

```bash
make pipelines-venv
make pipeline-list            # xem các bước
make pipeline                 # chạy toàn bộ luồng
make pipeline FROM=clean      # chạy từ một bước trở đi (không gọi lại Overpass)
make step STEP=coverage       # chạy đúng một bước
make survey                   # sinh/cập nhật data/survey/tier1_nhatrang.csv (giữ phần đã điền)
make survey-import            # nạp CSV đã điền vào bảng place_survey
make test-pipelines           # cần DB planner_test
```

```python
from itinerary_pipelines import flow
flow.run_flow()                       # toàn bộ
flow.run_flow(from_step="clean")      # từ clean trở đi
flow.run_step("survey_export")        # một bước
```

### Khảo sát tầng 1
1. `make survey` → mở `data/survey/tier1_nhatrang.csv` bằng Excel/Google Sheets. Dòng xếp theo `priority`; `suggested = y` là gợi ý ban đầu; `flags` là lý do nghi gắn thẻ sai (danh sách riêng ở `*.flagged.csv`).
2. Điền `include` (y/n) và các cột khảo sát. Giờ/giá **bắt buộc** có `source_url` hoặc `source_note` và `surveyed_at`.
3. `make survey-import` → lỗi (nếu có) nằm ở `data/survey/tier1_nhatrang.ingest_report.json`.
4. Chạy lại pipeline bất cứ lúc nào: phần đã điền được giữ nguyên.

## Dựng OSRM (tùy chọn, GĐ 2)
Cần bản trích OSM Việt Nam (`vietnam-latest.osm.pbf` từ Geofabrik, dữ liệu ODbL © OpenStreetMap contributors).
```bash
mkdir -p data/osrm && cp vietnam-latest.osm.pbf data/osrm/vietnam.osm.pbf
docker run --rm -v $PWD/data/osrm:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/vietnam.osm.pbf
docker run --rm -v $PWD/data/osrm:/data osrm/osrm-backend osrm-partition /data/vietnam.osrm
docker run --rm -v $PWD/data/osrm:/data osrm/osrm-backend osrm-customize /data/vietnam.osrm
docker compose --profile routing up -d osrm
```

## Cấu trúc
`backend/` (API, agents, models) · `mcp_servers/` · `pipelines/` · `data/` · `eval/` · `frontend/` · `infra/` · `docs/`
