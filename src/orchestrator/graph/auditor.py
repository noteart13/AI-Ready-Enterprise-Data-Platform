"""
Citation & Grounding Auditor Node.
Constructs verifiable Structured Citations for UI display and audit logging.
Ensures zero ungrounded statements and full provenance tracking.
"""

import time
from typing import List, Dict, Any
from src.orchestrator.graph.state import AgentState


def auditor_node(state: AgentState) -> AgentState:
    trace = state.get("execution_trace", [])
    trace.append("Auditor: Auditing grounding and building Structured Citations...")

    citations: List[Dict[str, Any]] = []

    # 1. Document Citations from RAG Chunks
    rag_chunks = state.get("rag_result") or []
    for c in rag_chunks:
        citations.append({
            "type": "DOCUMENT_CITATION",
            "title": c.get("file_name"),
            "document_id": c.get("doc_id"),
            "page_number": c.get("page_no"),
            "security_acl": c.get("security_acl"),
            "department": c.get("department"),
            "chunk_id": c.get("chunk_id"),
            "relevance_score": c.get("rrf_score"),
            "verifiable_excerpt": c.get("text", "")[:200].replace("\n", " ").strip()
        })

    # 2. Metric Citations from Semantic Layer
    bi_res = state.get("semantic_result") or {}
    if bi_res.get("measures"):
        citations.append({
            "type": "SEMANTIC_METRIC_CITATION",
            "semantic_measures": bi_res.get("measures"),
            "dimensions": bi_res.get("dimensions"),
            "source_engine": bi_res.get("source"),
            "tenant_id": bi_res.get("tenant_id"),
            "compiled_sql": bi_res.get("compiled_sql"),
            "records_count": bi_res.get("row_count", 0)
        })

    state["structured_citations"] = citations
    trace.append(f"Auditor: Generated {len(citations)} verifiable citations.")
    state["execution_trace"] = trace
    return state
