"""
Structured Data Loader (OLTP -> Bronze Delta Lake).
Implements incremental watermark extraction and idempotent append into Delta Lake Bronze.
"""

import os
import sqlite3
import pandas as pd
from deltalake import write_deltalake
from src.ingestion.control_plane import ControlPlane


class StructuredBronzeLoader:
    def __init__(self, oltp_db_path: str = "./data/seed_oltp/oltp_ecommerce.db", lakehouse_base: str = "./data/lakehouse"):
        self.oltp_db_path = oltp_db_path
        self.lakehouse_base = lakehouse_base
        self.control_plane = ControlPlane()

    def ingest_table(self, table_name: str, watermark_col: str = "created_at"):
        run_id = self.control_plane.start_pipeline_run(f"bronze_ingest_{table_name}")
        bronze_table_path = f"{self.lakehouse_base}/bronze/{table_name}"
        os.makedirs(bronze_table_path, exist_ok=True)

        try:
            last_wm = self.control_plane.get_watermark(f"bronze_{table_name}")

            conn = sqlite3.connect(self.oltp_db_path)
            if last_wm:
                query = f"SELECT * FROM {table_name} WHERE {watermark_col} > ? ORDER BY {watermark_col} ASC"
                df = pd.read_sql_query(query, conn, params=(last_wm,))
            else:
                query = f"SELECT * FROM {table_name} ORDER BY {watermark_col} ASC"
                df = pd.read_sql_query(query, conn)
            conn.close()

            count = len(df)
            if count > 0:
                # Add ingestion audit column
                df["_bronze_ingested_at"] = pd.Timestamp.utcnow()

                # Write to Delta table (append mode)
                write_deltalake(
                    bronze_table_path,
                    df,
                    mode="append" if os.path.exists(os.path.join(bronze_table_path, "_delta_log")) else "overwrite"
                )

                new_max_wm = str(df[watermark_col].max())
                self.control_plane.update_watermark(f"bronze_{table_name}", new_max_wm)

                self.control_plane.finish_pipeline_run(
                    run_id=run_id,
                    status="SUCCESS",
                    processed=count,
                    inserted=count,
                    skipped=0
                )
                print(f"[Bronze] Table {table_name}: Ingested {count} new records (Watermark: {new_max_wm})")
            else:
                self.control_plane.finish_pipeline_run(
                    run_id=run_id,
                    status="SUCCESS",
                    processed=0,
                    inserted=0,
                    skipped=0
                )
                print(f"[Bronze] Table {table_name}: No new records found.")

            return count
        except Exception as e:
            self.control_plane.finish_pipeline_run(
                run_id=run_id,
                status="FAILED",
                error_msg=str(e)
            )
            raise e

    def run_all(self):
        tables = [
            ("customers", "updated_at"),
            ("products", "created_at"),
            ("orders", "created_at"),
            ("order_items", "item_id")
        ]
        total = 0
        for tbl, wm_col in tables:
            total += self.ingest_table(tbl, wm_col)
        return total


if __name__ == "__main__":
    loader = StructuredBronzeLoader()
    loader.run_all()
