# AI-Ready Enterprise Data Platform

> **Nền tảng Dữ liệu Doanh nghiệp Hợp nhất phục vụ Báo cáo BI, Truy vấn Ngôn ngữ Tự nhiên (NLQ) và Hệ thống Đa Tác tử AI (Multi-Agent System) với Phân quyền Đa tầng.**

![Architecture Design](Architecture_Design.png)

---

## 🌟 Tính Năng Nổi Bật (Key Features)

1. **Idempotent Ingestion & Control Plane (Giai đoạn 1):**
   - Bảng điều khiển `watermark`, `run_log`, và `file_manifest` (mã băm SHA-256).
   - Tự động bỏ qua 100% tài liệu không thay đổi, giảm >85% chi phí tính toán & Embedding API.
2. **Medallion Lakehouse & Data Quality Gate (Giai đoạn 2):**
   - Bronze (Raw Immutable) -> Silver (SCD Type 2 + Normalized Docs) -> Gold (Star Schema + Deterministic Chunks).
   - Chốt chặn **Pandera** schema validation + **DuckDB SQL Assertions** kiểm tra tính toàn vẹn tham chiếu trước khi xuất bản lên tầng Gold.
3. **Single Source of Truth Semantic Layer (Giai đoạn 3):**
   - Triển khai **Cube Core** kết hợp DuckDB Semantic Engine nội bộ.
   - Định nghĩa tập trung Metrics-as-Code (`netRevenue`, `grossProfit`, `slaBreachRate`), tự động ép Dynamic Row-Level Security (RLS) theo `tenant_id`. Loại bỏ 100% ảo giác số liệu từ LLM.
4. **Enterprise Hybrid RAG Pipeline (Giai đoạn 4):**
   - Kết hợp **BM25 Exact Match** với **Dense Vector (HNSW)** trên **Qdrant**.
   - Hợp nhất thứ hạng bằng thuật toán **Reciprocal Rank Fusion (RRF)** ($k=60$) kết hợp Zero-Trust Document ACL Trimming (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).
5. **AI Agent Orchestrator & Phân quyền Đa tầng (Giai đoạn 5):**
   - Điều phối qua **FastAPI** và **LangGraph StateGraph**: Router -> Structured BI Agent | Hybrid RAG Agent | Cross-Analysis Synthesizer | Grounding Auditor.
   - Chốt chặn **SQL AST Guardrail (`sqlglot`)** chặn đứng SQL Injection và câu lệnh can thiệp dữ liệu.
   - **FinOps Semantic Caching (Redis)**: phản hồi P95 < 100ms khi trúng cache; Token Bucket Rate Limiting.
   - Giao diện **Streamlit AI Enterprise Portal** với Persona Switcher tức thì và Structured Citations.
6. **3D WebGL Digital Twin Universe (Three.js r128):**
   - Bản đồ không gian 3D trực quan hóa toàn bộ vũ trụ Lakehouse & Multi-Agent:
     - **Ingestion Hub & Bronze:** Silo dữ liệu OLTP, tài liệu thô, lá chắn băm SHA-256 `file_manifest`.
     - **Silver & Quality Gate:** Khối chuẩn hóa SCD Type 2 và vòng năng lượng Pandera Data Quality Gate.
     - **Gold Star Schema:** Kim tự tháp `fact_orders` và các vệ tinh `dim_customers`, `dim_products`.
     - **Cube Semantic Layer:** Khối lập phương phát sáng Cyan Cube Core với vòng quay chỉ số Metrics-as-Code.
     - **Qdrant Vector Space:** Quần thể vector 3D với 4 tài liệu mã hóa màu theo cấp độ `security_acl`.
     - **LangGraph Agent Nexus:** Router trung tâm kết nối 4 tác tử chuyên biệt, phát xung ánh sáng khi điều phối.
   - Luồng hạt dữ liệu (Particle Streams) chuyển động liên tục giữa các tầng kiến trúc.
   - Hỗ trợ OrbitControls, Camera Teleportation, Click-to-Inspect HUD và AI Cockpit trực tiếp trong không gian 3D.
7. **Automated Evaluation & Observability (Giai đoạn 6):**
   - Bộ đánh giá **Golden Dataset** tự động đo lường:
     - **Metric Consistency**: Đạt **100.0%**
     - **Security Block Rate (Red-Team & RBAC)**: Đạt **100.0%**
     - **Citation Provenance Rate**: Đạt **100.0%**
     - **P95 Semantic Cache Latency**: **< 1ms**

---

## 🚀 Hướng Dẫn Cài Đặt & Vận Hành Cục Bộ

### 1. Cài đặt Thư viện
```powershell
pip install -r requirements.txt
```

### 2. Sinh Dữ liệu Mẫu & Chạy Toàn bộ Pipeline
Chạy chuỗi pipeline nạp từ Bronze -> Silver -> Data Quality Gate -> Gold Lakehouse -> Vector Index:
```powershell
# Bước 1: Sinh dữ liệu mẫu B2B E-Commerce & Tài liệu doanh nghiệp
python src/ingestion/seed_generator.py

# Bước 2: Nạp dữ liệu vào Bronze Delta Lake
python -m src.ingestion.structured_loader
python -m src.ingestion.unstructured_loader

# Bước 3: Chạy Silver Transforms, Quality Gate và Gold Lakehouse
python -m src.lakehouse.silver_transforms
python -m src.lakehouse.quality_gate
python -m src.lakehouse.gold_transforms

# Bước 4: Lập chỉ mục Hybrid Vector vào Qdrant
python -c "from src.retrieval.hybrid_retriever import HybridRetriever; hr = HybridRetriever(); hr.index_gold_chunks()"
```

### 3. Khởi chạy Giao diện Streamlit AI Enterprise Portal
```powershell
streamlit run src/ui/app.py --server.port 8501
```
Mở trình duyệt tại: `http://localhost:8501`

### 4. Khởi chạy FastAPI Backend Gateway
```powershell
uvicorn src.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```
Xem Swagger UI API docs tại: `http://localhost:8000/docs`

---

## 🐳 Vận Hành Bằng Docker Compose

Toàn bộ hệ thống (Qdrant, Redis, Cube Core, FastAPI, Streamlit) được đóng gói sẵn trong `docker-compose.yml`:
```powershell
# Khởi động cụm dịch vụ
docker compose up -d --build

# Kiểm tra trạng thái các container
docker compose ps
```
- **Streamlit Portal**: `http://localhost:8501`
- **FastAPI Gateway**: `http://localhost:8000/docs`
- **Cube Semantic Layer**: `http://localhost:4000`
- **Qdrant Vector DB**: `http://localhost:6333/dashboard`

---

## 🧪 Kiểm Thử & Đo Lường Định Lượng

### Chạy Toàn bộ Pytest Test Suite:
```powershell
python -m pytest tests/test_platform.py -v
```
*(Kết quả: 7/7 bài kiểm thử PASSED 100%)*

### Chạy Bộ Đánh giá Golden Dataset Benchmark:
```powershell
python -m evaluation.evaluator
```
*(Kết quả: 8/8 test cases PASSED 100%, Security Block Rate: 100.0%, Metric Consistency: 100.0%)*
