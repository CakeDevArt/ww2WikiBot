from pydantic_settings import BaseSettings
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "WW2 RAG Consultant"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002

    API_KEY: str = ""

    AI_PROXY_URL: str = ""
    OPENAI_API_KEY: str = ""
    CHAT_MODEL: str = "gpt-4o"
    REWRITE_MODEL: str = "gpt-4.1-mini"
    VISION_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    STT_MODEL: str = "gpt-4o-mini-transcribe"

    DATABASE_URL: str = ""

    FAISS_STORE_PATH: str = str(_PROJECT_ROOT / "data" / "faiss_store")
    KNOWLEDGE_PATH: str = str(_PROJECT_ROOT / "data" / "knowledge")

    MEMORY_MAX_MESSAGES: int = 10
    RETURN_DEBUG: bool = False

    TELEGRAM_BOT_TOKEN: str = ""
    BOT_API_BASE: str = ""

    @property
    def openai_base_url(self) -> str:
        if self.AI_PROXY_URL:
            return self.AI_PROXY_URL.rstrip("/")
        return "https://api.openai.com"

    @property
    def openai_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.OPENAI_API_KEY:
            headers["Authorization"] = f"Bearer {self.OPENAI_API_KEY}"
        return headers

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
