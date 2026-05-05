from abc import ABC, abstractmethod
from typing import Any
from core.env_config import envConfig
from google import genai
from dataclasses import dataclass
from google.genai import types


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


def _build_embed_config(config: EmbeddingConfig) -> types.EmbedContentConfig:
    kwargs: dict[str, Any] = {"task_type": config.task_type}
    if config.output_dimensionality is not None:
        kwargs["output_dimensionality"] = config.output_dimensionality
    return types.EmbedContentConfig(**kwargs)


class EmbeddingsProvider(ABC):

    @abstractmethod
    def embed(self, batch: str) -> list[float]:
        pass


class GoogleGenAIEmbeddingsProvider(EmbeddingsProvider):

    def __init__(self):
        self.genai_client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)
        self.model = envConfig.EMBEDDINGS_MODEL

    def embed(self, batch: str):
        response = self.genai_client.models.embed_content(
            model=self.model,
            contents=batch,
            config=_build_embed_config(
                EmbeddingConfig(task_type="RETRIEVAL_DOCUMENT"))
        )
        return response
