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

    # 1. Comprehensive Red-Team Attack, Prompt Injection & SQL Injection Defense
    attack_patterns = [
        # SQL Injection / AST bypass tricks
        r"(--|/\*|\*/|;\s*(?:drop|delete|truncate|alter|create|insert|update))",
        r"\b(union\s+select|select\s+.*\s+from\s+information_schema)\b",
        r"\b(xp_cmdshell|exec\s*\(|benchmark\s*\(|pg_sleep)\b",
        # Prompt Injection, Jailbreaks, & System Override attempts
        r"\b(ignore\s+(?:all\s+)?previous\s+instructions|bỏ\s+qua\s+(?:mọi\s+)?hướng\s+dẫn)\b",
        r"\b(disregard\s+(?:all\s+)?(?:system\s+)?guardrails|dan\s+mode|do\s+anything\s+now|jailbreak)\b",
        r"\b(system\s+override|drop\s+all\s+restrictions|bypass\s+(?:all\s+)?security)\b",
        r"\b(grant\s+(?:me\s+)?admin|reveal\s+(?:all\s+)?passwords|output\s+all\s+executive\s+passwords)\b"
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
        "revenue", "profit", "giá trị", "aov", "tổng kết", "thống kê", "tồn kho", "báo cáo số liệu",
        "trễ hạn", "giao chậm", "vi phạm sla", "tỷ lệ vi phạm", "kỳ kế toán"
    ]
    rag_keywords = [
        "hợp đồng", "điều khoản", "quy định", "chính sách", "đổi trả", "bảo hành",
        "sop", "thời hạn", "cam kết", "phạt", "tiêu chuẩn", "tài liệu", "contract", "policy",
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
