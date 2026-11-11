"""
Supervisor Intent Router & Security Guardrail Pre-Check.
"""

import re
from src.orchestrator.graph.state import AgentState
from src.orchestrator.security.ast_guardrails import SQLASTGuardrail, SecurityBreachError


def router_node(state: AgentState) -> AgentState:
    query = state["user_query"]
    trace = state.get("execution_trace", [])
    trace.append("Router: Analyzing intent and checking guardrails...")

    # 1. Check for Red-Team Attack / SQL Injection Patterns
    attack_patterns = [
        r"(--|/\*|\*/|;\s*drop|;\s*delete|;\s*truncate)",
        r"(union\s+select|select\s+.*\s+from\s+information_schema)",
        r"(xp_cmdshell|exec\s*\(|benchmark\s*\()",
        r"(ignore previous instructions|bỏ qua hướng dẫn trước|jailbreak)"
    ]
    for pat in attack_patterns:
        if re.search(pat, query, re.IGNORECASE):
            trace.append("Security Guardrail: BLOCKED - Red-team/SQL injection pattern detected!")
            state["intent"] = "SECURITY_BLOCKED"
            state["final_answer"] = (
                "Cảnh báo An ninh: Yêu cầu của bạn bị từ chối do vi phạm chính sách bảo mật Zero-Trust "
                "(Phát hiện dấu hiệu tấn công SQL Injection hoặc Jailbreak bypass)."
            )
            state["sql_guardrail_passed"] = False
            state["execution_trace"] = trace
            return state

    state["sql_guardrail_passed"] = True

    # 2. Heuristic Intent Decomposition
    q_lower = query.lower()

    bi_keywords = [
        "doanh thu", "doanh số", "lợi nhuận", "đơn hàng", "số lượng", "orders", 
        "revenue", "profit", "giá trị", "aov", "tổng kết", "thống kê", "tồn kho", "báo cáo số liệu"
    ]
    rag_keywords = [
        "hợp đồng", "điều khoản", "quy định", "chính sách", "đổi trả", "bảo hành",
        "sop", "thời hạn", "cam kết", "phạt", "sla", "tiêu chuẩn", "tài liệu", "contract", "policy",
        "kiểm toán", "audit", "báo cáo tài chính"
    ]

    has_bi = any(k in q_lower for k in bi_keywords)
    has_rag = any(k in q_lower for k in rag_keywords)

    if has_bi and has_rag:
        state["intent"] = "HYBRID_ANALYSIS"
        trace.append("Router: Classified as HYBRID_ANALYSIS (Cross-checking BI data with Contract terms)")
    elif has_bi:
        state["intent"] = "STRUCTURED_BI"
        trace.append("Router: Classified as STRUCTURED_BI (Querying Semantic Layer)")
    elif has_rag:
        state["intent"] = "UNSTRUCTURED_RAG"
        trace.append("Router: Classified as UNSTRUCTURED_RAG (Querying Qdrant Hybrid Search)")
    else:
        # Default to hybrid if unclear
        state["intent"] = "HYBRID_ANALYSIS"
        trace.append("Router: Ambiguous intent, defaulting to HYBRID_ANALYSIS")

    state["execution_trace"] = trace
    return state
