import logging

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text

from app.api.deps import auth_deps, get_retriever, get_db
from app.core.config import settings
from app.db.repo import save_dialog
from app.memory.memory import get_history, add_message, clear_history
from app.rag.chain import ask_rag
from app.services.audio import transcribe_audio
from app.services.image import describe_image

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health(request: Request, session: AsyncSession = Depends(get_db)):
    faiss_status = "not_loaded"
    faiss_chunks = 0
    if hasattr(request.app.state, "retriever") and request.app.state.retriever is not None:
        faiss_status = "loaded"
        faiss_chunks = request.app.state.retriever.index.ntotal

    db_status = "disconnected"
    try:
        await session.execute(sa_text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Health check: DB connection failed")

    status = "ok" if faiss_status == "loaded" and db_status == "connected" else "degraded"

    return {
        "status": status,
        "faiss": faiss_status,
        "faiss_chunks": faiss_chunks,
        "db": db_status,
    }


def _format_result(result: dict) -> dict:
    if not settings.RETURN_DEBUG:
        result.pop("debug", None)
    return result


@router.post("/ask-text")
async def ask_text(
    user_id: str = Depends(auth_deps),
    retriever=Depends(get_retriever),
    session: AsyncSession = Depends(get_db),
    text: str = Form(default=None),
    image: UploadFile | None = File(default=None),
):
    logger.info("/ask-text user=%s text=%s image=%s", user_id, bool(text), image is not None)

    parts: list[str] = []

    if text:
        parts.append(text)

    if image:
        image_bytes = await image.read()
        logger.info("Распознаю изображение для user=%s …", user_id)
        description = await describe_image(image_bytes)
        parts.append(f"[Описание изображения]: {description}")

    if not parts:
        return {"answer": "Пожалуйста, отправьте текст или изображение.", "citations": []}

    final_question = "\n".join(parts)
    history = get_history(user_id)
    result = await ask_rag(retriever, final_question, history, user_id=user_id)

    add_message(user_id, "user", final_question)
    add_message(user_id, "assistant", result["answer"])

    try:
        await save_dialog(session, user_id, final_question, result["answer"])
        logger.info("Диалог сохранён в БД для user=%s", user_id)
    except Exception:
        logger.exception("Ошибка записи в БД для user=%s (ответ уже сформирован)", user_id)

    return _format_result(result)


@router.post("/ask-audio")
async def ask_audio(
    user_id: str = Depends(auth_deps),
    retriever=Depends(get_retriever),
    session: AsyncSession = Depends(get_db),
    audio: UploadFile = File(...),
    image: UploadFile | None = File(default=None),
):
    logger.info("/ask-audio user=%s filename=%s image=%s", user_id, audio.filename, image is not None)

    audio_bytes = await audio.read()
    transcript = await transcribe_audio(audio_bytes, filename=audio.filename or "audio.mp3")
    logger.info("Транскрипция user=%s: %s", user_id, transcript[:200])

    parts: list[str] = [transcript]

    if image:
        image_bytes = await image.read()
        logger.info("Распознаю изображение для user=%s …", user_id)
        description = await describe_image(image_bytes)
        parts.append(f"[Описание изображения]: {description}")

    final_question = "\n".join(parts)
    history = get_history(user_id)
    result = await ask_rag(retriever, final_question, history, user_id=user_id)

    add_message(user_id, "user", final_question)
    add_message(user_id, "assistant", result["answer"])

    try:
        await save_dialog(session, user_id, final_question, result["answer"])
        logger.info("Диалог сохранён в БД для user=%s", user_id)
    except Exception:
        logger.exception("Ошибка записи в БД для user=%s (ответ уже сформирован)", user_id)

    return _format_result(result)


@router.post("/memory/clear")
async def memory_clear(
    user_id: str = Depends(auth_deps),
):
    clear_history(user_id)
    logger.info("Память очищена для user=%s", user_id)
    return {"status": "ok", "message": f"История пользователя {user_id} очищена"}
