import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import router
from app.db.models import Base
from app.db.session import engine
from app.rag.store import load_faiss_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск %s на %s:%s", settings.PROJECT_NAME, settings.API_HOST, settings.API_PORT)
    logger.info("OpenAI base_url=%s", settings.openai_base_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL: таблицы созданы / проверены (url=%s)", settings.DATABASE_URL.split("@")[-1])

    logger.info("Загружаю FAISS индекс из %s …", settings.FAISS_STORE_PATH)
    index = load_faiss_index()
    chunks_count = index.index.ntotal
    app.state.retriever = index
    logger.info("FAISS loaded: %d chunks, path=%s", chunks_count, settings.FAISS_STORE_PATH)

    yield

    logger.info("Завершение работы, закрытие соединений…")
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.include_router(router)
