# personalized-itinerary-planner

Hệ thống lập kế hoạch du lịch cá nhân hóa (văn bản/giọng nói tiếng Việt → lịch trình theo ngày). Thiết kế đầy đủ: [docs/design.md](docs/design.md). Quyết định kiến trúc: [docs/adr/](docs/adr/).

## Trạng thái
Giai đoạn 0 (nền tảng): khung repo, Docker Compose (MySQL 8.4, OSRM tùy chọn), lược đồ `TripSpec` kèm test.

## Chạy nhanh
```bash
cp .env.example .env
make up          # MySQL 8.4
make venv        # môi trường Python cho backend
make test        # test lược đồ
```

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
