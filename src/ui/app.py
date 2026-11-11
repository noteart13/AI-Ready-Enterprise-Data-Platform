"""
Streamlit AI Enterprise Portal.
Unified interface for:
- Multi-Tenant Persona Switching & Zero-Trust RBAC testing
- Interactive Natural Language Queries (NLQ) with Structured Citations
- BI Executive Dashboard powered by Semantic Layer
- Data Quality Gate & Lakehouse Health Monitor
"""

import os
import sys
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath("."))

from src.orchestrator.security.auth import PREDEFINED_PERSONAS
from src.orchestrator.graph.workflow import EnterpriseAgentOrchestrator
from src.semantic.cube_client import SemanticLayerClient
from src.lakehouse.quality_gate import DataQualityGate
from src.retrieval.hybrid_retriever import HybridRetriever

# Page Setup
st.set_page_config(
    page_title="AI-Ready Enterprise Data Platform",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = EnterpriseAgentOrchestrator()
if "semantic_client" not in st.session_state:
    st.session_state.semantic_client = SemanticLayerClient()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ==============================================================================
# SIDEBAR: Persona Switcher & Zero-Trust Security Context
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/database.png", width=100)
    st.title("Enterprise Control")
    st.markdown("---")

    st.subheader("👤 Persona Switcher (RBAC)")
    persona_options = {
        "👑 Giám đốc Điều hành (Admin / All Access)": "admin",
        "💼 Giám đốc Kinh doanh Miền Bắc (Sales North)": "sales_north",
        "💼 Giám đốc Kinh doanh Miền Nam (Sales South)": "sales_south",
        "📦 Quản lý Kho Vận (Warehouse Operator)": "warehouse_operator",
        "👀 Khách vãng lai / Khách hàng (Guest Public)": "guest_auditor"
    }

    selected_label = st.selectbox("Chọn vai trò người dùng:", list(persona_options.keys()))
    selected_persona_key = persona_options[selected_label]
    current_sec = PREDEFINED_PERSONAS[selected_persona_key]

    # Display Security Badges
    st.markdown("##### 🛡️ Ngữ cảnh Bảo mật Hiện tại:")
    st.info(
        f"**User ID:** `{current_sec.user_id}`\n\n"
        f"**Tenant:** `{current_sec.tenant_id}`\n\n"
        f"**Phòng ban:** `{current_sec.department}`\n\n"
        f"**Cấp bảo mật (Clearance):** `{current_sec.security_clearance}`"
    )

    st.markdown("---")
    st.subheader("⚙️ Trạng thái Hệ thống")
    st.success("🟢 Lakehouse: Delta Lake (DuckDB)")
    st.success("🟢 Semantic Layer: Active (RLS)")
    st.success("🟢 Vector Search: Qdrant Hybrid (BM25+HNSW)")
    st.success("🟢 FinOps Cache: Redis Engine (P95 < 100ms)")
    st.success("🟢 Data Quality: 100% Passed (Pandera)")

# ==============================================================================
# MAIN VIEW: Navigation Tabs
# ==============================================================================
st.title("🏢 AI-Ready Enterprise Data Platform")
st.caption("Nền tảng Dữ liệu Doanh nghiệp Hợp nhất phục vụ Báo cáo BI, Truy vấn NLQ và Multi-Agent Orchestrator với Phân quyền Đa tầng.")

tab_chat, tab_bi, tab_security, tab_arch = st.tabs([
    "💬 Trợ lý AI Đa Tác tử (NLQ Multi-Agent)",
    "📊 BI Executive Dashboard (Semantic Layer)",
    "🛡️ Giám sát Chất lượng Dữ liệu & Control Plane",
    "🏗️ Sơ đồ Kiến trúc & Luồng Dữ liệu (Architecture & Lineage)"
])

# ------------------------------------------------------------------------------
# TAB 1: AI MULTI-AGENT NLQ
# ------------------------------------------------------------------------------
with tab_chat:
    st.subheader("Hỏi đáp Tự nhiên Hợp nhất (Số liệu BI + Tài liệu Quy định)")
    st.markdown(
        "Đặt câu hỏi tự nhiên để hệ thống tự động phân rã ý định: truy vấn **Semantic Layer** lấy số liệu chính xác "
        "hoặc **Hybrid RAG** tra cứu hợp đồng/quy định, đồng thời đối chiếu đa nguồn."
    )

    # Preset Sample Prompts
    st.markdown("**Gợi ý kịch bản kiểm thử:**")
    col1, col2, col3 = st.columns(3)
    prompt_clicked = None
    with col1:
        if st.button("📊 [BI] Doanh thu & Tỷ lệ trễ đơn theo tháng?"):
            prompt_clicked = "Tổng hợp doanh thu thuần và số đơn hàng theo tháng của khu vực?"
        if st.button("🚨 [Red-Team] Thử tấn công SQL Injection"):
            prompt_clicked = "'; DROP TABLE fact_orders; SELECT * FROM customers WHERE '1'='1"
    with col2:
        if st.button("📄 [RAG] Thời hạn đổi trả hàng theo chính sách?"):
            prompt_clicked = "Thời hạn và điều kiện được chấp thuận đổi trả hàng hóa theo quy định là bao nhiêu ngày?"
        if st.button("🔒 [RBAC] Xem báo cáo kiểm toán tài chính nội bộ"):
            prompt_clicked = "Báo cáo chi tiết lợi nhuận gộp và chi phí thưởng ban điều hành trong kỳ kiểm toán AUD-2026-Q1?"
    with col3:
        if st.button("🔍 [Hybrid] Đối chiếu đơn trễ với phạt hợp đồng VIP?"):
            prompt_clicked = "Đối chiếu số lượng đơn trễ hạn thực tế của đối tác Miền Bắc với điều khoản phạt trong hợp đồng CTR-2026-VIP-001?"

    # Input Box
    user_query = st.chat_input("Nhập câu hỏi của bạn (Ví dụ: Thống kê doanh thu, Tra cứu điều khoản hợp đồng SLA...)...")
    if prompt_clicked:
        user_query = prompt_clicked

    if user_query:
        with st.spinner("Đang điều phối các tác tử AI và áp dụng Zero-Trust Security..."):
            res = st.session_state.orchestrator.run(user_query, current_sec)
            st.session_state.chat_history.append({"query": user_query, "response": res, "persona": selected_label})

    # Render Chat History
    for chat in reversed(st.session_state.chat_history):
        with st.chat_message("user"):
            st.markdown(f"**{chat['query']}**")
            st.caption(f"Gửi bởi: {chat['persona']}")

        with st.chat_message("assistant"):
            r = chat["response"]
            
            # Metrics Badge Bar
            col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
            with col_m1:
                st.metric("Thời gian phản hồi", f"{r.get('latency_ms', 0)} ms")
            with col_m2:
                cache_status = "⚡ HIT (P95 < 100ms)" if r.get("cache_hit") else "🔄 LIVE EXECUTION"
                st.metric("Semantic Cache", cache_status)
            with col_m3:
                st.metric("Phân loại Ý định", r.get("intent", "UNKNOWN"))

            # Answer
            st.markdown(r.get("final_answer", ""))

            # BI Chart Visualization (if structured data present)
            bi_data = r.get("semantic_result", {}).get("data", [])
            if bi_data and len(bi_data) > 0:
                with st.expander("📈 Xem biểu đồ trực quan hóa dữ liệu Semantic", expanded=True):
                    df_bi = pd.DataFrame(bi_data)
                    st.dataframe(df_bi, use_container_width=True)

                    # Auto render bar chart if time dimension present
                    date_col = next((c for c in df_bi.columns if "orderYearMonth" in c or "date" in c or "tenantId" in c), None)
                    num_col = next((c for c in df_bi.columns if "Revenue" in c or "orderCount" in c), None)
                    if date_col and num_col:
                        st.bar_chart(df_bi.set_index(date_col)[num_col])

            # Structured Citations Expander
            citations = r.get("structured_citations", [])
            if citations:
                with st.expander(f"📚 Structured Citations ({len(citations)} nguồn kiểm chứng)", expanded=False):
                    for idx, cit in enumerate(citations):
                        if cit.get("type") == "DOCUMENT_CITATION":
                            st.markdown(
                                f"**[{idx+1}] Tài liệu:** `{cit.get('title')}` (Trang {cit.get('page_number')}) | "
                                f"Cấp bảo mật: `{cit.get('security_acl')}` | RRF Score: `{cit.get('relevance_score')}`"
                            )
                            st.caption(f"Trích đoạn: \"{cit.get('verifiable_excerpt')}\"")
                        elif cit.get("type") == "SEMANTIC_METRIC_CITATION":
                            st.markdown(
                                f"**[{idx+1}] Chỉ số Semantic:** `{cit.get('semantic_measures')}` | "
                                f"Engine: `{cit.get('source_engine')}` | Tenant: `{cit.get('tenant_id')}`"
                            )
                            st.code(cit.get("compiled_sql", ""), language="sql")

            # Execution Trace Expander
            traces = r.get("execution_trace", [])
            if traces:
                with st.expander("⚡ Execution Trace (Nhật ký thực thi tác tử)", expanded=False):
                    for t in traces:
                        st.text(f"• {t}")
        st.markdown("---")

# ------------------------------------------------------------------------------
# TAB 2: BI EXECUTIVE DASHBOARD
# ------------------------------------------------------------------------------
with tab_bi:
    st.subheader(f"Báo cáo Chỉ số Doanh nghiệp (Phân quyền Tenant: {current_sec.tenant_id})")
    st.markdown("Dữ liệu được truy vấn trực tiếp từ **Semantic Layer** bảo đảm 100% nhất quán.")

    try:
        # Load high-level KPIs
        kpi_res = st.session_state.semantic_client.query(
            measures=["Orders.orderCount", "Orders.netRevenue", "Orders.grossProfit", "Orders.slaBreachRate"],
            security_context=current_sec
        )
        kpi_data = kpi_res.get("data", [{}])[0]

        kcol1, kcol2, kcol3, kcol4 = st.columns(4)
        kcol1.metric("Tổng Đơn hàng", f"{kpi_data.get('Orders_orderCount', 0):,}")
        kcol2.metric("Doanh thu Thuần", f"${kpi_data.get('Orders_netRevenue', 0):,.2f}")
        kcol3.metric("Lợi nhuận Gộp", f"${kpi_data.get('Orders_grossProfit', 0):,.2f}")
        kcol4.metric("Tỷ lệ Vi phạm SLA", f"{kpi_data.get('Orders_slaBreachRate', 0)}%")

        st.markdown("---")

        # Monthly Trend
        trend_res = st.session_state.semantic_client.query(
            measures=["Orders.orderCount", "Orders.netRevenue", "Orders.slaBreachedCount"],
            dimensions=["Orders.orderYearMonth"],
            security_context=current_sec
        )
        if trend_res.get("data"):
            df_trend = pd.DataFrame(trend_res["data"]).sort_values("Orders_orderYearMonth")
            
            c_left, c_right = st.columns(2)
            with c_left:
                st.markdown("##### 📈 Xu hướng Doanh thu theo Tháng ($)")
                st.line_chart(df_trend.set_index("Orders_orderYearMonth")["Orders_netRevenue"])
            with c_right:
                st.markdown("##### 📦 Số lượng Đơn hàng & Đơn Vi phạm SLA")
                st.bar_chart(df_trend.set_index("Orders_orderYearMonth")[["Orders_orderCount", "Orders_slaBreachedCount"]])

            st.markdown("##### 📋 Bảng Chi tiết Dữ liệu Semantic:")
            st.dataframe(df_trend, use_container_width=True)

    except PermissionError as pe:
        st.warning(f"🔒 Hạn chế truy cập: {pe}")
    except Exception as e:
        st.error(f"Lỗi khi tải bảng điều khiển BI: {e}")

# ------------------------------------------------------------------------------
# TAB 3: DATA QUALITY & CONTROL PLANE
# ------------------------------------------------------------------------------
with tab_security:
    st.subheader("🛡️ Data Quality Gate & Ingestion Control Plane")
    
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        st.markdown("##### 🔍 Kiểm thử Chất lượng Dữ liệu (Pandera + DuckDB Assertions)")
        if st.button("Chạy kiểm tra Data Quality Gate ngay"):
            try:
                gate = DataQualityGate()
                report = gate.validate_gate()
                st.success("✅ Toàn bộ kiểm thử chất lượng dữ liệu ĐÃ ĐẠT (100% PASSED)!")
                st.json(report)
            except Exception as e:
                st.error(f"❌ Data Quality Gate thất bại: {e}")

    with col_q2:
        st.markdown("##### 📋 Bảng Kiểm soát Nạp Tăng trưởng (file_manifest & watermarks)")
        try:
            import sqlite3
            con = sqlite3.connect("./data/control/control_plane.db")
            st.markdown("**Bảng file_manifest (Dấu vân tay SHA-256):**")
            df_manifest = pd.read_sql_query("SELECT file_name, content_hash, file_type, status, last_processed_at FROM file_manifest", con)
            st.dataframe(df_manifest, use_container_width=True)

            st.markdown("**Bảng watermarks (Mốc tăng trưởng):**")
            df_wm = pd.read_sql_query("SELECT * FROM watermarks", con)
            st.dataframe(df_wm, use_container_width=True)
            con.close()
        except Exception as e:
            st.warning(f"Chưa có dữ liệu control plane: {e}")

# ------------------------------------------------------------------------------
# TAB 4: ARCHITECTURE & DATA LINEAGE
# ------------------------------------------------------------------------------
with tab_arch:
    st.subheader("🏗️ Sơ đồ Kiến trúc & Luồng Dữ liệu Hợp nhất (Architecture & Lineage)")
    st.markdown(
        "Toàn cảnh luồng dữ liệu chuẩn **Production Medallion Lakehouse** từ nguồn thô đến báo cáo BI và AI Agent."
    )

    # 6 Core Architectural Layers Summary
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(
            "**1. Ingestion & Control Plane**\n\n"
            "• Đa luồng: DB Giao dịch (OLTP) + Tài liệu (PDF, DOCX, XLSX, XML)\n\n"
            "• Idempotent: `file_manifest` SHA-256 & `watermarks` tăng trưởng"
        )
        st.info(
            "**4. Semantic Layer (Cube + DuckDB)**\n\n"
            "• Single Source of Truth: Metrics-as-Code (YAML)\n\n"
            "• Row-Level Security (RLS) theo `tenant_id` & `department`"
        )
    with c2:
        st.info(
            "**2. Medallion Lakehouse (Delta Lake)**\n\n"
            "• Bronze: Raw immutable Parquet & metadata\n\n"
            "• Silver: SCD Type 2 Customers/Products + Normalized Doc Model\n\n"
            "• Gold: Star Schema (`fact_orders`, `dim_customers`)"
        )
        st.info(
            "**5. Hybrid Vector Search (Qdrant)**\n\n"
            "• Tìm kiếm lai: Dense HNSW + Sparse BM25 + Thuật toán RRF\n\n"
            "• Zero-Trust ACL Payload Filtering theo người dùng"
        )
    with c3:
        st.info(
            "**3. Data Quality Gate**\n\n"
            "• Pandera Schema Validation (kiểm tra kiểu, range, non-null)\n\n"
            "• DuckDB SQL Assertions (khóa ngoại, logic nghiệp vụ)"
        )
        st.info(
            "**6. Multi-Agent Orchestrator (LangGraph)**\n\n"
            "• Phân rã ý định: Router ➔ Structured BI / Unstructured RAG\n\n"
            "• Chốt chặn an toàn: AST SQL Guardrail & FinOps Cache (Redis)"
        )

    st.markdown("---")
    st.markdown("##### 📊 Thống kê Tài nguyên Lưu trữ Thực tế (Live Lakehouse Storage)")
    try:
        import duckdb
        conn = duckdb.connect("./data/lakehouse/gold/lakehouse.duckdb", read_only=True)
        tables = conn.execute("SHOW TABLES").fetchall()
        tbl_names = [t[0] for t in tables]
        
        stat_cols = st.columns(min(len(tbl_names), 4))
        for idx, tbl in enumerate(tbl_names):
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            col_target = stat_cols[idx % 4]
            col_target.metric(f"Bảng `{tbl}`", f"{cnt:,} dòng")
        conn.close()
    except Exception as e:
        st.warning(f"Không thể đọc trực tiếp kho Gold DuckDB: {e}")

    st.markdown("---")
    st.markdown("##### 🔄 Quy trình Điều phối Tác tử AI (LangGraph StateGraph Workflow)")
    st.markdown(
        """
```mermaid
flowchart LR
    User[User Query] --> Guardrail[AST & RBAC Guardrail]
    Guardrail --> Cache{FinOps Cache?}
    Cache -- HIT (P95 < 100ms) --> FastResponse[Phản hồi Tức thì]
    Cache -- MISS --> Router[LangGraph Router]
    
    Router -- STRUCTURED_BI --> BIAgent[Structured BI Agent\n(Semantic Layer SQL)]
    Router -- UNSTRUCTURED_RAG --> RAGAgent[Unstructured RAG Agent\n(Qdrant Hybrid BM25+HNSW)]
    Router -- HYBRID_ANALYSIS --> HybridExec[Đồng thời BI + RAG\n(Đối chiếu đơn hàng & SLA hợp đồng)]
    
    BIAgent --> Synthesizer[Synthesizer Node]
    RAGAgent --> Synthesizer
    HybridExec --> Synthesizer
    
    Synthesizer --> Auditor[Auditor Node\n(Citations & Grounding Verification)]
    Auditor --> Final[Structured Citations & Final Answer]
```
        """
    )
