from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

_client: chromadb.ClientAPI | None = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(tenant_id: str):
    client = get_client()
    return client.get_or_create_collection(
        name=f"kb_{tenant_id}",
        metadata={"hnsw:space": "cosine"},
    )
