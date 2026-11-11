"""
LangGraph Multi-Agent Workflow Definition & Compilation.
Coordinates Router, Specialized Sub-Agents (BI, RAG), Synthesizer, and Auditor.
"""

import time
from langgraph.graph import StateGraph, END
from src.orchestrator.graph.state import AgentState
from src.orchestrator.graph.router import router_node
from src.orchestrator.graph.bi_agent import bi_agent_node
from src.orchestrator.graph.rag_agent import rag_agent_node
from src.orchestrator.graph.synthesizer import synthesizer_node
from src.orchestrator.graph.auditor import auditor_node
from src.orchestrator.cache.semantic_cache import SemanticCache


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("bi_agent", bi_agent_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("auditor", auditor_node)

    graph.set_entry_point("router")

    def route_decision(state: AgentState):
        intent = state.get("intent", "HYBRID_ANALYSIS")
        if intent == "SECURITY_BLOCKED":
            return "auditor"
        elif intent == "STRUCTURED_BI":
            return "bi_agent"
        elif intent == "UNSTRUCTURED_RAG":
            return "rag_agent"
        else:
            return "bi_agent" # In hybrid mode, first execute BI then RAG

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "auditor": "auditor",
            "bi_agent": "bi_agent",
            "rag_agent": "rag_agent"
        }
    )

    def after_bi(state: AgentState):
        intent = state.get("intent")
        if intent == "HYBRID_ANALYSIS":
            return "rag_agent"
        return "synthesizer"

    graph.add_conditional_edges("bi_agent", after_bi, {"rag_agent": "rag_agent", "synthesizer": "synthesizer"})
    graph.add_edge("rag_agent", "synthesizer")
    graph.add_edge("synthesizer", "auditor")
    graph.add_edge("auditor", END)

    return graph.compile()


class EnterpriseAgentOrchestrator:
    def __init__(self):
        self.app = build_agent_graph()
        self.cache = SemanticCache()

    def run(self, user_query: str, security_context) -> AgentState:
        start_time = time.time()
        tenant_id = security_context.tenant_id
        clearance = security_context.security_clearance

        # 1. FinOps Semantic Caching Check (Target P95 < 100ms)
        cached_result = self.cache.get_cache(user_query, tenant_id, clearance)
        if cached_result:
            latency = round((time.time() - start_time) * 1000, 2)
            cached_result["latency_ms"] = latency
            cached_result["cache_hit"] = True
            cached_result["execution_trace"] = [
                f"FinOps Semantic Cache: HIT ({latency} ms) for Tenant '{tenant_id}'."
            ]
            return cached_result

        # 2. Execute Multi-Agent Graph
        initial_state: AgentState = {
            "user_query": user_query,
            "security_context": security_context,
            "intent": "",
            "sql_guardrail_passed": False,
            "semantic_result": None,
            "rag_result": None,
            "final_answer": None,
            "structured_citations": [],
            "execution_trace": ["Orchestrator: Initiating Agent StateGraph execution"],
            "latency_ms": 0.0,
            "cache_hit": False
        }

        final_state = self.app.invoke(initial_state)
        latency = round((time.time() - start_time) * 1000, 2)
        final_state["latency_ms"] = latency

        # 3. Cache successful results
        if final_state.get("sql_guardrail_passed") and final_state.get("final_answer"):
            self.cache.set_cache(user_query, tenant_id, clearance, final_state)

        return final_state
