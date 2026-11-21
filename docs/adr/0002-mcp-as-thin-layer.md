# ADR 0002: MCP là lớp bọc mỏng quanh `services/`

- Trạng thái: chấp nhận
- Ngày: 2026-11-21

## Quyết định
Logic places/geo/routing/itinerary nằm trong `backend/app/services/`. Module xác định gọi trực tiếp; MCP server chỉ bọc lại cho Claude và client ngoài.

## Lý do
Tránh độ trễ và lỗi giao thức cho các agent không dùng LLM, mà vẫn giữ ranh giới "LLM chỉ chạm dữ liệu qua công cụ có lược đồ".
