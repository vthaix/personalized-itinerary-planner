# ADR 0003: Điều phối pipeline dữ liệu bằng Makefile, Airflow để Advanced

- Trạng thái: chấp nhận
- Ngày: 2026-11-21

## Quyết định
Core: các bước trong `pipelines/` là script idempotent, chạy qua `make`. Airflow chỉ bọc các hàm đó thành DAG nếu cần cập nhật định kỳ hoặc mở rộng nhiều thành phố.

## Lý do
Dữ liệu một thành phố gần như tĩnh; Airflow tốn công cấu hình (scheduler, webserver, metadata DB) mà lợi ích nhỏ.
