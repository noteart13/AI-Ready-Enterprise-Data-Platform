"""
Enterprise Hybrid RAG Retriever with Okapi BM25, Dense Vector HNSW (FastEmbed),
Reciprocal Rank Fusion (RRF), and Zero-Trust Document ACL Security Trimming.
Guarantees cross-run deterministic point IDs using RFC 4122 UUID5.
"""

import os
import re
import uuid
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np
import pandas as pd
from deltalake import DeltaTable
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchAny
)
from rank_bm25 import BM25Okapi
from src.retrieval.embedding_service import EmbeddingService
from src.semantic.cube_client import SecurityContext


def tokenize_corpus_text(text: str) -> List[str]:
    """Tokenizes text into normalized lexical terms for BM25 indexing."""
    if not text:
        return []
    # Match alphanumeric words and hyphenated terms (e.g. CTR-2026-VIP-001)
    tokens = re.findall(r"[\w-]+", text.lower())
    return [t for t in tokens if len(t) > 1]


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
        self._bm25_index: Optional[BM25Okapi] = None
        self._corpus_records: List[Dict[str, Any]] = []

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
        self._ensure_bm25_index()

    def _init_collection(self):
        """Initializes or migrates Qdrant collection to match current embedding dimensions."""
        try:
            collections = self.qdrant.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if exists:
                info = self.qdrant.get_collection(self.collection_name)
                # Check vector size compatibility (e.g. 1536 -> 384 migration)
                existing_dim = info.config.params.vectors.size
                if existing_dim != self.embedding_service.dimension:
                    print(
                        f"[HybridRetriever] Migrating collection '{self.collection_name}': "
                        f"dimension change {existing_dim} -> {self.embedding_service.dimension}"
                    )
                    self.qdrant.delete_collection(self.collection_name)
                    exists = False

            if not exists:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.embedding_service.dimension, distance=Distance.COSINE)
                )
                self.index_gold_chunks()
            else:
                info = self.qdrant.get_collection(self.collection_name)
                if info.points_count == 0:
                    self.index_gold_chunks()
        except Exception as e:
            print(f"[HybridRetriever] Collection init warning: {e}")

    def _ensure_bm25_index(self):
        """Loads and compiles Okapi BM25 inverted index across all Gold chunks in memory."""
        gold_chunks_path = f"{self.lakehouse_base}/gold/rag_chunks"
        if not os.path.exists(gold_chunks_path):
            return

        chunks_df = DeltaTable(gold_chunks_path).to_pandas()
        self._corpus_records = chunks_df.to_dict(orient="records")

        # Prepare tokenized corpus with extra weighting for document code / titles
        tokenized_corpus = []
        for row in self._corpus_records:
            doc_id_tokens = tokenize_corpus_text(str(row.get("doc_id", "")))
            file_name_tokens = tokenize_corpus_text(str(row.get("file_name", "")))
            text_tokens = tokenize_corpus_text(str(row.get("chunk_text", "")))
            # Document and title tokens repeated for higher lexical weighting
            combined_tokens = (doc_id_tokens * 3) + (file_name_tokens * 2) + text_tokens
            tokenized_corpus.append(combined_tokens)

        if tokenized_corpus:
            self._bm25_index = BM25Okapi(tokenized_corpus)

    def index_gold_chunks(self) -> int:
        """Indexes all deterministic chunks from Gold Delta Table into Qdrant using stable UUID5 IDs."""
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
            # Deterministic, cross-platform RFC 4122 UUID5 (avoids Python process hash randomization)
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk://{row['chunk_id']}"))
            points.append(PointStruct(
                id=point_id,
                vector=embeddings[idx],
                payload=payload
            ))

        self.qdrant.upsert(collection_name=self.collection_name, points=points)
        print(f"[HybridRetriever] Successfully indexed {len(points)} chunks into Qdrant with stable UUIDs.")
        self._ensure_bm25_index()
        return len(points)

    def retrieve_hybrid(
        self,
        query: str,
        security_context: Optional[SecurityContext] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Executes Standard Enterprise Hybrid Retrieval:
        1. Dense Semantic Vector Search (Cosine Similarity in Qdrant)
        2. Standard Okapi BM25 Lexical Keyword Search
        3. Zero-Trust Security Trimming (ACL Clearance & Multi-Tenant Boundaries)
        4. Reciprocal Rank Fusion (RRF: k=60)
        """
        sec = security_context or SecurityContext()
        permitted_acls = self.CLEARANCE_HIERARCHY.get(sec.security_clearance.upper(), ["PUBLIC"])
        allowed_tenants = [sec.tenant_id, "GLOBAL_TENANT"]

        # Security Trimming Filter for Qdrant
        query_filter = Filter(
            must=[
                FieldCondition(key="security_acl", match=MatchAny(any=permitted_acls)),
                FieldCondition(key="tenant_id", match=MatchAny(any=allowed_tenants))
            ]
        )

        # 1. Dense Vector Search
        query_vec = self.embedding_service.get_embedding(query)
        try:
            search_res = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=query_vec,
                query_filter=query_filter,
                limit=20
            )
            dense_results = search_res.points
        except Exception as e:
            print(f"[HybridRetriever] Dense search error: {e}")
            dense_results = []

        # 2. Standard Okapi BM25 Lexical Search with Zero-Trust Security Filtering
        query_tokens = tokenize_corpus_text(query)
        bm25_candidates = []

        if self._bm25_index is not None and self._corpus_records and query_tokens:
            bm25_scores = self._bm25_index.get_scores(query_tokens)
            
            for idx, score in enumerate(bm25_scores):
                if score <= 0.001:
                    continue
                record = self._corpus_records[idx]
                
                # Zero-Trust Security Trimming on BM25 candidates
                if record.get("security_acl") not in permitted_acls:
                    continue
                if record.get("tenant_id") not in allowed_tenants:
                    continue

                bm25_candidates.append({
                    "record": record,
                    "bm25_score": float(score)
                })

            # Sort BM25 candidates descending by BM25 score
            bm25_candidates.sort(key=lambda x: x["bm25_score"], reverse=True)

        # 3. Reciprocal Rank Fusion (RRF with k = 60)
        # RRF_Score(d) = SUM_m [ 1 / (k + rank_m(d)) ]
        k = 60
        rrf_dict = defaultdict(lambda: {
            "score": 0.0,
            "payload": None,
            "dense_rank": None,
            "bm25_rank": None,
            "bm25_score": 0.0
        })

        for rank, p in enumerate(dense_results):
            cid = p.payload["chunk_id"]
            rrf_dict[cid]["score"] += 1.0 / (k + rank + 1)
            rrf_dict[cid]["payload"] = p.payload
            rrf_dict[cid]["dense_rank"] = rank + 1

        for rank, cand in enumerate(bm25_candidates[:30]):
            rec = cand["record"]
            cid = rec["chunk_id"]
            rrf_dict[cid]["score"] += 1.0 / (k + rank + 1)
            if rrf_dict[cid]["payload"] is None:
                rrf_dict[cid]["payload"] = rec
            rrf_dict[cid]["bm25_rank"] = rank + 1
            rrf_dict[cid]["bm25_score"] = round(cand["bm25_score"], 4)

        sorted_candidates = sorted(rrf_dict.values(), key=lambda x: x["score"], reverse=True)

        # 4. Assemble Top-K Structured Results
        final_results = []
        for item in sorted_candidates[:top_k]:
            pt = item["payload"]
            if not pt:
                continue

            final_results.append({
                "chunk_id": pt.get("chunk_id"),
                "doc_id": pt.get("doc_id"),
                "file_name": pt.get("file_name"),
                "page_no": int(pt.get("page_no", 1)),
                "tenant_id": pt.get("tenant_id"),
                "department": pt.get("department"),
                "security_acl": pt.get("security_acl"),
                "text": pt.get("chunk_text"),
                "rrf_score": round(item["score"], 4),
                "dense_rank": item["dense_rank"],
                "bm25_rank": item["bm25_rank"],
                "bm25_score": item["bm25_score"]
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
        print(f"[{r['file_name']} (Trang {r['page_no']}) ACL={r['security_acl']} RRF={r['rrf_score']} BM25={r['bm25_score']}]\n{clean_txt}...\n")

    print("\n--- Test 2: Security Trimming Test (Guest PUBLIC clearance vs RESTRICTED audit report) ---")
    sec_guest = SecurityContext(
        tenant_id="VN_DIST_NORTH",
        role="guest",
        department="SALES",
        security_clearance="PUBLIC"
    )
    res2 = retriever.retrieve_hybrid("Lợi nhuận gộp và thưởng ban điều hành kiểm toán tài chính AUD-2026-Q1", sec_guest)
    print(f"Guest search result count (Should be 0 because audit report is RESTRICTED): {len(res2)}")
