"""
Authentication & Multi-Tenant Persona Context Provider.
Generates and verifies JWT tokens carrying security claims:
- user_id, tenant_id, role, department, security_clearance
"""

import os
import datetime
import jwt
from typing import Dict, Any, Optional
from pydantic import BaseModel
from src.semantic.cube_client import SecurityContext


JWT_SECRET = os.getenv("JWT_SECRET_KEY", "enterprise_jwt_secret_key_change_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Predefined Enterprise Personas for Instant Switching & Testing
PREDEFINED_PERSONAS = {
    "admin": SecurityContext(
        user_id="usr_admin_01",
        tenant_id="GLOBAL_TENANT",
        role="admin",
        department="EXECUTIVE",
        security_clearance="RESTRICTED"
    ),
    "sales_north": SecurityContext(
        user_id="usr_sales_north_02",
        tenant_id="VN_DIST_NORTH",
        role="sales_manager",
        department="SALES",
        security_clearance="CONFIDENTIAL"
    ),
    "sales_south": SecurityContext(
        user_id="usr_sales_south_03",
        tenant_id="VN_DIST_SOUTH",
        role="sales_manager",
        department="SALES",
        security_clearance="CONFIDENTIAL"
    ),
    "warehouse_operator": SecurityContext(
        user_id="usr_wh_04",
        tenant_id="GLOBAL_TENANT",
        role="operator",
        department="WAREHOUSE",
        security_clearance="INTERNAL"
    ),
    "guest_auditor": SecurityContext(
        user_id="usr_guest_05",
        tenant_id="VN_DIST_NORTH",
        role="guest",
        department="SALES",
        security_clearance="PUBLIC"
    )
}


def create_access_token(security_context: SecurityContext, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates signed JWT token with security claims."""
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(hours=8))
    to_encode = {
        "sub": security_context.user_id,
        "tenant_id": security_context.tenant_id,
        "role": security_context.role,
        "department": security_context.department,
        "security_clearance": security_context.security_clearance,
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> SecurityContext:
    """Decodes and validates JWT token into SecurityContext."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return SecurityContext(
            user_id=payload.get("sub", "anonymous"),
            tenant_id=payload.get("tenant_id", "GLOBAL_TENANT"),
            role=payload.get("role", "guest"),
            department=payload.get("department", "GENERAL"),
            security_clearance=payload.get("security_clearance", "PUBLIC")
        )
    except jwt.PyJWTError as e:
        raise PermissionError(f"Invalid JWT Token: {e}")
