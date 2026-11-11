"""
Enterprise Observability & Distributed Tracing Module.
Provides structured execution tracing, OpenTelemetry / Langfuse spans,
latency SLA measurement, and FinOps token usage accounting.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, List


logger = logging.getLogger("EnterpriseObservability")
logger.setLevel(logging.INFO)


class AgentExecutionSpan:
    def __init__(self, trace_id: str, span_name: str, parent_span: Optional[str] = None):
        self.trace_id = trace_id
        self.span_name = span_name
        self.parent_span = parent_span
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.metadata: Dict[str, Any] = {}
        self.status: str = "OK"
        self.error: Optional[str] = None

    def set_attribute(self, key: str, value: Any):
        self.metadata[key] = value

    def record_error(self, error: Exception):
        self.status = "ERROR"
        self.error = str(error)

    def finish(self) -> Dict[str, Any]:
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_name": self.span_name,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
            "error": self.error
        }


class PlatformObservability:
    def __init__(self):
        self.langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() in ("true", "1")
        self.langfuse_client = None
        if self.langfuse_enabled:
            try:
                from langfuse import Langfuse
                self.langfuse_client = Langfuse()
            except Exception as e:
                logger.warning(f"Langfuse init failed: {e}. Falling back to structured logging.")

    def start_trace(self, trace_id: str, user_id: str, tenant_id: str, query: str) -> Dict[str, Any]:
        """Initiates an end-to-end multi-agent execution trace."""
        trace_context = {
            "trace_id": trace_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "query": query,
            "start_time": time.time(),
            "spans": []
        }
        if self.langfuse_client:
            try:
                self.langfuse_client.trace(
                    id=trace_id,
                    name="Enterprise Multi-Agent NLQ",
                    user_id=user_id,
                    metadata={"tenant_id": tenant_id, "query": query}
                )
            except Exception:
                pass
        return trace_context

    def record_span(self, trace_context: Dict[str, Any], span: AgentExecutionSpan):
        """Records a completed span in the execution trace."""
        trace_context["spans"].append(span.to_dict())

    def end_trace(self, trace_context: Dict[str, Any], final_answer: str, intent: str, cache_hit: bool) -> Dict[str, Any]:
        """Finalizes the execution trace and computes end-to-end metrics."""
        end_time = time.time()
        total_latency_ms = round((end_time - trace_context["start_time"]) * 1000.0, 2)
        trace_context["total_latency_ms"] = total_latency_ms
        trace_context["intent"] = intent
        trace_context["cache_hit"] = cache_hit

        # Structured JSON logging for Datadog / CloudWatch / ELK Stack
        log_payload = {
            "event": "AI_QUERY_EXECUTION",
            "trace_id": trace_context["trace_id"],
            "user_id": trace_context["user_id"],
            "tenant_id": trace_context["tenant_id"],
            "intent": intent,
            "cache_hit": cache_hit,
            "latency_ms": total_latency_ms,
            "spans_count": len(trace_context["spans"])
        }
        logger.info(json.dumps(log_payload, ensure_ascii=False))
        return trace_context


tracer = PlatformObservability()
