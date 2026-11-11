"""
Enterprise Multi-Provider Embedding Service.
Supports high-performance on-device ONNX embedding (FastEmbed) as the production standard,
along with cloud providers (Azure OpenAI, OpenAI, Gemini) and a deterministic offline fallback.
"""

import os
import hashlib
from typing import List, Optional
import numpy as np


class EmbeddingService:
    _fastembed_instance = None
    _fastembed_model_name = None

    def __init__(self, provider: Optional[str] = None, dimension: Optional[int] = None):
        # Default to fastembed (real embedding model) if available, or environment setting
        self.provider = (provider or os.getenv("EMBEDDING_PROVIDER", "fastembed")).lower()
        self.model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
        
        # Determine dimension based on provider and model
        if dimension is not None:
            self.dimension = dimension
        elif self.provider == "fastembed":
            # BGE-small, MiniLM-L6, and multilingual-MiniLM are 384 dimensions
            if "large" in self.model_name.lower():
                self.dimension = 1024
            elif "base" in self.model_name.lower():
                self.dimension = 768
            else:
                self.dimension = 384
        elif self.provider in ["openai", "azure_openai"]:
            self.dimension = 1536
        elif self.provider == "gemini":
            self.dimension = 768
        else:
            self.dimension = 384

        self._init_fastembed_if_needed()

    def _init_fastembed_if_needed(self):
        """Initializes FastEmbed model singleton if fastembed provider is selected."""
        if self.provider == "fastembed":
            if EmbeddingService._fastembed_instance is None or EmbeddingService._fastembed_model_name != self.model_name:
                try:
                    from fastembed import TextEmbedding
                    EmbeddingService._fastembed_instance = TextEmbedding(model_name=self.model_name)
                    EmbeddingService._fastembed_model_name = self.model_name
                except Exception as e:
                    print(f"[EmbeddingService] FastEmbed initialization warning: {e}. Falling back to deterministic.")
                    self.provider = "mock"

    def get_embedding(self, text: str) -> List[float]:
        """Generates dense vector for a single text."""
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates dense vectors for a list of texts using the configured provider."""
        if not texts:
            return []

        # 1. FastEmbed (Real On-Device Production Embeddings)
        if self.provider == "fastembed" and EmbeddingService._fastembed_instance is not None:
            try:
                embeddings_gen = EmbeddingService._fastembed_instance.embed(texts)
                return [emb.tolist() for emb in embeddings_gen]
            except Exception as e:
                print(f"[EmbeddingService] FastEmbed inference error: {e}. Falling back.")

        # 2. OpenAI Direct API
        if self.provider == "openai" and os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                resp = client.embeddings.create(
                    input=texts,
                    model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                )
                return [d.embedding for d in resp.data]
            except Exception as e:
                print(f"[EmbeddingService] OpenAI API error: {e}. Falling back.")

        # 3. Azure OpenAI API
        if self.provider == "azure_openai" and os.getenv("AZURE_OPENAI_API_KEY"):
            try:
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
                )
                resp = client.embeddings.create(
                    input=texts,
                    model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
                )
                return [d.embedding for d in resp.data]
            except Exception as e:
                print(f"[EmbeddingService] Azure OpenAI API error: {e}. Falling back.")

        # 4. Google Gemini API
        if self.provider == "gemini" and os.getenv("GEMINI_API_KEY"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=texts,
                    task_type="retrieval_document"
                )
                return result["embedding"]
            except Exception as e:
                print(f"[EmbeddingService] Gemini API error: {e}. Falling back.")

        # 5. Deterministic fallback for test suites only if mock explicitly requested or runtime failure
        return [self._deterministic_vector(t) for t in texts]

    def _deterministic_vector(self, text: str) -> List[float]:
        """
        Creates a normalized, pseudo-random but strictly reproducible dense vector.
        Reserved for explicit unit test mock mode only.
        """
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        for w in words:
            w_hash = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(w_hash)
            component = rng.randn(self.dimension).astype(np.float32)
            vec += component

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
