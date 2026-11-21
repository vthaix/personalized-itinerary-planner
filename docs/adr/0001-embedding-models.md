# ADR 0001: Mô hình embedding

- Trạng thái: chấp nhận (có điều kiện thực nghiệm)
- Ngày: 2026-11-21

## Quyết định
- Chính: `AITeamVN/Vietnamese_Embedding`
- Baseline: `BAAI/bge-m3`
- Đối chứng: `multilingual-e5-large-instruct`

## Bối cảnh
Semantic search cần embedding hiểu tiếng Việt. Chạy cục bộ, vì Claude API không cung cấp embedding.

## Hệ quả
- Mỗi mô hình có bảng vector và chỉ mục riêng; lớp `Embedder` chọn qua `EMBEDDING_MODEL`.
- GĐ 2 so sánh ba mô hình trên bộ eval; nếu mô hình chính kém baseline thì đổi, ghi ADR mới.
- Chưa xác nhận chiều vector và độ dài ngữ cảnh: đọc model card khi cài đặt.
