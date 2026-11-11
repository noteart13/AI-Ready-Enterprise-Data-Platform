"""
Medallion Gold Layer Transformations.
Handles:
1. Structured Star Schema: fact_orders, dim_customers, dim_products, fact_sla_performance
2. Unstructured Deterministic Chunking: chunk_id hashing, embed_model tracking, delta lake persistence
3. High-Performance DuckDB Sync: creates lakehouse.duckdb for Cube Semantic Layer queries.
"""

import os
import re
import json
import hashlib
import duckdb
import pandas as pd
from deltalake import DeltaTable, write_deltalake


class GoldTransformer:
    def __init__(self, lakehouse_base: str = "./data/lakehouse"):
        self.lakehouse_base = lakehouse_base
        self.gold_path = f"{lakehouse_base}/gold"
        os.makedirs(self.gold_path, exist_ok=True)

    def run_all(self):
        print("[Gold] Running Gold transformations...")
        self.build_structured_star_schema()
        self.build_unstructured_deterministic_chunks()
        self.sync_gold_to_duckdb()
        print("[Gold] All Gold transformations and DuckDB sync completed successfully!")

    def build_structured_star_schema(self):
        silver_cust = DeltaTable(f"{self.lakehouse_base}/silver/customers_scd2").to_pandas()
        silver_prod = DeltaTable(f"{self.lakehouse_base}/silver/products_scd2").to_pandas()
        silver_orders = DeltaTable(f"{self.lakehouse_base}/silver/orders").to_pandas()
        silver_items = DeltaTable(f"{self.lakehouse_base}/silver/order_items").to_pandas()

        # 1. dim_customers_gold (current active version)
        dim_cust = silver_cust[silver_cust["is_current"] == True].copy()
        write_deltalake(f"{self.gold_path}/dim_customers", dim_cust, mode="overwrite")

        # 2. dim_products_gold
        dim_prod = silver_prod[silver_prod["is_current"] == True].copy()
        write_deltalake(f"{self.gold_path}/dim_products", dim_prod, mode="overwrite")

        # 3. fact_order_items
        write_deltalake(f"{self.gold_path}/fact_order_items", silver_items, mode="overwrite")

        # 4. Enriched fact_orders
        # Compute cost & margin from order items
        merged_items = silver_items.merge(dim_prod[["product_id", "unit_cost"]], on="product_id", how="left")
        merged_items["total_cost"] = merged_items["quantity"] * merged_items["unit_cost"]

        order_cogs = merged_items.groupby("order_id").agg(
            total_cogs=("total_cost", "sum"),
            item_count=("quantity", "sum")
        ).reset_index()

        fact_orders = silver_orders.merge(order_cogs, on="order_id", how="left").fillna(0)
        fact_orders["total_cogs"] = fact_orders["total_cogs"].astype(float)
        fact_orders["gross_profit"] = fact_orders["total_amount"] - fact_orders["total_cogs"]
        fact_orders["gross_margin_pct"] = (fact_orders["gross_profit"] / fact_orders["total_amount"].replace(0, 1) * 100).round(2)
        fact_orders["order_year_month"] = pd.to_datetime(fact_orders["order_date"]).dt.strftime("%Y-%m")

        write_deltalake(f"{self.gold_path}/fact_orders", fact_orders, mode="overwrite")
        print(f"[Gold] fact_orders written: {len(fact_orders)} records.")

        # 5. Aggregate fact_sla_performance
        sla_perf = fact_orders.groupby(["tenant_id", "customer_id", "order_year_month"]).agg(
            total_orders=("order_id", "count"),
            breached_orders=("sla_breached", "sum"),
            total_revenue=("total_amount", "sum"),
            avg_shipping_hours=("shipping_hours", "mean")
        ).reset_index()
        sla_perf["sla_breach_rate_pct"] = ((sla_perf["breached_orders"] / sla_perf["total_orders"]) * 100).round(2)
        sla_perf["sla_compliance_rate_pct"] = (100.0 - sla_perf["sla_breach_rate_pct"]).round(2)

        write_deltalake(f"{self.gold_path}/fact_sla_performance", sla_perf, mode="overwrite")
        print(f"[Gold] fact_sla_performance written: {len(sla_perf)} records.")

    def build_unstructured_deterministic_chunks(self):
        docs_df = DeltaTable(f"{self.lakehouse_base}/silver/normalized_documents").to_pandas()
        chunks = []

        for _, doc in docs_df.iterrows():
            doc_id = doc["doc_id"]
            file_name = doc["file_name"]
            tenant_id = doc["tenant_id"]
            dept = doc["department"]
            sec_acl = doc["security_acl"]
            pages = json.loads(doc["pages_json"]) if isinstance(doc["pages_json"], str) else doc["pages_json"]
            metadata = json.loads(doc["metadata_json"]) if isinstance(doc["metadata_json"], str) else doc["metadata_json"]

            for page in pages:
                page_no = page.get("page_no", 1)
                page_text = page.get("text", "")
                
                # Split into semantic paragraph blocks
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if len(p.strip()) > 30]
                if not paragraphs:
                    paragraphs = [page_text.strip()] if page_text.strip() else []

                for chunk_idx, p_text in enumerate(paragraphs):
                    # Deterministic hash ID
                    raw_id_seed = f"{doc_id}_{page_no}_{chunk_idx}_{p_text[:40]}"
                    chunk_id = f"chk_{hashlib.sha256(raw_id_seed.encode('utf-8')).hexdigest()[:16]}"

                    chunks.append({
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "file_name": file_name,
                        "page_no": int(page_no),
                        "chunk_index": int(chunk_idx),
                        "chunk_text": p_text,
                        "tenant_id": tenant_id,
                        "department": dept,
                        "security_acl": sec_acl,
                        "embed_model": "text-embedding-3-small",
                        "metadata_json": json.dumps(metadata, ensure_ascii=False),
                        "_gold_processed_at": pd.Timestamp.utcnow()
                    })

        chunks_df = pd.DataFrame(chunks)
        write_deltalake(f"{self.gold_path}/rag_chunks", chunks_df, mode="overwrite")
        print(f"[Gold] rag_chunks: {len(chunks_df)} deterministic chunks generated and persisted.")

    def sync_gold_to_duckdb(self):
        duck_file = f"{self.gold_path}/lakehouse.duckdb"
        con = duckdb.connect(duck_file)

        tables = ["fact_orders", "dim_customers", "dim_products", "fact_order_items", "fact_sla_performance"]
        for tbl in tables:
            df = DeltaTable(f"{self.gold_path}/{tbl}").to_pandas()
            con.execute(f"CREATE OR REPLACE TABLE {tbl} AS SELECT * FROM df")

        # Create convenience semantic views in DuckDB
        con.execute("""
            CREATE OR REPLACE VIEW v_monthly_metrics AS
            SELECT 
                order_year_month,
                tenant_id,
                COUNT(order_id) as total_orders,
                ROUND(SUM(total_amount), 2) as net_revenue,
                ROUND(SUM(gross_profit), 2) as gross_profit,
                ROUND(AVG(gross_margin_pct), 2) as avg_gross_margin_pct,
                SUM(sla_breached) as sla_breached_count,
                ROUND(AVG(shipping_hours), 1) as avg_delivery_hours
            FROM fact_orders
            GROUP BY order_year_month, tenant_id
            ORDER BY order_year_month DESC
        """)

        con.close()
        print(f"[Gold] Exported and synced Gold tables to DuckDB catalog: {duck_file}")


if __name__ == "__main__":
    transformer = GoldTransformer()
    transformer.run_all()
