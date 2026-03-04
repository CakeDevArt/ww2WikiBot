"""Telegram-бот: текст и голос -> API -> ответ. Запуск: python -m bot.telegram_bot"""

import asyncio
import io
import logging
import os
import re
import sys

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

API_BASE = settings.BOT_API_BASE or f"http://localhost:{settings.API_PORT}"
HEADERS = {
    "X-API-Key": settings.API_KEY,
}

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    "Привет! Меня зовут Григорий, я историк Великой Отечественной войны 🇷🇺\n\n"
    "Могу ответить на вопросы о событиях войны, датах, "
    "ключевых сражениях, операциях и других важных фактах 📚\n\n"
    "Мои темы:\n\n"
    "— Великая Отечественная война\n"
    "— операция «Барбаросса»\n"
    "— битва за Москву\n"
    "— Сталинградская битва\n"
    "— блокада Ленинграда\n\n"
    "Можно написать вопрос текстом, отправить фото или голосовое сообщение 🎤\n"
    "\n"
    "Команда /clear — очистить историю диалога."
)

_REF_RE = re.compile(r"\s*\[(\d+)\](?:\s*,\s*\[(\d+)\])*")


def _clean_answer(text: str) -> str:
    text = _REF_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _user_id(msg: Message) -> str:
    return f"tg_{msg.from_user.id}"


@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(WELCOME_TEXT)


@dp.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(WELCOME_TEXT)


@dp.message(Command("clear"))
async def handle_clear(message: Message):
    user_id = _user_id(message)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{API_BASE}/memory/clear",
                headers={**HEADERS, "X-User-Id": user_id},
            )
            resp.raise_for_status()
        await message.answer("История диалога очищена. Можете начать с чистого листа.")
    except Exception as e:
        logger.exception("Ошибка при очистке памяти")
        await message.answer(f"Не удалось очистить историю: {e}")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    user_id = _user_id(message)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{API_BASE}/ask-text",
                headers={**HEADERS, "X-User-Id": user_id},
                data={"text": message.text},
            )
            resp.raise_for_status()
            result = resp.json()
        answer = _clean_answer(result.get("answer", "Нет ответа"))
        await message.answer(answer)
    except Exception as e:
        logger.exception("Ошибка при обработке текста")
        await message.answer(f"Произошла ошибка: {e}")


@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = _user_id(message)
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        buffer = io.BytesIO()
        await bot.download_file(file.file_path, buffer)
        buffer.seek(0)

        caption = message.caption or "Опиши что на этом изображении в контексте ВОВ"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{API_BASE}/ask-text",
                headers={**HEADERS, "X-User-Id": user_id},
                data={"text": caption},
                files={"image": ("photo.jpg", buffer.read(), "image/jpeg")},
            )
            resp.raise_for_status()
            result = resp.json()
        answer = _clean_answer(result.get("answer", "Нет ответа"))
        await message.answer(answer)
    except Exception as e:
        logger.exception("Ошибка при обработке фото")
        await message.answer(f"Произошла ошибка: {e}")


@dp.message(F.voice)
async def handle_voice(message: Message):
    user_id = _user_id(message)
    try:
        file = await bot.get_file(message.voice.file_id)
        buffer = io.BytesIO()
        await bot.download_file(file.file_path, buffer)
        buffer.seek(0)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{API_BASE}/ask-audio",
                headers={**HEADERS, "X-User-Id": user_id},
                files={"audio": ("voice.ogg", buffer.read(), "audio/ogg")},
            )
            resp.raise_for_status()
            result = resp.json()
        answer = _clean_answer(result.get("answer", "Нет ответа"))
        await message.answer(answer)
    except Exception as e:
        logger.exception("Ошибка при обработке голосового")
        await message.answer(f"Произошла ошибка: {e}")


@dp.message()
async def handle_unsupported(message: Message):
    await message.answer(
        "Я принимаю только текст, фото или голосовое сообщение.\n"
        "Попробуйте задать вопрос одним из этих способов."
    )


async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
