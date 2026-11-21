# ADR 0004: Dùng MySQL làm CSDL chính

- Trạng thái: chấp nhận
- Ngày: 2026-11-21

## Quyết định
MySQL 8.4 là nguồn dữ liệu chuẩn (thay cho PostgreSQL + PostGIS + pgvector ở bản thiết kế 0.3).

## Hệ quả và cách bù
| Nhu cầu | Cách làm với MySQL |
|---|---|
| Truy vấn không gian | Cột `POINT SRID 4326` + `SPATIAL INDEX`; lọc khung bao bằng `MBRContains`, đo khoảng cách bằng `ST_Distance_Sphere` |
| Tìm kiếm vector | MySQL Community không có tìm kiếm vector sẵn dùng; lưu BLOB float32 trong `place_embedding`, nạp vào bộ nhớ, cosine bằng NumPy. Qdrant nếu dữ liệu lớn |
| So khớp mờ tên địa danh | `rapidfuzz` trên gazetteer trong bộ nhớ (không có `pg_trgm`) |
| Giờ mở cửa | Cột `JSON` |
| Checkpoint LangGraph | SQLite (có checkpointer chính thức) cho Core; MySQL cần gói cộng đồng hoặc tự viết — quyết định ở GĐ 4 |

## Cần kiểm chứng
- Hiệu năng quét vector trong bộ nhớ trên dữ liệu thật (dự kiến vài nghìn địa điểm).

## Đã kiểm chứng (MySQL 8.4.11, 2026-11-21)
Thứ tự trục của SRID 4326 dễ nhầm. Trên bản chạy thử:
- `ST_SRID(POINT(lon, lat), 4326)`: hàm `POINT()` nhận **(lon, lat)**; truyền (lat, lon) bị lỗi 3732 "latitude out of range".
- `ST_GeomFromText('POINT(lat lon)', 4326)`: WKT theo trục của SRID, tức **(lat lon)**.
- Điểm lưu ra có `ST_X` = lat, `ST_Y` = lon, `ST_AsText` in `POINT(lat lon)`.
- Hai cách tạo điểm cho cùng khoảng cách `ST_Distance_Sphere` (1296 m cho cặp điểm thử gần Nha Trang).

Quy ước của repo: tạo điểm bằng `ST_SRID(POINT(lon, lat), 4326)`, đọc lat/lon bằng `ST_Latitude`/`ST_Longitude`, không dùng `ST_X`/`ST_Y` trực tiếp. Có test nạp và đọc lại toạ độ ở GĐ 1.
