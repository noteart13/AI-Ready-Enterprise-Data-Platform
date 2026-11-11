"""
SQL AST Guardrails & Anti-Injection Defense using sqlglot.
Enforces Zero-Trust query parsing to prevent SQL Injection, prompt injection escapes,
and unauthorized data mutation commands before execution.
"""

import re
import sqlglot
from sqlglot import exp


class SecurityBreachError(Exception):
    pass


class SQLASTGuardrail:
    FORBIDDEN_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", 
        "GRANT", "REVOKE", "CREATE", "EXEC", "EXECUTE", "XP_CMDSHELL",
        "PG_SLEEP", "BENCHMARK", "INTO OUTFILE", "LOAD_FILE"
    ]

    ALLOWED_TABLES = [
        "fact_orders", "dim_customers", "dim_products", 
        "fact_order_items", "fact_sla_performance", "v_monthly_metrics",
        "o", "c", "p", "i" # aliases
    ]

    @classmethod
    def validate_sql(cls, query_sql: str) -> bool:
        """
        Parses SQL AST and validates:
        1. Purely SELECT statements
        2. No DDL/DML mutation expressions
        3. No comment-based injection bypasses
        4. No subquery escapes to forbidden tables
        """
        if not query_sql or not query_sql.strip():
            raise SecurityBreachError("Empty SQL query is not allowed.")

        # Check raw string for obvious comment injection tricks
        if re.search(r"(--|/\*|\*/|;\s*\w+)", query_sql):
            raise SecurityBreachError("Phát hiện kỹ thuật SQL Injection (Comment bypass hoặc stacked query ';').")

        # Check forbidden keywords
        upper_query = query_sql.upper()
        for kw in cls.FORBIDDEN_KEYWORDS:
            if re.search(r"\b" + kw + r"\b", upper_query):
                raise SecurityBreachError(f"Phát hiện từ khóa nguy hiểm bị cấm: '{kw}'.")

        # Parse AST using sqlglot
        try:
            parsed = sqlglot.parse_one(query_sql, read="duckdb")
        except Exception as e:
            raise SecurityBreachError(f"Cú pháp SQL không hợp lệ hoặc bị lỗi AST: {e}")

        # AST must be a Select expression
        if not isinstance(parsed, exp.Select):
            raise SecurityBreachError(f"Loại câu lệnh không được phép (yêu cầu SELECT thuần túy): {type(parsed).__name__}")

        # Inspect all tables referenced in AST
        tables = [t.name.lower() for t in parsed.find_all(exp.Table) if t.name]
        for tbl in tables:
            if tbl not in cls.ALLOWED_TABLES:
                raise SecurityBreachError(f"Truy cập bảng ngoài danh mục được phép: '{tbl}'.")

        return True
