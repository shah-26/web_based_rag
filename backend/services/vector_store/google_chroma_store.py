from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services_util.embeddings_provider.EmbeddingsProviderFactory import EmbeddingsProviderFactory
import chromadb
from google.genai import types
import time

REQUESTS_PER_SECOND = 3  # tune based on your quota
MIN_INTERVAL = 1.0 / REQUESTS_PER_SECOND

last_call_ts = 0.0


def wait_for_slot():
    global last_call_ts
    now = time.time()
    elapsed = now - last_call_ts
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    last_call_ts = time.time()


@dataclass(frozen=True)
class EmbeddingConfig:
    """Google embedding settings for retrieval documents."""

    model: str = "gemini-embedding-001"
    batch_size: int = 50
    output_dimensionality: int | None = None
    task_type: str = "RETRIEVAL_DOCUMENT"

    def __post_init__(self) -> None:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")


@dataclass(frozen=True)
class ChromaStoreConfig:
    """Local Chroma settings for the POC vector store."""

    persist_directory: str = "./chroma_db"
    collection_name: str = "waters_articles"


def index_chunks(
    chunks: list[dict[str, Any]],
    genai_client: Any,
    store_config: ChromaStoreConfig | None = None,
    embedding_config: EmbeddingConfig | None = None,
) -> dict[str, Any]:
    """Embed chunk text with Google GenAI and upsert the vectors into Chroma."""
    if not chunks:
        return {
            "collection_name": (store_config or ChromaStoreConfig()).collection_name,
            "persist_directory": (store_config or ChromaStoreConfig()).persist_directory,
            "chunks_indexed": 0,
        }

    store_cfg = store_config or ChromaStoreConfig()
    embed_cfg = embedding_config or EmbeddingConfig()

    persist_path = Path(store_cfg.persist_directory)
    persist_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_path))
    collection = client.get_or_create_collection(
        name=store_cfg.collection_name)

    ids = [chunk["id"] for chunk in chunks]
    documents = [chunk["page_content"] for chunk in chunks]
    metadatas = [_flatten_metadata(chunk.get("metadata", {}))
                 for chunk in chunks]
    embeddings = _embed_texts(
        texts=documents,
        genai_client=genai_client,
        config=embed_cfg,
    )

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    return {
        "collection_name": store_cfg.collection_name,
        "persist_directory": str(persist_path),
        "chunks_indexed": len(chunks),
    }


def query_chunks(
    query: str,
    genai_client: Any,
    store_config: ChromaStoreConfig | None = None,
    embedding_config: EmbeddingConfig | None = None,
    n_results: int = 5,
) -> dict[str, Any]:
    """Retrieve similar chunks from the local Chroma collection."""
    store_cfg = store_config or ChromaStoreConfig()
    embed_cfg = embedding_config or EmbeddingConfig(
        task_type="RETRIEVAL_QUERY")

    client = chromadb.PersistentClient(path=store_cfg.persist_directory)
    collection = client.get_or_create_collection(
        name=store_cfg.collection_name)
    query_embedding = _embed_texts(
        texts=[query],
        genai_client=genai_client,
        config=embed_cfg,
    )[0]

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )


def _embed_texts(
    texts: list[str],
    genai_client: Any,
    config: EmbeddingConfig,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), config.batch_size):
        batch = texts[start:start + config.batch_size]
        time.sleep(0.5)  # brief pause to avoid hitting rate limits
        # response = genai_client.models.embed_content(
        #     model=config.model,
        #     contents=batch,
        #     config=_build_embed_config(config),
        # )
        # embeddings.extend(_extract_embedding_values(response))
        response = EmbeddingsProviderFactory.create().embed(batch)
        embeddings.extend(response)

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Expected {len(texts)} embeddings, received {len(embeddings)}."
        )

    return embeddings


def _build_embed_config(config: EmbeddingConfig) -> types.EmbedContentConfig:
    kwargs: dict[str, Any] = {"task_type": config.task_type}
    if config.output_dimensionality is not None:
        kwargs["output_dimensionality"] = config.output_dimensionality
    return types.EmbedContentConfig(**kwargs)


def _extract_embedding_values(response: Any) -> list[list[float]]:
    values: list[list[float]] = []
    for embedding in getattr(response, "embeddings", []) or []:
        if isinstance(embedding, dict):
            vector = embedding.get("values") or embedding.get("embedding")
        else:
            vector = getattr(embedding, "values", None) or getattr(
                embedding, "embedding", None)

        if vector is None:
            raise RuntimeError(
                "Google embedding response did not include vector values.")

        values.append([float(item) for item in vector])

    return values


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    flattened: dict[str, str | int | float | bool] = {}

    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            flattened[key] = value
        elif isinstance(value, list):
            flattened[key] = ", ".join(str(item) for item in value)
        else:
            flattened[key] = str(value)

    return flattened
