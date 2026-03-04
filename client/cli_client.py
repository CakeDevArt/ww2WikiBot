"""Интерактивный CLI для запросов к API. Запуск: python -m client.cli_client"""

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

API_BASE = f"http://localhost:{settings.API_PORT}"
USER_ID = "cli_user"


async def ask(question: str) -> None:
    headers = {
        "X-API-Key": settings.API_KEY,
        "X-User-Id": USER_ID,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{API_BASE}/ask-text",
            headers=headers,
            data={"text": question},
        )
        resp.raise_for_status()
        result = resp.json()

    print(f"\nОтвет: {result['answer']}")
    citations = result.get("citations") or result.get("sources") or []
    if citations:
        print("\nИсточники:")
        for i, c in enumerate(citations, 1):
            src = c.get("source", "?") if isinstance(c, dict) else str(c)
            section = c.get("section", "") if isinstance(c, dict) else ""
            label = f"{src} [{section}]" if section else src
            print(f"  {i}. {label}")


async def main():
    print("WW2 RAG Консультант — CLI")
    print("Введите 'exit' для выхода.\n")

    while True:
        try:
            question = input("Вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question or question.lower() in ("exit", "quit", "q"):
            break

        try:
            await ask(question)
        except Exception as e:
            print(f"Ошибка: {e}")

        print()


if __name__ == "__main__":
    asyncio.run(main())
