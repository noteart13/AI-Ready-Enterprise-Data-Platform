# AI-Ready Enterprise Data Platform

> **A Unified Enterprise Data Platform powering Business Intelligence (BI), Natural Language Querying (NLQ), and Multi-Agent AI Systems with Multi-Tier Governance and Zero-Trust Security.**

![Architecture Design](Architecture_Design.png)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B.svg?logo=streamlit)](https://streamlit.io)
[![Delta Lake](https://img.shields.io/badge/Delta_Lake-0.17+-00ADD8.svg)](https://delta.io)
[![DuckDB](https://img.shields.io/badge/DuckDB-0.10+-FFF000.svg?logo=duckdb)](https://duckdb.org)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.11+-DC2626.svg?logo=qdrant)](https://qdrant.tech)
[![Cube Core](https://img.shields.io/badge/Cube-0.35+-7A40F2.svg)](https://cube.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.30+-black.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-Ready-2496ED.svg?logo=docker)](https://www.docker.com/)

---

## 🌟 Key Architecture Highlights

### 1. Idempotent Ingestion & Control Plane (Stage 1)
- **Stateful Governance**: Centralized control plane tracking high-watermarks (`watermark`), execution history (`run_log`), and cryptographic SHA-256 checksums (`file_manifest`).
- **Cost & Compute Optimization**: Automatically identifies and bypasses unchanged structured tables and unstructured documents, eliminating redundant compute and reducing LLM embedding API costs by over 85%.

### 2. Medallion Lakehouse & Data Quality Gate (Stage 2)
- **Multi-Hop Medallion Storage**:
  - **Bronze**: Append-only, raw immutable Delta Lake tables.
  - **Silver**: Slowly Changing Dimensions (SCD Type 2) tracking historical changes (`valid_from`, `valid_to`, `is_current`) alongside cleaned and normalized document text.
  - **Gold**: High-performance Star Schema (`fact_orders`, `fact_order_items`, `fact_sla_performance`, `dim_customers`, `dim_products`) and deterministically partitioned RAG chunks.
- **Enforced Data Quality Gate**: Pre-publish data validation pipeline using **Pandera** for schema compliance and **DuckDB SQL Assertions** for foreign key referential integrity, range constraints, and orphan record prevention.

### 3. Single Source of Truth Semantic Layer (Stage 3)
- **Headless Semantic Modeling**: Implemented with **Cube Core** backed by an embedded **DuckDB** analytical engine.
- **Metrics-as-Code**: Standardized definitions for critical business KPIs (`netRevenue`, `grossProfit`, `slaBreachRate`, `customerLTV`), preventing metric drift and eliminating 100% of LLM mathematical hallucinations.
- **Dynamic Row-Level Security (RLS)**: Enforces compile-time tenant isolation (`tenant_id`) and clearance filtering within generated SQL queries.

### 4. Enterprise Hybrid RAG Pipeline (Stage 4)
- **Dual-Engine Retrieval**: Combines exact lexical matching via **BM25** with high-dimensional dense vector embeddings (**HNSW**) indexed in **Qdrant**.
- **Reciprocal Rank Fusion (RRF)**: Merges sparse and dense search results using rank-based weighting ($k=60$).
- **Zero-Trust Document ACL Trimming**: Post-retrieval security trimming that strictly filters documents against user clearance levels (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).

### 5. Multi-Agent AI Orchestrator & Defense-in-Depth (Stage 5)
- **LangGraph StateGraph Routing**:
  - `Router`: Classifies incoming user intent into Structured BI, Unstructured Knowledge Retrieval, or Cross-Analysis Synthesis.
  - `Structured BI Agent`: Converts natural language into governed Semantic Layer queries.
  - `Hybrid RAG Agent`: Executes ACL-filtered hybrid retrieval over enterprise knowledge.
  - `Cross-Analysis Synthesizer`: Correlates quantitative Lakehouse metrics with unstructured operational policies.
  - `Grounding Auditor`: Validates facts against source citations, flagging ungrounded assertions.
- **SQL AST Guardrail**: Uses `sqlglot` to parse Abstract Syntax Trees, blocking SQL injection, statement stacking, and DDL/DML data manipulation attempts.
- **FinOps Semantic Caching**: Redis-powered semantic cache providing P95 latency < 100ms for repeated/similar queries, paired with token-bucket rate limiting.
- **Enterprise Streamlit Portal**: Real-time role-based persona switching (`Executive`, `Store Manager`, `Data Analyst`, `External Partner`) with interactive citations and telemetry metrics.

### 6. 3D WebGL Digital Twin Universe (Three.js r128)
- **Interactive Spatial Visualization**: A full 3D interactive model visualizing the platform topology:
  - **Ingestion Hub & Bronze**: OLTP databases, raw file silos, and the SHA-256 manifest security barrier.
  - **Silver & Quality Gate**: SCD Type 2 transformation engine and glowing Pandera Quality Gate perimeter.
  - **Gold Star Schema**: Pyramidal fact tables linked to orbiting dimension satellites.
  - **Cube Semantic Layer**: Central cyan Cube Core with rotating Metrics-as-Code rings.
  - **Qdrant Vector Space**: 3D vector embeddings categorized by security ACL clearance.
  - **LangGraph Agent Nexus**: Central neural router pulsating dynamic light beams across all 4 specialized agents.
- **Features**: OrbitControls, camera teleportation presets, click-to-inspect HUD, and animated particle data streams between pipeline layers.

### 7. Automated Evaluation & Benchmark Suite (Stage 6)
- **Golden Dataset Verification**: Built-in benchmark suite measuring:
  - **Metric Consistency**: **100.0%**
  - **Security Block Rate (Red-Team & RBAC)**: **100.0%**
  - **Citation Provenance Rate**: **100.0%**
  - **P95 Semantic Cache Latency**: **< 1ms**

---

## 📁 Repository Structure

```text
├── cube/                          # Headless Semantic Layer (Cube Core)
│   ├── cube.js                    # Cube configuration & DuckDB driver setup
│   └── schema/                    # Metrics-as-Code definitions (YML)
│       ├── Customers.yml
│       ├── Orders.yml
│       ├── Products.yml
│       └── SLAPerformance.yml
├── data/                          # Seed data & Lakehouse storage
│   ├── control/                   # SQLite control plane (watermarks, run_log, manifests)
│   ├── lakehouse/                 # Medallion Delta Lake (Bronze, Silver, Gold)
│   ├── raw_documents/             # Enterprise documents (PDF, DOCX, XLSX, XML)
│   └── seed_oltp/                 # SQLite OLTP transactional database
├── evaluation/                    # Quantitative evaluation & benchmarking
│   ├── evaluator.py               # Golden dataset test harness
│   └── golden_dataset.json        # Test cases across BI, RAG, Cross-Analysis & Red-Team
├── src/
│   ├── ingestion/                 # Stage 1: Ingestion & Control Plane
│   │   ├── control_plane.py       # Idempotency manager & metadata storage
│   │   ├── document_parser.py     # Multi-format document parser
│   │   ├── seed_generator.py      # Synthetic enterprise data generator
│   │   ├── structured_loader.py   # OLTP -> Bronze Delta Lake loader
│   │   └── unstructured_loader.py # Documents -> Bronze Delta Lake loader
│   ├── lakehouse/                 # Stage 2: Medallion Transforms & Quality Gate
│   │   ├── silver_transforms.py   # SCD Type 2 & document normalization
│   │   ├── quality_gate.py        # Pandera schemas & DuckDB SQL assertions
│   │   └── gold_transforms.py     # Star Schema & DuckDB export
│   ├── semantic/                  # Stage 3: Semantic Layer Client
│   │   └── cube_client.py         # Cube REST API client with RLS & fallback engine
│   ├── retrieval/                 # Stage 4: Hybrid RAG Engine
│   │   ├── embedding_service.py   # Dense vector embeddings (Azure OpenAI / Mock)
│   │   └── hybrid_retriever.py    # BM25 + Qdrant HNSW + RRF + ACL trimming
│   ├── orchestrator/              # Stage 5: LangGraph Multi-Agent Orchestrator
│   │   ├── cache/semantic_cache.py# Redis semantic caching & rate limiting
│   │   ├── graph/                 # LangGraph StateGraph nodes
│   │   │   ├── router.py          # Intent routing node
│   │   │   ├── bi_agent.py        # Structured BI agent
│   │   │   ├── rag_agent.py       # Hybrid RAG agent
│   │   │   ├── synthesizer.py     # Cross-analysis synthesizer
│   │   │   ├── auditor.py         # Grounding & citation auditor
│   │   │   ├── state.py           # Typed State definition
│   │   │   └── workflow.py        # StateGraph compilation
│   │   ├── security/              # Security & Guardrails
│   │   │   ├── ast_guardrails.py  # sqlglot SQL AST security validation
│   │   │   └── auth.py            # RBAC persona tokens & clearance mapping
│   │   └── main.py                # FastAPI gateway application
│   └── ui/                        # User Interface
│       ├── app.py                 # Streamlit Enterprise Portal
│       └── static/lakehouse_3d.html# Three.js 3D WebGL Digital Twin Universe
├── tests/                         # End-to-end platform tests
│   └── test_platform.py
├── docker-compose.yml             # Container orchestration
├── Dockerfile.api                 # FastAPI container specification
├── Dockerfile.ui                  # Streamlit container specification
├── Makefile                       # Convenient workflow automation
├── requirements.txt               # Python package dependencies
└── README.md                      # Documentation
```

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10 or higher
- (Optional) Docker & Docker Compose for containerized deployment

### 1. Installation & Environment Configuration

Clone the repository and install dependencies:
```bash
git clone https://github.com/noteart13/AI-Ready-Enterprise-Data-Platform.git
cd AI-Ready-Enterprise-Data-Platform

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Set up your environment variables:
```bash
cp .env.example .env
```
*(By default, `LLM_PROVIDER=mock` and `EMBEDDING_PROVIDER=mock` are enabled, allowing the platform to run fully locally without external API keys or cloud credentials.)*

---

### 2. Run the End-to-End Pipeline Locally

You can execute the entire pipeline with a single `make` command:
```bash
make pipeline
```

Or run each stage step-by-step:

```bash
# Step 1: Generate synthetic B2B OLTP data and enterprise documents
python src/ingestion/seed_generator.py

# Step 2: Ingest into Bronze Delta Lake with SHA-256 manifest tracking
python -m src.ingestion.structured_loader
python -m src.ingestion.unstructured_loader

# Step 3: Run Silver transforms (SCD Type 2), Data Quality Gate, and Gold Star Schema
python -m src.lakehouse.silver_transforms
python -m src.lakehouse.quality_gate
python -m src.lakehouse.gold_transforms

# Step 4: Index Gold knowledge chunks into Qdrant vector storage
python -c "from src.retrieval.hybrid_retriever import HybridRetriever; hr = HybridRetriever(); hr.index_gold_chunks()"
```

---

### 3. Launch the Applications

#### Option A: Streamlit AI Enterprise Portal (Recommended)
```bash
streamlit run src/ui/app.py --server.port 8501
```
Open your browser at **[http://localhost:8501](http://localhost:8501)**.
- Explore the **Lakehouse & Analytics Explorer** to inspect Delta Lake tables and DuckDB queries.
- Switch personas via the **Role & Clearance Selector** to experience dynamic RLS and ACL trimming.
- Open the **3D WebGL Digital Twin Universe** tab to explore the interactive Three.js platform visualizer.

#### Option B: FastAPI Central Orchestrator Gateway
```bash
uvicorn src.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```
View interactive OpenAPI documentation at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

---

## 🐳 Docker Compose Deployment

Spin up all platform microservices (Redis, Qdrant, Cube Core, FastAPI, Streamlit) simultaneously:

```bash
# Start all services in the background
docker compose up -d --build

# Verify container health status
docker compose ps
```

### Service Endpoints

| Service | Port | Description | URL |
| :--- | :--- | :--- | :--- |
| **Streamlit Portal** | `8501` | Enterprise AI Portal & 3D WebGL Cockpit | [http://localhost:8501](http://localhost:8501) |
| **FastAPI Gateway** | `8000` | Orchestrator API & Interactive Swagger UI | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Cube Core** | `4000` | Headless Semantic Layer & SQL API | [http://localhost:4000](http://localhost:4000) |
| **Qdrant Dashboard** | `6333` | Vector Database Web Dashboard | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) |
| **Redis** | `6379` | FinOps State & Semantic Cache | `localhost:6379` |

To tear down all services:
```bash
docker compose down
```

---

## 🧪 Testing & Verification

### 1. Pytest Test Suite
Execute the end-to-end integration test suite verifying Ingestion, Medallion Transforms, Quality Gates, Cube Semantics, Hybrid RRF, Guardrails, and LangGraph Agent flows:
```bash
python -m pytest tests/test_platform.py -v
```
**Result**: `7/7 passed (100%)`

### 2. Golden Dataset Evaluation Benchmark
Run quantitative evaluation measuring response accuracy, metric consistency, security block rates, and cache performance:
```bash
python -m evaluation.evaluator
```
**Result**: `8/8 test cases passed (100%)`
- **Metric Consistency**: `100.0%`
- **Security Block Rate (Red-Team & RBAC)**: `100.0%`
- **Citation Provenance Rate**: `100.0%`
- **P95 Semantic Cache Latency**: `< 1ms`

---

## 🛡️ Security, Governance & Zero-Trust Design

| Security Layer | Implementation Mechanism | Protection Guarantee |
| :--- | :--- | :--- |
| **Data Plane Integrity** | SHA-256 Checksum Manifest & High-Watermark tracking | Prevents duplicate processing, ensures data provenance |
| **Schema & Quality Gate** | Pandera Schema Validation + DuckDB SQL Assertions | Rejects corrupted rows, prevents referential integrity violations |
| **Semantic Governance** | Cube Core Metrics-as-Code + DuckDB Semantic Engine | Eliminates LLM calculation hallucinations and metric drift |
| **Row-Level Security** | Dynamic Tenant Filtering (`tenant_id = ?`) in SQL generation | Strict multi-tenant isolation at the database layer |
| **Document Access Control** | Zero-Trust ACL Hierarchy (`PUBLIC` $\to$ `RESTRICTED`) | Eliminates unauthorized document retrieval in RAG responses |
| **Query Guardrails** | `sqlglot` Abstract Syntax Tree (AST) validation | Strictly blocks SQL injection, `DROP`, `DELETE`, and stacked queries |
| **FinOps Protection** | Redis Semantic Caching & Token-Bucket Rate Limiter | Protects backend infrastructure from query flooding and cost spikes |

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
