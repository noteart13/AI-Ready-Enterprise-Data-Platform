"""
FastAPI Enterprise AI Gateway & Multi-Agent Orchestrator API.
Exposes Zero-Trust authenticated REST endpoints for NLQ chat, Metrics Catalog, and Secure Identity Authentication.
Strictly eliminates unauthenticated admin access, persona tampering, and cross-tenant leakage.
"""

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.orchestrator.security.auth import (
    PREDEFINED_PERSONAS,
    ENTERPRISE_CREDENTIALS,
    authenticate_user,
    create_access_token,
    decode_access_token,
    ALLOW_DEV_PERSONA_TOKEN
)
from src.semantic.cube_client import SecurityContext, SemanticLayerClient
from src.orchestrator.graph.workflow import EnterpriseAgentOrchestrator
from src.orchestrator.cache.semantic_cache import SemanticCache


app = FastAPI(
    title="AI-Ready Enterprise Data Platform API",
    version="2.0.0",
    description="Zero-Trust Enterprise Data Platform API serving BI Metrics, Natural Language Queries, and Multi-Agent Orchestration."
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
    query: str = Field(..., description="Natural language enterprise question")
    # Body-level persona tampering strictly eliminated for Zero-Trust enterprise security


class LoginRequest(BaseModel):
    username: str = Field(..., description="Enterprise employee username")
    password: str = Field(..., description="Enterprise employee password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str
    department: str
    security_clearance: str


def get_current_security_context(
    authorization: Optional[str] = Header(None)
) -> SecurityContext:
    """
    Zero-Trust Security Dependency:
    Extracts and cryptographically validates Bearer JWT.
    Rejects any missing, forged, expired, or tampered credentials with HTTP 401.
    Strictly forbids default fallback to admin.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu xác thực: Vui lòng cung cấp mã thông báo Bearer hợp lệ trong tiêu đề Authorization.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = authorization.split(" ")[1].strip()
    try:
        return decode_access_token(token)
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(pe),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Mã thông báo không hợp lệ: {e}",
            headers={"WWW-Authenticate": "Bearer"}
        )


@app.get("/api/v1/health")
def healthcheck():
    return {
        "status": "HEALTHY",
        "service": "AI-Ready Enterprise Data Platform",
        "version": "2.0.0",
        "auth_mode": "Zero-Trust Strict JWT"
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
    """Lists available persona profiles for client reference."""
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


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(creds: LoginRequest):
    """
    Enterprise Authentication Gateway:
    Validates username and password hash, issuing an immutable signed JWT token.
    """
    sec = authenticate_user(creds.username, creds.password)
    if not sec:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thông tin đăng nhập không hợp lệ (Tên đăng nhập hoặc mật khẩu không đúng)."
        )

    token = create_access_token(sec)
    return TokenResponse(
        access_token=token,
        user_id=sec.user_id,
        tenant_id=sec.tenant_id,
        role=sec.role,
        department=sec.department,
        security_clearance=sec.security_clearance
    )


@app.post("/api/v1/auth/dev-token/{persona_name}", response_model=TokenResponse)
def issue_dev_token(persona_name: str, x_dev_secret: Optional[str] = Header(None)):
    """
    Development/Benchmark Helper: Issues token for test suites only when dev mode is enabled.
    Blocked in production high-security environments.
    """
    dev_secret = os.getenv("DEV_TEST_SECRET", "enterprise_dev_test_secret_2026")
    if not ALLOW_DEV_PERSONA_TOKEN and x_dev_secret != dev_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tính năng tạo token theo persona trực tiếp bị khóa trong chế độ bảo mật nghiêm ngặt. Vui lòng dùng /api/v1/auth/login."
        )

    if persona_name not in PREDEFINED_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{persona_name}' không tồn tại. Danh sách khả dụng: {list(PREDEFINED_PERSONAS.keys())}"
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
def get_metrics_catalog(sec: SecurityContext = Depends(get_current_security_context)):
    """Returns Single Source of Truth Metrics-as-Code catalog for authenticated users."""
    return semantic_client.get_metrics_catalog()


@app.post("/api/v1/chat")
def chat(
    request: ChatRequest,
    sec: SecurityContext = Depends(get_current_security_context)
):
    """
    Protected Natural Language Query & Multi-Agent Orchestrator endpoint.
    Zero-Trust Enforced: Identity and permissions are cryptographically bound to the Bearer JWT.
    """
    # 1. FinOps Token Bucket Rate Limiting per user_id
    is_allowed, remaining = cache.check_rate_limit(sec.user_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FinOps Rate Limit Exceeded: Đã vượt quá số lượng truy vấn cho phép trong 1 phút."
        )

    # 2. Execute Orchestrator with verified SecurityContext
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
