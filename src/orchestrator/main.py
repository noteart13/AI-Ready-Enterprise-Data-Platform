"""
FastAPI Enterprise AI Gateway & Multi-Agent Orchestrator API.
Exposes REST endpoints for NLQ chat, Persona switching, and Semantic Catalog queries.
"""

from typing import Dict, Any, Optional
import os
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.orchestrator.security.auth import (
    PREDEFINED_PERSONAS, create_access_token, decode_access_token
)
from src.semantic.cube_client import SecurityContext, SemanticLayerClient
from src.orchestrator.graph.workflow import EnterpriseAgentOrchestrator
from src.orchestrator.cache.semantic_cache import SemanticCache


app = FastAPI(
    title="AI-Ready Enterprise Data Platform API",
    version="1.0.0",
    description="Unified Data Platform API serving BI Metrics, Natural Language Queries, and Multi-Agent Orchestration."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = EnterpriseAgentOrchestrator()
semantic_client = SemanticLayerClient()
cache = SemanticCache()


class ChatRequest(BaseModel):
    query: str
    persona: Optional[str] = "admin" # Convenience parameter if token is not sent directly


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str
    department: str
    security_clearance: str


def get_current_security_context(
    authorization: Optional[str] = Header(None),
    x_persona: Optional[str] = Header(None)
) -> SecurityContext:
    # 1. Bearer Token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            return decode_access_token(token)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # 2. Persona Header fallback
    if x_persona and x_persona in PREDEFINED_PERSONAS:
        return PREDEFINED_PERSONAS[x_persona]

    # Default to admin persona for development convenience
    return PREDEFINED_PERSONAS["admin"]


@app.get("/api/v1/health")
def healthcheck():
    return {
        "status": "HEALTHY",
        "service": "AI-Ready Enterprise Data Platform",
        "version": "1.0.0"
    }


@app.get("/3d", response_class=HTMLResponse)
def get_3d_portal():
    """Serves full-screen 3D Three.js WebGL Lakehouse & Multi-Agent Universe."""
    path_3d = os.path.join(os.path.dirname(__file__), "..", "ui", "static", "lakehouse_3d.html")
    if os.path.exists(path_3d):
        with open(path_3d, "r", encoding="utf-8") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="3D WebGL asset not found")


@app.get("/api/v1/personas")
def get_personas():
    """Lists available personas for instant UI role switching."""
    return {
        k: {
            "user_id": v.user_id,
            "tenant_id": v.tenant_id,
            "role": v.role,
            "department": v.department,
            "security_clearance": v.security_clearance
        }
        for k, v in PREDEFINED_PERSONAS.items()
    }


@app.post("/api/v1/auth/token/{persona_name}", response_model=TokenResponse)
def generate_token_for_persona(persona_name: str):
    """Issues signed JWT token for a chosen persona."""
    if persona_name not in PREDEFINED_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{persona_name}' not found. Available: {list(PREDEFINED_PERSONAS.keys())}"
        )
    sec = PREDEFINED_PERSONAS[persona_name]
    token = create_access_token(sec)
    return TokenResponse(
        access_token=token,
        user_id=sec.user_id,
        tenant_id=sec.tenant_id,
        role=sec.role,
        department=sec.department,
        security_clearance=sec.security_clearance
    )


@app.get("/api/v1/metrics/catalog")
def get_metrics_catalog():
    """Returns single source of truth Metrics-as-Code catalog."""
    return semantic_client.get_metrics_catalog()


@app.post("/api/v1/chat")
def chat(
    request: ChatRequest,
    sec: SecurityContext = Depends(get_current_security_context)
):
    """
    Main Natural Language Query & Multi-Agent endpoint.
    Orchestrates Router, BI Agent, RAG Agent, Synthesizer, and Auditor.
    """
    # 1. FinOps Token Bucket Rate Limiting
    is_allowed, remaining = cache.check_rate_limit(sec.user_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FinOps Rate Limit Exceeded: Đã vượt quá số lượng truy vấn cho phép trong 1 phút."
        )

    # 2. Override persona if explicitly requested in body and no custom bearer token provided
    if request.persona and request.persona in PREDEFINED_PERSONAS:
        sec = PREDEFINED_PERSONAS[request.persona]

    # 3. Execute Orchestrator
    result = orchestrator.run(user_query=request.query, security_context=sec)

    return {
        "query": request.query,
        "persona_used": {
            "user_id": sec.user_id,
            "tenant_id": sec.tenant_id,
            "role": sec.role,
            "department": sec.department,
            "security_clearance": sec.security_clearance
        },
        "intent": result.get("intent"),
        "answer": result.get("final_answer"),
        "structured_citations": result.get("structured_citations", []),
        "semantic_data": result.get("semantic_result", {}).get("data", []),
        "execution_trace": result.get("execution_trace", []),
        "latency_ms": result.get("latency_ms", 0.0),
        "cache_hit": result.get("cache_hit", False)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
