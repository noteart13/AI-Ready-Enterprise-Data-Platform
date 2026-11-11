"""
Structured BI Sub-Agent.
Queries the Unified Semantic Layer using predefined Metrics-as-Code.
Enforces Row-Level Security and prevents SQL metric hallucination.
"""

from src.orchestrator.graph.state import AgentState
from src.semantic.cube_client import SemanticLayerClient


def bi_agent_node(state: AgentState) -> AgentState:
    trace = state.get("execution_trace", [])
    query = state["user_query"].lower()
    sec = state["security_context"]

    trace.append(f"BI Agent: Invoking Semantic Layer with RLS Context (Tenant: {sec.tenant_id}, Dept: {sec.department})...")

    # Select semantic metrics based on query intent
    measures = ["Orders.orderCount", "Orders.netRevenue"]
    dimensions = []

    if any(k in query for k in ["lợi nhuận", "profit", "margin"]):
        measures.append("Orders.grossProfit")

    if any(k in query for k in ["sla", "trễ", "chậm", "giao hàng", "breach", "cam kết"]):
        measures.extend(["Orders.slaBreachedCount", "Orders.slaBreachRate", "Orders.avgShippingHours"])

    if any(k in query for k in ["tháng", "năm", "thời gian", "kỳ", "xu hướng", "trend", "month"]):
        dimensions.append("Orders.orderYearMonth")

    if any(k in query for k in ["khách hàng", "đối tác", "customer", "đại lý"]):
        dimensions.append("Customers.companyName")

    # Deduplicate measures
    measures = list(dict.fromkeys(measures))

    try:
        client = SemanticLayerClient()
        result = client.query(
            measures=measures,
            dimensions=dimensions,
            security_context=sec
        )
        state["semantic_result"] = result
        trace.append(f"BI Agent: Received {result.get('row_count', 0)} rows from {result.get('source')}")
    except PermissionError as pe:
        trace.append(f"BI Agent: Permission Denied! {pe}")
        state["semantic_result"] = {"error": str(pe), "data": []}
    except Exception as e:
        trace.append(f"BI Agent: Error querying semantic layer: {e}")
        state["semantic_result"] = {"error": str(e), "data": []}

    state["execution_trace"] = trace
    return state
