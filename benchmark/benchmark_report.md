# 📊 Báo cáo Hiệu năng End-to-End & FinOps Benchmark
**AI-Ready Enterprise Data Platform & Enterprise Hybrid RAG**
*Thời gian đo lường: 2026-11-12 00:06:35*

---

## 1. ⚡ Tốc độ Nhập liệu & Chỉ mục (Ingestion & Indexing)
- **Tổng số chunks chỉ mục:** `11`
- **Thời gian xử lý:** `5.43 giây`
- **Thông lượng (Throughput):** `2.03 chunks/giây`
- **Cơ chế định danh Vector Point:** RFC 4122 UUID5 (Deterministic 100% qua các lần chạy)

---

## 2. 🔍 Hiệu năng Truy xuất Dữ liệu (Retrieval Latency Breakdown)

| Chế độ Tìm kiếm | P50 Latency (ms) | P95 Latency (ms) | Trung bình (ms) | Công nghệ / Thuật toán |
| :--- | :--- | :--- | :--- | :--- |
| **Dense Vector Search** | `91.4` | `115.51` | `98.63` | FastEmbed (`BAAI/bge-small-en-v1.5`, 384 dim) |
| **BM25 Lexical Search** | `0.0` | `5.66` | `1.41` | Standard `rank_bm25.BM25Okapi` (k1=1.5, b=0.75) |
| **Hybrid RRF Search** | `96.43` | `120.52` | `95.68` | Reciprocal Rank Fusion (k=60) + ACL Trimming |

> **Nhận xét kiến trúc:** Tìm kiếm lai (Hybrid RRF) kết hợp hoàn hảo giữa khả năng hiểu ngữ nghĩa (Dense Semantic) và độ chính xác của từ khóa/mã hợp đồng (Okapi BM25) trong khi vẫn đảm bảo độ trễ P95 ở mức tối ưu.

---

## 3. 💰 Hiệu năng Bộ đệm Semantic & Bài toán Chi phí (FinOps SLA)

| Chỉ số | Thực thi Live (Cache Miss) | Bộ đệm Semantic (Cache Hit) | Mức độ Cải thiện |
| :--- | :--- | :--- | :--- |
| **Thời gian phản hồi (Latency)** | `3284.77 ms` | `0.0 ms` | **Nhanh hơn 32847.7x** |
| **Chi phí ước tính / truy vấn** | `$0.0057` | `$0.0` | **Tiết kiệm 100% LLM tokens** |
| **SLA Cam kết** | < 3,500 ms | < 100 ms (P95: `0.0 ms`) | **Đạt chuẩn SLA Enterprise** |

---

## 4. 🛡️ Kiểm chứng Tuân thủ An ninh & Phân quyền (Zero-Trust Security Matrix)
- **Cross-Tenant Leakage Rate:** `0.0%` (Ngăn chặn 100% hành vi đọc chéo tenant)
- **Role & Clearance Escalation Block Rate:** `100.0%` (Chặn toàn bộ truy vấn vượt quyền)
- **SQL AST Injection Defense:** `100.0%` (sqlglot AST chặn stacked queries, comment bypass, union injection)
- **Prompt Injection & Jailbreak Defense:** `100.0%` (Router guardrail nhận diện và chặn các biến thể jailbreak)
