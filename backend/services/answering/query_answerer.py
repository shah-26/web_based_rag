from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.vector_store import ChromaStoreConfig, query_chunks


@dataclass(frozen=True)
class AnswerConfig:
    """Google generation settings for grounded answers."""

    model: str = "gemini-3-flash-preview"
    n_results: int = 5
    max_context_chars: int = 14000

    def __post_init__(self) -> None:
        if self.n_results <= 0:
            raise ValueError("n_results must be greater than 0")
        if self.max_context_chars <= 0:
            raise ValueError("max_context_chars must be greater than 0")


def answer_user_query(
    query: str,
    genai_client: Any,
    store_config: ChromaStoreConfig | None = None,
    answer_config: AnswerConfig | None = None,
) -> dict[str, Any]:
    """Retrieve relevant chunks and answer the user query with citations."""
    cfg = answer_config or AnswerConfig()
    retrieval = query_chunks(
        query=query,
        genai_client=genai_client,
        store_config=store_config,
        n_results=cfg.n_results,
    )
    chunks = _normalize_retrieval_results(retrieval)
    citations = _build_citations(chunks)

    if not chunks:
        return {
            "answer": "I could not find relevant indexed content to answer that question.",
            "citations": [],
            "retrieved_chunks": [],
        }

    prompt = _build_prompt(
        query=query,
        chunks=chunks,
        max_context_chars=cfg.max_context_chars,
    )
    response = genai_client.models.generate_content(
        model=cfg.model,
        contents=prompt,
    )

    return {
        "answer": _extract_text(response),
        "citations": citations,
        "retrieved_chunks": chunks,
    }


def _normalize_retrieval_results(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    ids = _first_result_group(retrieval.get("ids"))
    documents = _first_result_group(retrieval.get("documents"))
    metadatas = _first_result_group(retrieval.get("metadatas"))
    distances = _first_result_group(retrieval.get("distances"))

    chunks: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(
            metadatas) and metadatas[index] else {}
        chunk_id = ids[index] if index < len(
            ids) else metadata.get("id", f"chunk-{index}")
        distance = distances[index] if index < len(distances) else None

        chunks.append(
            {
                "citation_id": index + 1,
                "id": chunk_id,
                "content": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return chunks


def _build_citations(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        source = str(metadata.get("source") or metadata.get("link") or "")
        chunk_index = int(metadata.get("chunk_index") or 0)
        key = (source, chunk_index)
        if key in seen:
            continue

        seen.add(key)
        citations.append(
            {
                "citation_id": chunk["citation_id"],
                "title": metadata.get("title", "Untitled page"),
                "source": source,
                "chunk_index": chunk_index,
                "distance": chunk.get("distance"),
            }
        )

    return citations


def _build_prompt(
    query: str,
    chunks: list[dict[str, Any]],
    max_context_chars: int,
) -> str:
    context_blocks: list[str] = []
    used_chars = 0

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        title = metadata.get("title", "Untitled page")
        source = metadata.get("source") or metadata.get("link") or ""
        chunk_index = metadata.get("chunk_index", 0)
        content = chunk.get("content", "")
        print(chunk)
        block = (
            f"[{chunk['citation_id']}] Title: {title}\n"
            f"Source: {source}\n"
            f"Chunk: {chunk_index}\n"
            f"Content: {content}\n"
        )

        if used_chars + len(block) > max_context_chars:
            break

        context_blocks.append(block)
        used_chars += len(block)

    context = "\n---\n".join(context_blocks)
    return (
        "You are a helpful assistant answering questions from indexed Waters support articles.\n"
        "Use only the provided context. If the context does not answer the question, say that you do not know from the indexed content.\n"
        "Cite every factual claim using bracketed citation ids like [1] or [2].\n\n"
        f"Question:\n{query}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:"
    )


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()

    candidates = getattr(response, "candidates", []) or []
    parts: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(str(part_text))

    return "\n".join(parts).strip()


def _first_result_group(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list) and value and isinstance(value[0], list):
        return value[0]
    if isinstance(value, list):
        return value
    return []
