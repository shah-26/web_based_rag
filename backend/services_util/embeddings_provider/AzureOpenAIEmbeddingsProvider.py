from .interface_embeddings_provider import EmbeddingsProvider
from openai import AzureOpenAI
from core.env_config import envConfig


class AzureOpenAIEmbeddingsProvider(EmbeddingsProvider):

    def __init__(self):
        # Initialize Azure OpenAI client here
        self.client = AzureOpenAI(
            # Placeholder, replace with actual Azure OpenAI API key
            api_key=envConfig.AZURE_OPENAI_API_KEY,
            azure_endpoint=envConfig.AZURE_OPENAI_ENDPOINT,
            api_version=envConfig.AZURE_OPENAI_API_VERSION,
        )  # Placeholder, replace with actual Azure OpenAI client initialization

    def embed(self, batch: list[str]) -> list[list[float]]:
        # Call Azure OpenAI embedding API here
        response = self.client.embeddings.create(
            input=batch,
            # Placeholder, replace with actual model name
            model=envConfig.AZURE_DEPLOYMENT_ID,
        )
        return [item.embedding for item in response.data]
