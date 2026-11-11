"""
Unified Semantic Layer Client (Cube Core + High-Performance Local DuckDB Compiler).
Guarantees Metric Consistency (Single Source of Truth) and Dynamic Row-Level Security (RLS).
Prevents LLM metric hallucination by compiling predefined Metrics-as-Code.
"""

import os
import duckdb
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class SecurityContext(BaseModel):
    user_id: str = "usr_admin"
    tenant_id: str = "GLOBAL_TENANT"
    role: str = "admin"
    department: str = "EXECUTIVE"
    security_clearance: str = "RESTRICTED" # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED


class SemanticLayerClient:
    def __init__(
        self,
        cube_api_url: Optional[str] = None,
        cube_secret: Optional[str] = None,
        duckdb_path: str = "./data/lakehouse/gold/lakehouse.duckdb"
    ):
        self.cube_api_url = cube_api_url or os.getenv("CUBE_API_URL", "http://localhost:4000/cubejs-api/v1")
        self.cube_secret = cube_secret or os.getenv("CUBE_API_SECRET", "enterprise_super_secret_cube_token_2026")
        self.duckdb_path = duckdb_path

        # Semantic Metrics Definition Dictionary (Metrics-as-Code)
        self.catalog = {
            "cubes": {
                "Orders": {
                    "measures": {
                        "Orders.orderCount": {"sql": "COUNT(o.order_id)", "title": "Total Orders"},
                        "Orders.netRevenue": {"sql": "ROUND(SUM(o.total_amount), 2)", "title": "Net Revenue ($)"},
                        "Orders.grossProfit": {"sql": "ROUND(SUM(o.gross_profit), 2)", "title": "Gross Profit ($)"},
                        "Orders.averageOrderValue": {"sql": "ROUND(AVG(o.total_amount), 2)", "title": "Average Order Value ($)"},
                        "Orders.avgShippingHours": {"sql": "ROUND(AVG(o.shipping_hours), 1)", "title": "Avg Delivery Hours"},
                        "Orders.slaBreachedCount": {"sql": "SUM(o.sla_breached)", "title": "SLA Breached Orders"},
                        "Orders.slaBreachRate": {
                            "sql": "ROUND(SUM(o.sla_breached) * 100.0 / NULLIF(COUNT(o.order_id), 0), 2)",
                            "title": "SLA Breach Rate (%)"
                        }
                    },
                    "dimensions": {
                        "Orders.orderId": "o.order_id",
                        "Orders.orderNumber": "o.order_number",
                        "Orders.customerId": "o.customer_id",
                        "Orders.tenantId": "o.tenant_id",
                        "Orders.status": "o.status",
                        "Orders.orderYearMonth": "o.order_year_month",
                        "Orders.slaBreached": "o.sla_breached"
                    }
                },
                "Customers": {
                    "measures": {
                        "Customers.count": {"sql": "COUNT(DISTINCT c.customer_id)", "title": "Total Customers"}
                    },
                    "dimensions": {
                        "Customers.customerId": "c.customer_id",
                        "Customers.companyName": "c.company_name",
                        "Customers.tier": "c.tier",
                        "Customers.tenantId": "c.tenant_id",
                        "Customers.region": "c.region",
                        "Customers.creditLimit": "c.credit_limit"
                    }
                },
                "Products": {
                    "measures": {
                        "Products.count": {"sql": "COUNT(DISTINCT p.product_id)", "title": "Total SKUs"},
                        "Products.totalInventoryUnits": {"sql": "SUM(p.stock_quantity)", "title": "Total Inventory Units"}
                    },
                    "dimensions": {
                        "Products.productId": "p.product_id",
                        "Products.sku": "p.sku",
                        "Products.productName": "p.product_name",
                        "Products.category": "p.category",
                        "Products.unitPrice": "p.unit_price"
                    }
                }
            }
        }

    def get_metrics_catalog(self) -> Dict[str, Any]:
        """Returns catalog of all authorized business measures and dimensions."""
        catalog_summary = {}
        for cube_name, cube_def in self.catalog["cubes"].items():
            catalog_summary[cube_name] = {
                "measures": [
                    {"name": k, "title": v["title"]} 
                    for k, v in cube_def["measures"].items()
                ],
                "dimensions": list(cube_def["dimensions"].keys())
            }
        return catalog_summary

    def query(
        self,
        measures: List[str],
        dimensions: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        security_context: Optional[SecurityContext] = None
    ) -> Dict[str, Any]:
        """
        Executes semantic query.
        Tries Cube REST API first; if unavailable, falls back to direct DuckDB semantic compilation.
        Enforces Row-Level Security (RLS) and department permissions.
        """
        sec = security_context or SecurityContext()
        dimensions = dimensions or []
        filters = filters or []

        # 1. Check Department & Role RBAC Restrictions (Zero-Trust)
        restricted_financial_measures = ["Orders.netRevenue", "Orders.grossProfit", "Orders.averageOrderValue"]
        if (sec.department == "WAREHOUSE" or sec.role == "guest") and any(m in restricted_financial_measures for m in measures):
            raise PermissionError(
                f"Truy vấn bị từ chối: Vai trò '{sec.role}' / Phòng ban '{sec.department}' không có quyền truy cập chỉ số tài chính & doanh thu."
            )

        # 2. Try remote Cube API if available
        try:
            headers = {
                "Authorization": self.cube_secret,
                "x-tenant-id": sec.tenant_id,
                "x-role": sec.role,
                "x-security-clearance": sec.security_clearance
            }
            payload = {
                "query": {
                    "measures": measures,
                    "dimensions": dimensions,
                    "filters": filters
                }
            }
            resp = requests.post(f"{self.cube_api_url}/load", json=payload, headers=headers, timeout=0.2)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return {
                    "source": "Cube-REST-API",
                    "tenant_id": sec.tenant_id,
                    "measures": measures,
                    "dimensions": dimensions,
                    "data": data,
                    "row_count": len(data)
                }
        except Exception:
            # Fallback to local DuckDB Semantic Engine
            pass

        # 3. Local DuckDB Semantic Engine with Dynamic RLS
        return self._execute_duckdb_semantic(measures, dimensions, filters, sec)

    def _execute_duckdb_semantic(
        self,
        measures: List[str],
        dimensions: List[str],
        filters: List[Dict[str, Any]],
        sec: SecurityContext
    ) -> Dict[str, Any]:
        from src.orchestrator.security.ast_guardrails import SQLASTGuardrail

        if not os.path.exists(self.duckdb_path):
            raise FileNotFoundError(f"Gold DuckDB not found: {self.duckdb_path}. Please run lakehouse transforms first.")

        con = duckdb.connect(self.duckdb_path, read_only=True)

        # Build Select expressions
        select_exprs = []
        group_by_indices = []
        idx = 1

        for d in dimensions:
            dim_expr = self._resolve_dimension(d)
            col_alias = d.replace(".", "_")
            select_exprs.append(f"{dim_expr} AS {col_alias}")
            group_by_indices.append(str(idx))
            idx += 1

        for m in measures:
            meas_expr = self._resolve_measure(m)
            col_alias = m.replace(".", "_")
            select_exprs.append(f"{meas_expr} AS {col_alias}")
            idx += 1

        # Parameterized Where clauses to eliminate SQL injection and guarantee Tenant Isolation
        where_clauses = ["1=1"]
        params: List[Any] = []

        # Enforce Row-Level Security (RLS) on tenant_id
        if sec.tenant_id != "GLOBAL_TENANT":
            where_clauses.append("o.tenant_id = ?")
            params.append(sec.tenant_id)

        # Apply user filters with strict parameterization and tenant boundary validation
        for f in filters:
            dim = f.get("member")
            op = f.get("operator", "equals")
            vals = f.get("values", [])
            resolved_dim = self._resolve_dimension(dim)

            # Strict Tenant Isolation Defense: Block cross-tenant exfiltration via filters
            if dim in ("Orders.tenantId", "Customers.tenantId") and sec.tenant_id != "GLOBAL_TENANT":
                if any(str(v) != sec.tenant_id for v in vals):
                    raise PermissionError(
                        f"Phát hiện hành vi vi phạm phân quyền Tenant Isolation: Người dùng thuộc tenant '{sec.tenant_id}' "
                        f"không được phép truy vấn dữ liệu của tenant khác ({vals})."
                    )
                continue  # Scoped already by mandatory RLS parameter

            if op == "equals" and vals:
                where_clauses.append(f"{resolved_dim} = ?")
                params.append(vals[0])
            elif op == "in" and vals:
                placeholders = ", ".join(["?"] * len(vals))
                where_clauses.append(f"{resolved_dim} IN ({placeholders})")
                params.extend(vals)

        # Assemble full compiled SQL
        select_clause = ", ".join(select_exprs)
        where_clause = " AND ".join(where_clauses)
        group_clause = f" GROUP BY {', '.join(group_by_indices)}" if group_by_indices else ""
        order_clause = f" ORDER BY {group_by_indices[0]} DESC" if group_by_indices else ""

        # Dynamic join construction based on referenced cubes
        joins = ["LEFT JOIN dim_customers c ON o.customer_id = c.customer_id"]
        if any("Products." in x for x in measures + dimensions):
            joins.append("LEFT JOIN fact_order_items i ON o.order_id = i.order_id")
            joins.append("LEFT JOIN dim_products p ON i.product_id = p.product_id")
        join_clause = " ".join(joins)

        sql = f"""
            SELECT {select_clause}
            FROM fact_orders o
            {join_clause}
            WHERE {where_clause}
            {group_clause}
            {order_clause}
        """

        # Pre-execution AST Guardrail verification
        SQLASTGuardrail.validate_sql(sql)

        df = con.execute(sql, params).df()
        con.close()

        records = df.to_dict(orient="records")
        return {
            "source": "DuckDB-Semantic-Engine (Zero-Trust RLS)",
            "tenant_id": sec.tenant_id,
            "compiled_sql": sql.strip(),
            "sql_parameters": [str(p) for p in params],
            "measures": measures,
            "dimensions": dimensions,
            "data": records,
            "row_count": len(records)
        }

    def _resolve_measure(self, measure_name: str) -> str:
        for cube in self.catalog["cubes"].values():
            if measure_name in cube["measures"]:
                return cube["measures"][measure_name]["sql"]
        raise ValueError(f"Unknown semantic measure: {measure_name}")

    def _resolve_dimension(self, dim_name: str) -> str:
        for cube in self.catalog["cubes"].values():
            if dim_name in cube["dimensions"]:
                return cube["dimensions"][dim_name]
        raise ValueError(f"Unknown semantic dimension: {dim_name}")


if __name__ == "__main__":
    client = SemanticLayerClient()
    
    print("Testing Semantic Query for Admin (GLOBAL_TENANT):")
    res_admin = client.query(
        measures=["Orders.orderCount", "Orders.netRevenue", "Orders.slaBreachRate"],
        dimensions=["Orders.tenantId"]
    )
    print(pd.DataFrame(res_admin["data"]))

    print("\nTesting Semantic Query with RLS for Sales North (VN_DIST_NORTH):")
    sec_north = SecurityContext(
        user_id="usr_sales_north",
        tenant_id="VN_DIST_NORTH",
        role="sales_manager",
        department="SALES"
    )
    res_north = client.query(
        measures=["Orders.orderCount", "Orders.netRevenue", "Orders.slaBreachRate"],
        dimensions=["Orders.orderYearMonth"],
        security_context=sec_north
    )
    print(pd.DataFrame(res_north["data"]))
