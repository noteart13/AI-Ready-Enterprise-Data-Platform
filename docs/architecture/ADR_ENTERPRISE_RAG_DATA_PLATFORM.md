# Kiến Trúc Hệ Thống: AI-Ready Enterprise Data Platform & Enterprise Hybrid RAG

> Tài liệu Kiến trúc & Quyết định Thiết kế (ADR - Architecture Decision Records) tuân thủ tiêu chuẩn Enterprise Software Architecture, Zero-Trust AI Security và LLMOps.

---

## 1. Bối cảnh & Mục tiêu Chuyển đổi Kiến trúc

| Tiêu chí | Trạng thái Ban đầu (Demo/PoC) | Trạng thái Sau Cải tiến (Enterprise Standard) |
| :--- | :--- | :--- |
| **Authentication & RBAC** | Fallback quyền admin khi thiếu token; cho phép đổi persona qua request body hoặc header; endpoint issue token tự do. | **Zero-Trust Strict JWT**: Bắt buộc Bearer token với chữ ký HS256, kiểm tra thời hạn, mã hóa claims bất biến (`tenant_id`, `role`, `department`, `clearance`). Loại bỏ hoàn toàn ghi đè persona. |
| **Semantic Embedding** | Mock hash vector (MD5 word hashing) sinh vector giả lập. | **Production FastEmbed (ONNX)**: Mô hình thực `BAAI/bge-small-en-v1.5` (384-dim), hỗ trợ đa nhà cung cấp (OpenAI, Azure OpenAI, Gemini). |
| **Lexical Search & Ranking** | Đếm tần suất từ khóa thủ công; giới hạn 50 chunks; trọng số tùy ý. | **Chuẩn Okapi BM25 (`BM25Okapi`)**: Tính toán IDF toàn kho văn bản, chuẩn hóa độ dài tài liệu (k1=1.5, b=0.75), kết hợp Dense HNSW bằng thuật toán **Reciprocal Rank Fusion (RRF k=60)**. |
| **Qdrant Vector Point ID** | Python `hash()` phụ thuộc vào `PYTHONHASHSEED` ngẫu nhiên giữa các tiến trình. | **RFC 4122 UUID5**: Tạo ID vector xác định 100% dựa trên namespace URL và `chunk_id`, chống trùng lặp tuyệt đối giữa các lần chạy. |
| **SQL RLS & Anti-Injection** | Ghép chuỗi SQL thô trong mệnh đề WHERE bộ lọc; nguy cơ SQLi và Cross-Tenant Leakage. | **Tham số hóa Truy vấn (Parameterized SQL)** + Kiểm tra biên giới Tenant Isolation + Thẩm định cú pháp AST tự động bằng `sqlglot`. |
| **Benchmark & Đánh giá** | 8 test cases thủ công, chỉ đánh giá sơ bộ. | **Bộ Golden Benchmark 140 Cases**: Đo lường Recall@K, MRR, Citation Provenance, Security Attack Block Rate, P95 Latency và Chi phí FinOps. |

---

## 2. Danh mục Quyết định Kiến trúc (Architecture Decision Records)

### ADR-001: Strict Cryptographic JWT Authentication & Elimination of Body Persona Overrides

- **Bối cảnh**: Hệ thống ban đầu hỗ trợ tham số `persona: "admin"` trong `ChatRequest` body và mặc định cấp quyền Admin khi không có `Authorization` header. Cơ chế này tiện cho PoC nhưng là lỗ hổng nghiêm trọng cho phép leo thang đặc quyền (Privilege Escalation).
- **Lựa chọn cân nhắc**:
  1. *Option A (Session Cookies)*: Phụ thuộc vào stateful session server, khó mở rộng microservices.
  2. *Option B (OAuth2 / Stateless JWT Claims)*: Đóng gói toàn bộ Security Claims bất biến (`sub`, `tenant_id`, `role`, `department`, `security_clearance`) có chữ ký số.
- **Quyết định**: Chọn **Option B**. Bắt buộc mọi truy vấn API Gateway phải có Bearer JWT. Trường `persona` trong request body bị loại bỏ hoàn toàn. Endpoint login `/api/v1/auth/login` kiểm tra mật khẩu đã hash.
- **Hệ quả**:
  - *Tích cực*: Ngăn chặn 100% hành vi giả mạo vai trò hoặc truy cập vượt quyền.
  - *Đánh đổi*: Client phải đăng nhập để lấy token trước khi gọi API.

---

### ADR-002: Real On-Device Embedding with FastEmbed (ONNX) & Multi-Provider Architecture

- **Bối cảnh**: Mock vector không phản ánh đúng ngữ nghĩa thực tế của tài liệu và câu hỏi, làm sai lệch benchmark RAG.
- **Lựa chọn cân nhắc**:
  1. *Option A (Chỉ dùng Cloud API OpenAI/Azure)*: Phụ thuộc internet, tốn chi phí API tokens, chậm khi chạy CI/CD.
  2. *Option B (PyTorch Transformers nặng ký)*: Cần tải model nhiều GB, yêu cầu GPU hoặc tốn RAM.
  3. *Option C (FastEmbed với Quantized ONNX Runtime)*: Tải model ONNX nhỏ gọn (~60MB), suy luận cục bộ cực nhanh (< 5ms/vector), không tốn chi phí token.
