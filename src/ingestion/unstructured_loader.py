"""
Unstructured Document Loader (Raw Files -> Bronze Delta Lake).
Implements SHA-256 hash checking via file_manifest to guarantee 100% idempotency,
skipping redundant processing and reducing embedding API calls.
"""

import os
import json
import pandas as pd
from pathlib import Path
from deltalake import write_deltalake
from src.ingestion.control_plane import ControlPlane
from src.ingestion.document_parser import DocumentParser


class UnstructuredBronzeLoader:
    def __init__(self, raw_docs_dir: str = "./data/raw_documents", lakehouse_base: str = "./data/lakehouse"):
        self.raw_docs_dir = raw_docs_dir
        self.lakehouse_base = lakehouse_base
        self.control_plane = ControlPlane()
        self.parser = DocumentParser()

    def ingest_documents(self):
        run_id = self.control_plane.start_pipeline_run("bronze_ingest_documents")
        bronze_table_path = f"{self.lakehouse_base}/bronze/documents"
        os.makedirs(bronze_table_path, exist_ok=True)

        inserted = 0
        skipped = 0
        processed_records = []

        try:
            files = [
                os.path.join(self.raw_docs_dir, f)
                for f in os.listdir(self.raw_docs_dir)
                if os.path.isfile(os.path.join(self.raw_docs_dir, f))
            ]

            for file_path in files:
                needs_processing, current_hash, manifest_record = self.control_plane.check_file_status(file_path)

                if not needs_processing:
                    print(f"[Bronze] Skipping unchanged document (Idempotency Hit): {os.path.basename(file_path)}")
                    skipped += 1
                    continue

                print(f"[Bronze] Parsing and ingesting document: {os.path.basename(file_path)} (Hash: {current_hash[:12]}...)")
                parsed = self.parser.parse_file(file_path)

                doc_record = {
                    "doc_id": parsed["metadata"]["contract_code"] or Path(file_path).stem,
                    "file_name": parsed["file_name"],
                    "file_path": parsed["file_path"],
                    "file_type": parsed["file_type"],
                    "content_hash": current_hash,
                    "text_content": parsed["text"],
                    "pages_json": json.dumps(parsed["pages"], ensure_ascii=False),
                    "tables_json": json.dumps(parsed["tables"], ensure_ascii=False),
                    "metadata_json": json.dumps(parsed["metadata"], ensure_ascii=False),
                    "tenant_id": parsed["metadata"]["tenant_id"],
                    "department": parsed["metadata"]["department"],
                    "security_acl": parsed["metadata"]["security_acl"],
                    "_bronze_ingested_at": pd.Timestamp.utcnow()
                }
                processed_records.append(doc_record)
                inserted += 1

                # Update manifest
                self.control_plane.record_file_manifest(
                    file_path=file_path,
                    content_hash=current_hash,
                    status="INGESTED",
                    chunks_count=len(parsed["pages"])
                )

            if processed_records:
                df = pd.DataFrame(processed_records)
                write_deltalake(
                    bronze_table_path,
                    df,
                    mode="append" if os.path.exists(os.path.join(bronze_table_path, "_delta_log")) else "overwrite"
                )

            self.control_plane.finish_pipeline_run(
                run_id=run_id,
                status="SUCCESS",
                processed=len(files),
                inserted=inserted,
                skipped=skipped
            )
            print(f"[Bronze Documents] Completed: {inserted} ingested, {skipped} skipped.")
            return {"inserted": inserted, "skipped": skipped, "total": len(files)}

        except Exception as e:
            self.control_plane.finish_pipeline_run(
                run_id=run_id,
                status="FAILED",
                error_msg=str(e)
            )
            raise e


if __name__ == "__main__":
    loader = UnstructuredBronzeLoader()
    loader.ingest_documents()
