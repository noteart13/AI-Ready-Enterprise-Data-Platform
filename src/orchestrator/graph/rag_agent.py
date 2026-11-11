"""
Unstructured Hybrid RAG Sub-Agent.
Queries Qdrant with BM25 + Dense Vector HNSW + RRF rank fusion,
applying Zero-Trust ACL Security Trimming.
"""

from src.orchestrator.graph.state import AgentState
from src.retrieval.hybrid_retriever import HybridRetriever


def rag_agent_node(state: AgentState) -> AgentState:
    trace = state.get("execution_trace", [])
    query = state["user_query"]
    sec = state["security_context"]

    trace.append(f"RAG Agent: Running Hybrid Search (Dense + BM25 + ACL Trimming: {sec.security_clearance})...")

    try:
        retriever = HybridRetriever()
        chunks = retriever.retrieve_hybrid(query=query, security_context=sec, top_k=4)
        state["rag_result"] = chunks
        trace.append(f"RAG Agent: Retrieved {len(chunks)} authorized document chunks after security trimming.")
    except Exception as e:
        trace.append(f"RAG Agent: Retrieval error: {e}")
        state["rag_result"] = []

    state["execution_trace"] = trace
    return state
