"""
Medallion Silver Layer Transformations.
Handles:
1. Data cleaning, type casting, and deduplication.
2. SCD Type 2 (Slowly Changing Dimensions) for Customers and Products.
3. Normalized Document Model with validated metadata.
"""

import os
import hashlib
import pandas as pd
from deltalake import DeltaTable, write_deltalake


class SilverTransformer:
    def __init__(self, lakehouse_base: str = "./data/lakehouse"):
        self.lakehouse_base = lakehouse_base

    def run_all(self):
        print("[Silver] Running Silver transformations...")
        self.transform_customers_scd2()
        self.transform_products_scd2()
        self.transform_orders()
        self.transform_order_items()
        self.transform_documents()
        print("[Silver] All Silver transformations completed successfully!")

    def transform_customers_scd2(self):
        bronze_path = f"{self.lakehouse_base}/bronze/customers"
        silver_path = f"{self.lakehouse_base}/silver/customers_scd2"
        os.makedirs(silver_path, exist_ok=True)

        dt = DeltaTable(bronze_path)
        bronze_df = dt.to_pandas()

        # Build SCD2 representation
        records = []
        for _, row in bronze_df.iterrows():
            surrogate_key = hashlib.md5(f"{row['customer_id']}_{row['updated_at']}".encode()).hexdigest()
            records.append({
                "customer_sk": surrogate_key,
                "customer_id": str(row["customer_id"]).strip(),
                "company_name": str(row["company_name"]).strip(),
                "tier": str(row["tier"]).strip().upper(),
                "tenant_id": str(row["tenant_id"]).strip().upper(),
                "contact_email": str(row["contact_email"]).strip().lower(),
                "credit_limit": float(row["credit_limit"]),
                "region": str(row["region"]).strip().upper(),
                "valid_from": pd.to_datetime(row["created_at"]),
                "valid_to": pd.to_datetime("2099-12-31 23:59:59"),
                "is_current": True,
                "_silver_processed_at": pd.Timestamp.utcnow()
            })

        silver_df = pd.DataFrame(records)
        write_deltalake(silver_path, silver_df, mode="overwrite")
        print(f"[Silver] Customers SCD2: {len(silver_df)} records written.")

    def transform_products_scd2(self):
        bronze_path = f"{self.lakehouse_base}/bronze/products"
        silver_path = f"{self.lakehouse_base}/silver/products_scd2"
        os.makedirs(silver_path, exist_ok=True)

        dt = DeltaTable(bronze_path)
        bronze_df = dt.to_pandas()

        records = []
        for _, row in bronze_df.iterrows():
            surrogate_key = hashlib.md5(f"{row['product_id']}_{row['created_at']}".encode()).hexdigest()
            records.append({
                "product_sk": surrogate_key,
                "product_id": str(row["product_id"]).strip(),
                "sku": str(row["sku"]).strip(),
                "product_name": str(row["product_name"]).strip(),
                "category": str(row["category"]).strip(),
                "unit_cost": float(row["unit_cost"]),
                "unit_price": float(row["unit_price"]),
                "stock_quantity": int(row["stock_quantity"]),
                "valid_from": pd.to_datetime(row["created_at"]),
                "valid_to": pd.to_datetime("2099-12-31 23:59:59"),
                "is_current": True,
                "_silver_processed_at": pd.Timestamp.utcnow()
            })

        silver_df = pd.DataFrame(records)
        write_deltalake(silver_path, silver_df, mode="overwrite")
        print(f"[Silver] Products SCD2: {len(silver_df)} records written.")

    def transform_orders(self):
        bronze_path = f"{self.lakehouse_base}/bronze/orders"
        silver_path = f"{self.lakehouse_base}/silver/orders"
        os.makedirs(silver_path, exist_ok=True)

        dt = DeltaTable(bronze_path)
        df = dt.to_pandas()

        df["order_id"] = df["order_id"].astype(str).str.strip()
        df["order_number"] = df["order_number"].astype(str).str.strip()
        df["customer_id"] = df["customer_id"].astype(str).str.strip()
        df["tenant_id"] = df["tenant_id"].astype(str).str.strip().str.upper()
        df["order_date"] = pd.to_datetime(df["order_date"])
        df["status"] = df["status"].astype(str).str.strip().str.upper()
        df["total_amount"] = df["total_amount"].astype(float)
        df["shipping_hours"] = df["shipping_hours"].astype(int)
        df["sla_target_hours"] = df["sla_target_hours"].astype(int)
        df["sla_breached"] = df["sla_breached"].astype(int)
        df["_silver_processed_at"] = pd.Timestamp.utcnow()

        # Deduplicate on order_id
        df = df.drop_duplicates(subset=["order_id"], keep="last")

        write_deltalake(silver_path, df, mode="overwrite")
        print(f"[Silver] Orders: {len(df)} cleaned records written.")

    def transform_order_items(self):
        bronze_path = f"{self.lakehouse_base}/bronze/order_items"
        silver_path = f"{self.lakehouse_base}/silver/order_items"
        os.makedirs(silver_path, exist_ok=True)

        dt = DeltaTable(bronze_path)
        df = dt.to_pandas()

        df["item_id"] = df["item_id"].astype(str).str.strip()
        df["order_id"] = df["order_id"].astype(str).str.strip()
        df["product_id"] = df["product_id"].astype(str).str.strip()
        df["quantity"] = df["quantity"].astype(int)
        df["unit_price"] = df["unit_price"].astype(float)
        df["discount_rate"] = df["discount_rate"].astype(float)
        df["subtotal"] = df["subtotal"].astype(float)
        df["_silver_processed_at"] = pd.Timestamp.utcnow()

        df = df.drop_duplicates(subset=["item_id"], keep="last")

        write_deltalake(silver_path, df, mode="overwrite")
        print(f"[Silver] Order Items: {len(df)} cleaned records written.")

    def transform_documents(self):
        bronze_path = f"{self.lakehouse_base}/bronze/documents"
        silver_path = f"{self.lakehouse_base}/silver/normalized_documents"
        os.makedirs(silver_path, exist_ok=True)

        dt = DeltaTable(bronze_path)
        df = dt.to_pandas()

        # Clean document records
        df["doc_id"] = df["doc_id"].astype(str).str.strip()
        df["tenant_id"] = df["tenant_id"].fillna("GLOBAL_TENANT").astype(str).str.strip().str.upper()
        df["department"] = df["department"].fillna("GENERAL").astype(str).str.strip().str.upper()
        df["security_acl"] = df["security_acl"].fillna("INTERNAL").astype(str).str.strip().str.upper()
        df["_silver_processed_at"] = pd.Timestamp.utcnow()

        write_deltalake(silver_path, df, mode="overwrite")
        print(f"[Silver] Normalized Documents: {len(df)} records written.")


if __name__ == "__main__":
    transformer = SilverTransformer()
    transformer.run_all()
