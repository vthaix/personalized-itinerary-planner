-- Khung ban đầu; schema đầy đủ do pipelines/ tạo ở GĐ 1.
-- Lưu ý: MySQL dùng POINT SRID 4326 + SPATIAL INDEX cho không gian,
-- vector embedding lưu BLOB (float32) — xem docs/adr/0004-mysql.md.
SELECT 1;
