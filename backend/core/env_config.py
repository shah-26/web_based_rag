import os
from pydantic_settings import BaseSettings


class EnvConfig(BaseSettings):
    ENV: str = os.getenv("ENV", "development")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    EMBEDDINGS_MODEL: str = os.getenv(
        "EMBEDDINGS_MODEL", "gemini-embedding-001")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION: str = os.getenv(
        "AZURE_OPENAI_API_VERSION", "2024-06-01")
    AZURE_DEPLOYMENT_ID: str = os.getenv("AZURE_DEPLOYMENT_ID")

    class config:
        env_file = ".env"
        env_file_encoding = "utf-8"


envConfig = EnvConfig()
