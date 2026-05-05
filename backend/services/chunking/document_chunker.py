from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import tiktoken


@dataclass(frozen=True)
class ChunkingConfig:
    """Token-aware settings for preparing crawled pages for embeddings."""

    chunk_size: int = 800
    chunk_overlap: int = 120
    encoding_name: str = "cl100k_base"
    include_title_in_content: bool = True
    min_chunk_tokens: int = 40

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.min_chunk_tokens < 0:
            raise ValueError("min_chunk_tokens cannot be negative")


def chunk_crawled_pages(
    pages: list[dict[str, Any]],
    config: ChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """
    Convert crawler output into vector-DB-ready chunks.

    Expected input shape:
    {
        "link": "https://...",
        "title": "Page title",
        "text": "Visible webpage text",
        "images": ["https://..."]
    }

    Output chunks use the common LangChain/vector-store shape:
    {
        "id": "...",
        "page_content": "...",
        "metadata": {
            "source": "...",
            "title": "...",
            "chunk_index": 0,
            "total_chunks": 3,
            ...
        }
    }
    """
    cfg = config or ChunkingConfig()
    chunks: list[dict[str, Any]] = []

    for page_index, page in enumerate(pages):
        chunks.extend(chunk_page(page=page, page_index=page_index, config=cfg))

    return chunks


def chunk_page(
    page: dict[str, Any],
    page_index: int = 0,
    config: ChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """Chunk one crawled page while preserving citation metadata."""
    cfg = config or ChunkingConfig()
    encoding = tiktoken.get_encoding(cfg.encoding_name)

    title = _clean_text(str(page.get("title") or "Untitled page"))
    source = str(page.get("link") or page.get("url") or "")
    text = _clean_text(str(page.get("text") or page.get("raw_text") or ""))
    images = _normalize_images(page.get("images", []))

    if not text:
        return []

    content = f"{title}\n\n{text}" if cfg.include_title_in_content and title else text
    token_ids = encoding.encode(content)
    token_windows = _make_token_windows(
        token_ids=token_ids,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )

    chunks: list[dict[str, Any]] = []
    total_chunks = len(token_windows)

    for chunk_index, window in enumerate(token_windows):
        token_count = len(window)
        if token_count < cfg.min_chunk_tokens and total_chunks > 1:
            continue

        chunk_text = _clean_text(encoding.decode(window))
        if not chunk_text:
            continue

        chunks.append(
            {
                "id": _build_chunk_id(source=source, page_index=page_index, chunk_index=chunk_index),
                "page_content": chunk_text,
                "metadata": {
                    "source": source,
                    "link": source,
                    "title": title,
                    "page_index": page_index,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "token_count": token_count,
                    "images": images,
                },
            }
        )

    return chunks


def to_langchain_documents(chunks: list[dict[str, Any]]) -> list[Any]:
    """
    Convert chunk dicts to LangChain Document objects when langchain-core is installed.

    Keeping this optional lets the service stay useful for any vector DB client that
    accepts plain dictionaries, while still supporting LangChain pipelines.
    """
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise ImportError(
            "Install langchain-core to convert chunks into LangChain Document objects."
        ) from exc

    return [
        Document(
            page_content=chunk["page_content"],
            metadata=chunk.get("metadata", {}),
        )
        for chunk in chunks
    ]


def _make_token_windows(
    token_ids: list[int],
    chunk_size: int,
    chunk_overlap: int,
) -> list[list[int]]:
    windows: list[list[int]] = []
    start = 0
    step = chunk_size - chunk_overlap

    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))
        windows.append(token_ids[start:end])
        if end == len(token_ids):
            break
        start += step

    return windows


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_images(images: Any) -> list[str]:
    if not isinstance(images, list):
        return []

    normalized: list[str] = []
    for image in images:
        if isinstance(image, str):
            normalized.append(image)
        elif isinstance(image, dict):
            src = image.get("src") or image.get("url")
            if src:
                normalized.append(str(src))

    return list(dict.fromkeys(normalized))


def _build_chunk_id(source: str, page_index: int, chunk_index: int) -> str:
    source_key = re.sub(r"[^a-zA-Z0-9]+", "-", source).strip("-").lower()
    if not source_key:
        source_key = f"page-{page_index}"
    return f"{source_key}:chunk-{chunk_index}"
