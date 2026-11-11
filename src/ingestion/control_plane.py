"""
Control Plane & Idempotency Engine for AI-Ready Enterprise Data Platform.
Manages:
- file_manifest: SHA-256 content hashes, idempotency checks
- watermark: High-watermarks for incremental ingestion
- run_log: Execution audits, latency, and record counters
"""

import hashlib
import os
import sqlite3
import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


class ControlPlane:
    def __init__(self, db_path: str = "./data/control/control_plane.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. file_manifest table for document and file idempotency
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_manifest (
                    file_path TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL, -- 'INGESTED', 'FAILED', 'PENDING'
                    records_or_chunks_count INTEGER DEFAULT 0
                )
            """)

            # 2. watermark table for incremental table/log ingestion
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watermarks (
                    entity_name TEXT PRIMARY KEY,
                    last_watermark_val TEXT NOT NULL,
                    watermark_type TEXT NOT NULL, -- 'TIMESTAMP', 'INCREMENTAL_ID'
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. run_log table for pipeline execution audits & FinOps metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_logs (
                    run_id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL, -- 'RUNNING', 'SUCCESS', 'FAILED'
                    records_processed INTEGER DEFAULT 0,
                    records_inserted INTEGER DEFAULT 0,
                    records_updated INTEGER DEFAULT 0,
                    records_skipped INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """)
            conn.commit()

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of a file's binary content."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def check_file_status(self, file_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Check if file is new or modified.
        Returns:
            (needs_processing: bool, current_hash: str, manifest_record: Optional[Dict])
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        current_hash = self.calculate_file_hash(file_path)
        normalized_path = str(Path(file_path).resolve())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM file_manifest WHERE file_path = ?", 
                (normalized_path,)
            )
            row = cursor.fetchone()

            if not row:
                # Completely new file
                return True, current_hash, None

            record = dict(row)
            if record["content_hash"] != current_hash or record["status"] != "INGESTED":
                # File content has changed or previous attempt failed
                return True, current_hash, record

            # File unchanged and already successfully ingested
            return False, current_hash, record

    def record_file_manifest(
        self,
        file_path: str,
        content_hash: str,
        status: str = "INGESTED",
        chunks_count: int = 0
    ):
        """Insert or update file manifest entry."""
        normalized_path = str(Path(file_path).resolve())
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_type = Path(file_path).suffix.lower().lstrip(".")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO file_manifest (
                    file_path, file_name, content_hash, file_size, file_type, 
                    last_processed_at, status, records_or_chunks_count
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    file_size = excluded.file_size,
                    last_processed_at = CURRENT_TIMESTAMP,
                    status = excluded.status,
                    records_or_chunks_count = excluded.records_or_chunks_count
            """, (normalized_path, file_name, content_hash, file_size, file_type, status, chunks_count))
            conn.commit()

    def get_watermark(self, entity_name: str) -> Optional[str]:
        """Retrieve current high watermark value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_watermark_val FROM watermarks WHERE entity_name = ?", 
                (entity_name,)
            )
            row = cursor.fetchone()
            return row["last_watermark_val"] if row else None

    def update_watermark(self, entity_name: str, watermark_val: str, watermark_type: str = "TIMESTAMP"):
        """Update entity high watermark."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watermarks (entity_name, last_watermark_val, watermark_type, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(entity_name) DO UPDATE SET
                    last_watermark_val = excluded.last_watermark_val,
                    watermark_type = excluded.watermark_type,
                    updated_at = CURRENT_TIMESTAMP
            """, (entity_name, str(watermark_val), watermark_type))
            conn.commit()

    def start_pipeline_run(self, pipeline_name: str) -> str:
        """Create new execution run record."""
        run_id = f"{pipeline_name}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO run_logs (run_id, pipeline_name, status, start_time)
                VALUES (?, ?, 'RUNNING', CURRENT_TIMESTAMP)
            """, (run_id, pipeline_name))
            conn.commit()
        return run_id

    def finish_pipeline_run(
        self,
        run_id: str,
        status: str = "SUCCESS",
        processed: int = 0,
        inserted: int = 0,
        updated: int = 0,
        skipped: int = 0,
        error_msg: Optional[str] = None
    ):
        """Mark pipeline run completed with execution metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE run_logs SET
                    end_time = CURRENT_TIMESTAMP,
                    status = ?,
                    records_processed = ?,
                    records_inserted = ?,
                    records_updated = ?,
                    records_skipped = ?,
                    error_message = ?
                WHERE run_id = ?
            """, (status, processed, inserted, updated, skipped, error_msg, run_id))
            conn.commit()
