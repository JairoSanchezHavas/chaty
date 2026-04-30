"""
Carga archivos .md de un tenant, los chunka por sección (## heading) y los
embebe con Gemini text-embedding-004 para guardarlos en ChromaDB.
"""

import re
from pathlib import Path

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
                task_type="retrieval_document",
            )
    return _embeddings


def _chunk_markdown(text: str, source: str) -> list[dict]:
    chunks = []
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        first_line = section.splitlines()[0].lstrip("#").strip()
        chunks.append({"text": section, "source": source, "section": first_line})
    return chunks


def _embed_texts(texts: list[str]) -> list[list[float]]:
    return _get_embeddings().embed_documents(texts)


def ingest_tenant(tenant_id: str) -> int:
    collection = get_collection(tenant_id)
    if collection.count() > 0:
        print(f"[ingest] Colección '{tenant_id}' ya tiene datos, se omite ingesta.")
        return collection.count()

    kb_dir: Path = settings.tenant_dir(tenant_id) / "knowledge"
    if not kb_dir.exists():
        print(f"[ingest] No se encontró directorio knowledge para '{tenant_id}'.")
        return 0

    all_chunks: list[dict] = []
    for md_file in sorted(kb_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = _chunk_markdown(text, source=md_file.name)
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    texts = [c["text"] for c in all_chunks]
    embeddings = _embed_texts(texts)

    ids = [f"{tenant_id}_{i}" for i in range(len(all_chunks))]
    metadatas = [{"tenant_id": tenant_id, "source": c["source"], "section": c["section"]} for c in all_chunks]

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    print(f"[ingest] {len(all_chunks)} chunks indexados para '{tenant_id}'.")
    return len(all_chunks)
