
from services_util.embeddings_provider.AzureOpenAIEmbeddingsProvider import AzureOpenAIEmbeddingsProvider
from services_util.embeddings_provider.interface_embeddings_provider import EmbeddingsProvider, GoogleGenAIEmbeddingsProvider
from core.env_config import envConfig


class EmbeddingsProviderFactory:

    @staticmethod
    def create() -> EmbeddingsProvider:
        if envConfig.ENV == "development":
            # Google
            return GoogleGenAIEmbeddingsProvider()

        elif envConfig.ENV == "uat":
            # Azure
            return AzureOpenAIEmbeddingsProvider()

        else:
            raise ValueError(f"Unsupported ENV: {envConfig.ENV}")
