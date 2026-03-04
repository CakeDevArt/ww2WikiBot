from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY or "proxy-no-key",
        openai_api_base=f"{settings.openai_base_url}/v1",
    )


def load_faiss_index() -> FAISS:
    embeddings = get_embeddings()
    return FAISS.load_local(
        settings.FAISS_STORE_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
