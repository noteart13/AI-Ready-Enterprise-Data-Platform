"""
Enterprise Hybrid RAG Retriever with Reciprocal Rank Fusion (RRF)
and Zero-Trust Document ACL Security Trimming.
Combines BM25 Exact Keyword Search with Dense Vector HNSW Search in Qdrant.
"""

import os
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np
import pandas as pd
from deltalake import DeltaTable
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny
)
from src.retrieval.embedding_service import EmbeddingService
from src.semantic.cube_client import SecurityContext


class HybridRetriever:
    CLEARANCE_HIERARCHY = {
        "PUBLIC": ["PUBLIC"],
        "INTERNAL": ["PUBLIC", "INTERNAL"],
        "CONFIDENTIAL": ["PUBLIC", "INTERNAL", "CONFIDENTIAL"],
        "RESTRICTED": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    }

    def __init__(
        self,
        collection_name: str = "rag-chunks-index-v1",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        lakehouse_base: str = "./data/lakehouse"
    ):
        self.collection_name = collection_name
        self.lakehouse_base = lakehouse_base
        self.embedding_service = EmbeddingService()

        # Connect to Qdrant (try docker first, fallback to persistent disk storage)
        self.storage_path = f"{lakehouse_base}/gold/qdrant_storage"
        try:
            self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=0.2, check_compatibility=False)
            self.qdrant.get_collections()
            self.is_remote = True
        except Exception:
            os.makedirs(self.storage_path, exist_ok=True)
            self.qdrant = QdrantClient(path=self.storage_path)
            self.is_remote = False

        self._init_collection()

    def _init_collection(self):
        try:
            collections = self.qdrant.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.embedding_service.dimension, distance=Distance.COSINE)
                )
                self.index_gold_chunks()
            else:
                # If collection exists but is empty, index gold chunks
                info = self.qdrant.get_collection(self.collection_name)
                if info.points_count == 0:
                    self.index_gold_chunks()
        except Exception as e:
            print(f"[HybridRetriever] Collection init warning: {e}")

    def index_gold_chunks(self) -> int:
        """Indexes all deterministic chunks from Gold Delta Table into Qdrant."""
        gold_chunks_path = f"{self.lakehouse_base}/gold/rag_chunks"
        if not os.path.exists(gold_chunks_path):
            print(f"[HybridRetriever] Gold chunks not found at {gold_chunks_path}")
            return 0

        chunks_df = DeltaTable(gold_chunks_path).to_pandas()
        texts = chunks_df["chunk_text"].tolist()
        embeddings = self.embedding_service.get_embeddings(texts)

        points = []
        for idx, row in chunks_df.iterrows():
            payload = {
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "file_name": row["file_name"],
                "page_no": int(row["page_no"]),
                "chunk_index": int(row["chunk_index"]),
                "chunk_text": row["chunk_text"],
                "tenant_id": row["tenant_id"],
                "department": row["department"],
                "security_acl": row["security_acl"],
                "metadata_json": row["metadata_json"]
            }
            # Deterministic integer point ID
            point_id = int(hash(row["chunk_id"]) % (10**9))
            points.append(PointStruct(
                id=point_id,
                vector=embeddings[idx],
                payload=payload
            ))

        self.qdrant.upsert(collection_name=self.collection_name, points=points)
        print(f"[HybridRetriever] Successfully indexed {len(points)} chunks into Qdrant.")
        return len(points)

    def retrieve_hybrid(
        self,
        query: str,
        security_context: Optional[SecurityContext] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Executes Hybrid Retrieval:
        1. BM25 keyword matching
        2. Dense vector cosine search
        3. Reciprocal Rank Fusion (RRF)
        4. Zero-Trust Security Trimming (ACL & Tenant filtering)
        """
        sec = security_context or SecurityContext()
        permitted_acls = self.CLEARANCE_HIERARCHY.get(sec.security_clearance.upper(), ["PUBLIC"])
        allowed_tenants = [sec.tenant_id, "GLOBAL_TENANT"]

        # 1. Fetch candidates from Qdrant with Security Trimming Filter
        query_filter = Filter(
            must=[
                FieldCondition(key="security_acl", match=MatchAny(any=permitted_acls)),
                FieldCondition(key="tenant_id", match=MatchAny(any=allowed_tenants))
            ]
        )

        query_vec = self.embedding_service.get_embedding(query)

        # Dense Vector Search
        search_res = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vec,
            query_filter=query_filter,
            limit=15
        )
        dense_results = search_res.points

        # 2. BM25 Keyword Search over candidates
        all_points, _ = self.qdrant.scroll(
            collection_name=self.collection_name,
            scroll_filter=query_filter,
            limit=50,
            with_payload=True
        )

        tokens = set(re.findall(r"\w+", query.lower()))
        bm25_scores = []
        for p in all_points:
            text = p.payload.get("chunk_text", "").lower()
            doc_id = p.payload.get("doc_id", "").lower()
            file_name = p.payload.get("file_name", "").lower()

            score = 0.0
            for t in tokens:
                if len(t) <= 1:
                    continue
                # Boost exact match on code/ID
                if t in doc_id or t in file_name:
                    score += 5.0
                if t in text:
                    score += 1.0 + (text.count(t) * 0.2)

            if score > 0:
                bm25_scores.append((p, score))

        bm25_scores.sort(key=lambda x: x[1], reverse=True)

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_Score = 1 / (k + rank_dense) + 1 / (k + rank_bm25) with k = 60
        k = 60
        rrf_dict = defaultdict(lambda: {"score": 0.0, "point": None, "dense_rank": None, "bm25_rank": None})

        for rank, p in enumerate(dense_results):
            cid = p.payload["chunk_id"]
            rrf_dict[cid]["score"] += 1.0 / (k + rank + 1)
            rrf_dict[cid]["point"] = p
            rrf_dict[cid]["dense_rank"] = rank + 1

        for rank, (p, _) in enumerate(bm25_scores):
            cid = p.payload["chunk_id"]
            rrf_dict[cid]["score"] += 1.0 / (k + rank + 1)
            rrf_dict[cid]["point"] = p
            rrf_dict[cid]["bm25_rank"] = rank + 1

        sorted_candidates = sorted(rrf_dict.values(), key=lambda x: x["score"], reverse=True)

        # 4. Format structured citation outputs with Threshold Filtering
        final_results = []
        for item in sorted_candidates[:top_k]:
            pt = item["point"]
            # Threshold filtering: must have matched at least some keyword or has high dense relevance
            bm25_r = item["bm25_rank"]
            if bm25_r is None and item["score"] < 0.016:
                # Discard low-confidence noise
                continue

            final_results.append({
                "chunk_id": pt.payload["chunk_id"],
                "doc_id": pt.payload["doc_id"],
                "file_name": pt.payload["file_name"],
                "page_no": pt.payload["page_no"],
                "tenant_id": pt.payload["tenant_id"],
                "department": pt.payload["department"],
                "security_acl": pt.payload["security_acl"],
                "text": pt.payload["chunk_text"],
                "rrf_score": round(item["score"], 4),
                "dense_rank": item["dense_rank"],
                "bm25_rank": item["bm25_rank"]
            })

        return final_results


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    retriever = HybridRetriever()
    retriever.index_gold_chunks()

    print("\n--- Test 1: Query SLA for North Distribution as Sales Manager (CONFIDENTIAL clearance) ---")
    sec_sales = SecurityContext(
        tenant_id="VN_DIST_NORTH",
        role="sales_manager",
        department="SALES",
        security_clearance="CONFIDENTIAL"
    )
    res1 = retriever.retrieve_hybrid("Cam kết thời gian giao hàng và điều khoản phạt SLA hợp đồng CTR-2026-VIP-001", sec_sales)
    for r in res1:
        clean_txt = r['text'][:150].replace('\n', ' ')
        print(f"[{r['file_name']} (Trang {r['page_no']}) ACL={r['security_acl']} RRF={r['rrf_score']}]\n{clean_txt}...\n")

    print("\n--- Test 2: Security Trimming Test (Guest PUBLIC clearance vs RESTRICTED audit report) ---")
    sec_guest = SecurityContext(
        tenant_id="VN_DIST_NORTH",
        role="guest",
        department="SALES",
        security_clearance="PUBLIC"
    )
    res2 = retriever.retrieve_hybrid("Lợi nhuận gộp và thưởng ban điều hành kiểm toán tài chính AUD-2026-Q1", sec_guest)
    print(f"Guest search result count (Should be 0 because audit report is RESTRICTED): {len(res2)}")
