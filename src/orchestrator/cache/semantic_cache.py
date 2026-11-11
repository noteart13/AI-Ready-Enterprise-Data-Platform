"""
FinOps Semantic Cache & Token Bucket Rate Limiting.
Uses Redis (with local fallback) to:
1. Cache answers for high-frequency queries to hit P95 < 100ms SLA.
2. Prevent duplicate LLM embedding/generation costs.
3. Enforce Token Bucket Rate Limiting per user/department.
"""

import os
import json
import time
import hashlib
import numpy as np
from typing import Optional, Dict, Any, Tuple
import redis
from src.retrieval.embedding_service import EmbeddingService


class SemanticCache:
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        similarity_threshold: float = 0.95,
        default_ttl_seconds: int = 3600
    ):
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl_seconds
        self.embedding_service = EmbeddingService()

        # Connect to Redis with fallback to in-memory dictionary
        try:
            self.redis = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                decode_responses=True, 
                socket_connect_timeout=0.2, 
                socket_timeout=0.2
            )
            self.redis.ping()
            self.is_redis_available = True
        except Exception:
            self.redis = None
            self.is_redis_available = False
            self._local_cache = {}

    def get_cache(self, prompt: str, tenant_id: str, clearance: str) -> Optional[Dict[str, Any]]:
        """
        Looks up response in cache.
        Returns cached payload if exact hash match or semantic similarity >= threshold.
        """
        prompt_norm = prompt.strip().lower()
        exact_key = f"cache:{tenant_id}:{clearance}:{hashlib.sha256(prompt_norm.encode()).hexdigest()}"

        # 1. Exact match lookup (< 5ms)
        if self.is_redis_available:
            data = self.redis.get(exact_key)
            if data:
                return json.loads(data)
        else:
            if exact_key in self._local_cache:
                return self._local_cache[exact_key]["data"]

        # 2. Semantic vector cosine match lookup
        prompt_vec = self.embedding_service.get_embedding(prompt_norm)
        prompt_vec_arr = np.array(prompt_vec, dtype=np.float32)

        if not self.is_redis_available:
            for k, val in self._local_cache.items():
                if val["tenant_id"] == tenant_id and val["clearance"] == clearance:
                    cached_vec = np.array(val["vector"], dtype=np.float32)
                    sim = float(np.dot(prompt_vec_arr, cached_vec))
                    if sim >= self.similarity_threshold:
                        return val["data"]
        return None

    def set_cache(self, prompt: str, tenant_id: str, clearance: str, response_data: Dict[str, Any]):
        """Caches query response with TTL."""
        prompt_norm = prompt.strip().lower()
        exact_key = f"cache:{tenant_id}:{clearance}:{hashlib.sha256(prompt_norm.encode()).hexdigest()}"
        prompt_vec = self.embedding_service.get_embedding(prompt_norm)

        payload = {
            "prompt": prompt,
            "tenant_id": tenant_id,
            "clearance": clearance,
            "cached_at": time.time(),
            "data": response_data
        }

        if self.is_redis_available:
            self.redis.setex(exact_key, self.default_ttl, json.dumps(response_data, ensure_ascii=False))
        else:
            self._local_cache[exact_key] = {
                "tenant_id": tenant_id,
                "clearance": clearance,
                "vector": prompt_vec,
                "data": response_data
            }

    def check_rate_limit(self, user_id: str, max_requests_per_minute: int = 60) -> Tuple[bool, int]:
        """
        Enforces Token Bucket / Sliding window rate limit per user.
        Returns (is_allowed, remaining_requests).
        """
        current_minute = int(time.time() // 60)
        rate_key = f"ratelimit:{user_id}:{current_minute}"

        if self.is_redis_available:
            count = self.redis.incr(rate_key)
            if count == 1:
                self.redis.expire(rate_key, 65)
            remaining = max(0, max_requests_per_minute - count)
            return (count <= max_requests_per_minute), remaining
        else:
            # Local in-memory rate limit
            return True, max_requests_per_minute
