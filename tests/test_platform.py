"""
Comprehensive Pytest Test Suite for AI-Ready Enterprise Data Platform.
Covers:
1. Ingestion Control Plane & Idempotency
2. Medallion Lakehouse & Pandera Data Quality Gate
3. Semantic Layer & Row-Level Security (RLS)
4. Hybrid Vector Search & ACL Security Trimming
5. SQL AST Guardrail & Anti-Injection Defense
6. FinOps Semantic Caching & Token Rate Limiting
7. Multi-Agent Orchestration & Structured Citations
"""

import os
import pytest
from src.ingestion.control_plane import ControlPlane
from src.lakehouse.quality_gate import DataQualityGate
from src.semantic.cube_client import SemanticLayerClient, SecurityContext
from src.retrieval.hybrid_retriever import HybridRetriever
from src.orchestrator.security.ast_guardrails import SQLASTGuardrail, SecurityBreachError
from src.orchestrator.cache.semantic_cache import SemanticCache
from src.orchestrator.graph.workflow import EnterpriseAgentOrchestrator


def test_control_plane_idempotency():
    """Verify SHA-256 calculation and idempotency state tracking."""
    cp = ControlPlane()
    test_file = "./data/raw_documents/CTR_2026_VIP_001_NorthDistribution.pdf"
    assert os.path.exists(test_file)

    # First check
    needs_processing, current_hash, record = cp.check_file_status(test_file)
    assert len(current_hash) == 64

    # Record manifest
    cp.record_file_manifest(test_file, current_hash, status="INGESTED")

    # Second check must yield needs_processing = False (Idempotency Hit)
    needs_proc2, _, record2 = cp.check_file_status(test_file)
    assert needs_proc2 is False
    assert record2["status"] == "INGESTED"


def test_data_quality_gate():
    """Verify Pandera schemas and DuckDB referential integrity assertions."""
    gate = DataQualityGate()
    report = gate.validate_gate()
    assert report["overall_status"] == "PASSED"
    assert report["sql_assertions"]["check_no_orphaned_orders"]["violations"] == 0
    assert report["sql_assertions"]["check_no_orphaned_order_items"]["violations"] == 0


def test_semantic_layer_and_rls():
    """Verify Semantic Layer computes correct metrics and applies RLS on tenant."""
    client = SemanticLayerClient()

    # Admin query
    res_admin = client.query(
        measures=["Orders.orderCount", "Orders.netRevenue"],
        dimensions=["Orders.tenantId"]
    )
    assert res_admin["row_count"] == 2
    tenants = [r["Orders_tenantId"] for r in res_admin["data"]]
    assert "VN_DIST_NORTH" in tenants
    assert "VN_DIST_SOUTH" in tenants

    # Sales North query (RLS should restrict strictly to VN_DIST_NORTH)
    sec_north = SecurityContext(tenant_id="VN_DIST_NORTH", role="sales_manager", department="SALES")
    res_north = client.query(
        measures=["Orders.orderCount", "Orders.netRevenue"],
        security_context=sec_north
    )
    assert res_north["row_count"] == 1
    # Check that revenue is around 1,203,780.50
    assert res_north["data"][0]["Orders_netRevenue"] > 1000000.0


def test_hybrid_retrieval_and_acl_trimming():
    """Verify Qdrant Hybrid Search and ACL clearance security trimming."""
    retriever = HybridRetriever()
    retriever.index_gold_chunks()

    # Sales Manager (CONFIDENTIAL) can view VIP Contract
    sec_conf = SecurityContext(tenant_id="VN_DIST_NORTH", security_clearance="CONFIDENTIAL")
    res_conf = retriever.retrieve_hybrid("Hợp đồng CTR-2026-VIP-001 cam kết thời gian giao hàng", sec_conf)
    assert len(res_conf) > 0
    assert any("CTR_2026_VIP_001" in r["file_name"] for r in res_conf)

    # Guest (PUBLIC) cannot view RESTRICTED financial audit
    sec_public = SecurityContext(tenant_id="VN_DIST_NORTH", security_clearance="PUBLIC")
    res_public = retriever.retrieve_hybrid("Báo cáo kiểm toán AUD-2026-Q1 thưởng ban điều hành", sec_public)
    # Ensure no restricted files leaked
    assert not any(r["security_acl"] in ["RESTRICTED", "CONFIDENTIAL"] for r in res_public)


def test_sql_ast_guardrails():
    """Verify sqlglot AST guardrail blocks SQL injection, mutation, and comments."""
    # Valid Select
    assert SQLASTGuardrail.validate_sql("SELECT order_id, total_amount FROM fact_orders WHERE total_amount > 100") is True

    # Block Drop Table
    with pytest.raises(SecurityBreachError):
        SQLASTGuardrail.validate_sql("SELECT * FROM fact_orders; DROP TABLE fact_orders;")

    # Block Comment bypass
    with pytest.raises(SecurityBreachError):
        SQLASTGuardrail.validate_sql("SELECT * FROM fact_orders WHERE order_id = '1' -- comment")

    # Block unauthorized system table
    with pytest.raises(SecurityBreachError):
        SQLASTGuardrail.validate_sql("SELECT * FROM information_schema.tables")


def test_semantic_cache_finops():
    """Verify Redis/local Semantic Caching hit latency < 100ms."""
    cache = SemanticCache()
    prompt = "Doanh thu thuần quý 1 của Miền Bắc là bao nhiêu?"
    tenant = "VN_DIST_NORTH"
    clearance = "CONFIDENTIAL"

    test_payload = {"answer": "Doanh thu là 1,203,780.50 USD", "cached": True}
    cache.set_cache(prompt, tenant, clearance, test_payload)

    t0 = pytest.importorskip("time").time()
    hit = cache.get_cache(prompt, tenant, clearance)
    latency_ms = (pytest.importorskip("time").time() - t0) * 1000

    assert hit is not None
    assert hit["answer"] == test_payload["answer"]
    assert latency_ms < 50.0 # Sub-50ms cache response


def test_multi_agent_workflow():
    """Verify full end-to-end multi-agent execution with Structured Citations."""
    orchestrator = EnterpriseAgentOrchestrator()
    sec = SecurityContext(
        user_id="usr_sales_north",
        tenant_id="VN_DIST_NORTH",
        role="sales_manager",
        department="SALES",
        security_clearance="CONFIDENTIAL"
    )

    query = "Đối chiếu số lượng đơn trễ hạn thực tế của đối tác Miền Bắc với cam kết thời gian giao hàng trong hợp đồng CTR-2026-VIP-001?"
    result = orchestrator.run(query, sec)

    assert result["intent"] == "HYBRID_ANALYSIS"
    assert result["sql_guardrail_passed"] is True
    assert result["final_answer"] is not None
    assert len(result["structured_citations"]) > 0
    # Check that citations include both document and semantic metric
    types = [c["type"] for c in result["structured_citations"]]
    assert "DOCUMENT_CITATION" in types
    assert "SEMANTIC_METRIC_CITATION" in types
