"""
LangGraph Multi-Agent State Definition.
"""

from typing import TypedDict, List, Dict, Any, Optional
from src.semantic.cube_client import SecurityContext


class AgentState(TypedDict):
    user_query: str
    security_context: SecurityContext
    intent: str # 'STRUCTURED_BI', 'UNSTRUCTURED_RAG', 'HYBRID_ANALYSIS', 'SECURITY_BLOCKED'
    sql_guardrail_passed: bool
    semantic_result: Optional[Dict[str, Any]]
    rag_result: Optional[List[Dict[str, Any]]]
    final_answer: Optional[str]
    structured_citations: List[Dict[str, Any]]
    execution_trace: List[str]
    latency_ms: float
    cache_hit: bool
