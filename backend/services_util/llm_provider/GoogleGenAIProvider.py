import google.generativeai as genai
from .interface_llm_provider import LLMProvider
from google import genai
from backend.core.env_config import envConfig


class GoogleGenAIProvider(LLMProvider):

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-pro")

    def generate(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text

    def embed(self, text: str) -> list[float]:
        result = genai.embed_content(
            model="models/embedding-001",
            content=text
        )
        return result["embedding"]