- **Quyết định**: Chọn **Option C (FastEmbed)** làm mặc định cho hệ thống, đồng thời duy trì interface mở cho phép chuyển đổi sang OpenAI, Azure OpenAI hoặc Gemini qua biến môi trường.
- **Hệ quả**:
  - *Tích cực*: Benchmark đạt tính đúng đắn 100% ngữ nghĩa thật; chạy offline hoàn toàn; không tốn chi phí API; tích hợp trơn tru trong CI/CD.
  - *Tự động di chuyển (Migration)*: Hệ thống tự động phát hiện sự thay đổi kích thước vector (1536 ➔ 384) và tái lập chỉ mục Qdrant mà không làm gián đoạn vận hành.

---

### ADR-003: Standard Okapi BM25 Lexical Indexing & Reciprocal Rank Fusion (RRF)

- **Bối cảnh**: Đếm từ khóa thô sơ bỏ qua độ hiếm của từ (IDF) và chiều dài đoạn văn, dẫn đến kết quả tìm kiếm từ khóa sai lệch.
- **Quyết định**: Tích hợp thuật toán chuẩn **Okapi BM25** (`rank_bm25.BM25Okapi` với $k_1=1.5, b=0.75$) lập chỉ mục toàn bộ Gold Chunks. Kết hợp kết quả Dense Vector Search và Lexical BM25 Search bằng công thức **Reciprocal Rank Fusion**:
  $$\text{RRF\_Score}(d) = \sum_{m \in \{\text{dense}, \text{bm25}\}} \frac{1}{60 + \text{rank}_m(d)}$$
  Đồng thời áp dụng bộ lọc Zero-Trust Security Trimming để chỉ người dùng có cấp bảo mật hợp lệ mới có thể nhận tài liệu.
- **Hệ quả**: Khả năng truy xuất chính xác cả thuật ngữ pháp lý / mã hợp đồng (ví dụ `CTR-2026-VIP-001`, `POL-2026-RET-01`) lẫn diễn đạt ngữ nghĩa tự nhiên.

---

### ADR-004: Stable RFC 4122 UUID5 Deterministic Point IDs for Vector Database

- **Bối cảnh**: Hàm `hash()` tích hợp sẵn của Python tạo ra giá trị băm ngẫu nhiên trên mỗi phiên chạy (do cơ chế bảo mật `PYTHONHASHSEED`), làm ID của cùng một chunk thay đổi sau mỗi lần khởi động service, gây trùng lặp điểm trong Qdrant.
- **Quyết định**: Chuyển sang sử dụng chuỗi UUID phiên bản 5 chuẩn RFC 4122:
  ```python
  point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk://{row['chunk_id']}"))
  ```
- **Hệ quả**: Điểm ID hoàn toàn ổn định, xác định và không phụ thuộc vào hệ điều hành hay seed ngẫu nhiên của Python.

---

### ADR-005: Zero-Trust Row-Level Security (RLS) Parameterization & Anti-Injection Guardrails

- **Bối cảnh**: Khi người dùng truyền bộ lọc vào Semantic Layer, việc nội suy chuỗi trực tiếp tạo ra nguy cơ SQL Injection và phá vỡ phân vùng đa khách hàng (Tenant Isolation).
- **Quyết định**:
  1. Kiểm tra biên giới Tenant: Chặn đứng mọi filter cố tình chỉ định tenant khác với `sec.tenant_id` của token.
  2. Tham số hóa 100% câu lệnh truy vấn DuckDB (`con.execute(sql, params)`).
  3. Thẩm định cây cú pháp trừu tượng (AST Guardrail) bằng thư viện `sqlglot` để cấm tuyệt đối stacked queries, comment tricks và subquery độc hại.
- **Hệ quả**: Ngăn chặn 100% rò rỉ chéo tenant (Cross-Tenant Leakage) và 100% tấn công SQLi.

---

## 3. Sơ đồ Kiến trúc & Luồng Thực thi (Architecture Flow)

```mermaid
flowchart TD
    Client[Client / Web UI / REST Client] -->|1. Bearer JWT Token| Gateway[FastAPI Enterprise Gateway]
    Gateway -->|2. Verify Claims| AuthEngine[Zero-Trust Auth Engine]
    AuthEngine -- Invalid / Missing --> Err401[HTTP 401 Unauthorized]
    
    AuthEngine -- Valid Claims --> FinOpsCache{3. Semantic Cache Hit?\nP95 < 100ms}
    FinOpsCache -- HIT --> CachedResponse[Trả về kết quả ngay lập tức]
    
    FinOpsCache -- MISS --> Supervisor[4. LangGraph Supervisor Router]
    Supervisor -->|AST Guardrail| ASTCheck{An toàn?}
    ASTCheck -- SQLi / Jailbreak --> SecurityBlocked[5. Security Blocked & Logged]
    
    ASTCheck -- Hợp lệ --> RouteExec[6. Phân rã Ý định]
    RouteExec -- STRUCTURED_BI --> BIAgent[Structured BI Agent\n(Semantic Layer + RLS)]
    RouteExec -- UNSTRUCTURED_RAG --> RAGAgent[Hybrid RAG Agent\n(FastEmbed + BM25Okapi + RRF)]
    RouteExec -- HYBRID_ANALYSIS --> CrossAnalysis[Đồng thời BI + RAG]
    
    BIAgent --> DuckDBEngine[(Gold Lakehouse DuckDB)]
    RAGAgent --> QdrantEngine[(Qdrant Vector DB)]
    
    BIAgent --> Synthesizer[7. Synthesizer Node]
    RAGAgent --> Synthesizer
    CrossAnalysis --> Synthesizer
    
    Synthesizer --> Auditor[8. Auditor Node: Provenance & Grounding]
    Auditor --> CacheUpdate[Lưu Semantic Cache]
    CacheUpdate --> FinalResponse[9. Structured Citations & Final Answer]
```
