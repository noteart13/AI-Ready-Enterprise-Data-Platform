"""
Data Quality Gate (Pandera Schemas + DuckDB SQL Assertions).
Validates Silver tables before allowing publication to Gold consumption tier.
Checks:
- Schema conformance & types
- Nullability & domain ranges
- Referential Integrity (Foreign Keys)
- Document security_acl classification values
"""

import json
import duckdb
import pandas as pd
import pandera.pandas as pa
from pandera import Column, Check, DataFrameSchema
from deltalake import DeltaTable


class DataQualityError(Exception):
    pass


class DataQualityGate:
    def __init__(self, lakehouse_base: str = "./data/lakehouse"):
        self.lakehouse_base = lakehouse_base
        self.duck_conn = duckdb.connect(":memory:")

    def get_pandera_schemas(self):
        orders_schema = DataFrameSchema({
            "order_id": Column(str, nullable=False),
            "order_number": Column(str, nullable=False),
            "customer_id": Column(str, nullable=False),
            "tenant_id": Column(str, nullable=False),
            "status": Column(str, Check.isin(["DELIVERED", "SHIPPED", "CANCELLED", "RETURNED"])),
            "total_amount": Column(float, Check.greater_than_or_equal_to(0.0)),
            "shipping_hours": Column(int, Check.greater_than_or_equal_to(0)),
            "sla_target_hours": Column(int, Check.greater_than(0)),
            "sla_breached": Column(int, Check.isin([0, 1]))
        })

        customers_schema = DataFrameSchema({
            "customer_sk": Column(str, nullable=False),
            "customer_id": Column(str, nullable=False),
            "company_name": Column(str, nullable=False),
            "tier": Column(str, Check.isin(["VIP", "TIER_1", "TIER_2", "STANDARD"])),
            "tenant_id": Column(str, nullable=False),
            "credit_limit": Column(float, Check.greater_than_or_equal_to(0.0)),
            "is_current": Column(bool)
        })

        documents_schema = DataFrameSchema({
            "doc_id": Column(str, nullable=False),
            "tenant_id": Column(str, nullable=False),
            "security_acl": Column(str, Check.isin(["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"])),
            "department": Column(str, nullable=False)
        })

        return orders_schema, customers_schema, documents_schema

    def run_pandera_checks(self) -> dict:
        print("[Quality Gate] Running Pandera Schema validations...")
        orders_schema, customers_schema, docs_schema = self.get_pandera_schemas()
        results = {}

        # 1. Orders
        orders_df = DeltaTable(f"{self.lakehouse_base}/silver/orders").to_pandas()
        try:
            orders_schema.validate(orders_df)
            results["orders_schema"] = {"status": "PASSED", "records": len(orders_df)}
        except pa.errors.SchemaError as e:
            results["orders_schema"] = {"status": "FAILED", "error": str(e)}

        # 2. Customers
        cust_df = DeltaTable(f"{self.lakehouse_base}/silver/customers_scd2").to_pandas()
        try:
            customers_schema.validate(cust_df)
            results["customers_schema"] = {"status": "PASSED", "records": len(cust_df)}
        except pa.errors.SchemaError as e:
            results["customers_schema"] = {"status": "FAILED", "error": str(e)}

        # 3. Documents
        docs_df = DeltaTable(f"{self.lakehouse_base}/silver/normalized_documents").to_pandas()
        try:
            docs_schema.validate(docs_df)
            results["documents_schema"] = {"status": "PASSED", "records": len(docs_df)}
        except pa.errors.SchemaError as e:
            results["documents_schema"] = {"status": "FAILED", "error": str(e)}

        return results

    def run_duckdb_sql_assertions(self) -> dict:
        print("[Quality Gate] Running DuckDB SQL Referential Integrity Assertions...")
        
        # Load silver tables into in-memory DuckDB
        orders_df = DeltaTable(f"{self.lakehouse_base}/silver/orders").to_pandas()
        customers_df = DeltaTable(f"{self.lakehouse_base}/silver/customers_scd2").to_pandas()
        items_df = DeltaTable(f"{self.lakehouse_base}/silver/order_items").to_pandas()
        products_df = DeltaTable(f"{self.lakehouse_base}/silver/products_scd2").to_pandas()

        self.duck_conn.register("silver_orders", orders_df)
        self.duck_conn.register("silver_customers", customers_df)
        self.duck_conn.register("silver_items", items_df)
        self.duck_conn.register("silver_products", products_df)

        assertions = [
            {
                "name": "check_no_orphaned_orders",
                "sql": """
                    SELECT count(*) as violation_count 
                    FROM silver_orders o 
                    LEFT JOIN silver_customers c ON o.customer_id = c.customer_id 
                    WHERE c.customer_id IS NULL
                """,
                "expected": 0
            },
            {
                "name": "check_no_orphaned_order_items",
                "sql": """
                    SELECT count(*) as violation_count 
                    FROM silver_items i 
                    LEFT JOIN silver_orders o ON i.order_id = o.order_id 
                    WHERE o.order_id IS NULL
                """,
                "expected": 0
            },
            {
                "name": "check_item_product_integrity",
                "sql": """
                    SELECT count(*) as violation_count 
                    FROM silver_items i 
                    LEFT JOIN silver_products p ON i.product_id = p.product_id 
                    WHERE p.product_id IS NULL
                """,
                "expected": 0
            },
            {
                "name": "check_positive_quantities_and_amounts",
                "sql": """
                    SELECT count(*) as violation_count 
                    FROM silver_items 
                    WHERE quantity <= 0 OR unit_price < 0 OR discount_rate < 0 OR discount_rate > 1.0
                """,
                "expected": 0
            }
        ]

        sql_results = {}
        for a in assertions:
            df_res = self.duck_conn.execute(a["sql"]).df()
            violations = int(df_res["violation_count"].iloc[0])
            passed = violations == a["expected"]
            sql_results[a["name"]] = {
                "status": "PASSED" if passed else "FAILED",
                "violations": violations,
                "expected": a["expected"]
            }

        return sql_results

    def validate_gate(self) -> dict:
        pandera_res = self.run_pandera_checks()
        sql_res = self.run_duckdb_sql_assertions()

        all_passed = (
            all(v.get("status") == "PASSED" for v in pandera_res.values()) and
            all(v.get("status") == "PASSED" for v in sql_res.values())
        )

        report = {
            "overall_status": "PASSED" if all_passed else "FAILED",
            "pandera_checks": pandera_res,
            "sql_assertions": sql_res
        }

        print("\n" + "="*50)
        print("DATA QUALITY GATE REPORT")
        print("="*50)
        print(json.dumps(report, indent=2))
        print("="*50 + "\n")

        if not all_passed:
            raise DataQualityError(f"Data Quality Gate failed! Report: {report}")

        return report


if __name__ == "__main__":
    gate = DataQualityGate()
    gate.validate_gate()
