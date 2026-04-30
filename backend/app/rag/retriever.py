from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import settings
from app.rag.store import get_collection

_embeddings: Embeddings | None = None


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        if settings.llm_backend == "vertex":
            from langchain_google_vertexai import VertexAIEmbeddings
            _embeddings = VertexAIEmbeddings(
                model_name=settings.vertex_embed_model,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
        else:
            _embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.gemini_embed_model,
                google_api_key=settings.gemini_api_key,
                task_type="retrieval_query",
            )
    return _embeddings


def _embed_query(text: str) -> list[float]:
    return _get_embeddings().embed_query(text)


def similarity_search(tenant_id: str, query: str, k: int = 4) -> list[str]:
    collection = get_collection(tenant_id)
    if collection.count() == 0:
        return []

    query_emb = _embed_query(query)
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=min(k, collection.count()),
        include=["documents"],
    )
    docs: list[str] = results["documents"][0] if results["documents"] else []
    return docs
