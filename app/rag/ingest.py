"""Построение FAISS-индекса из .txt в data/knowledge. Запуск: python -m app.rag.ingest"""

import asyncio
import logging
import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.store import get_embeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(={2,})\s*(.+?)\s*\1\s*$", re.MULTILINE)


def _detect_section(text: str, char_start: int, full_text: str) -> str | None:
    best_title: str | None = None
    for m in _HEADING_RE.finditer(full_text):
        if m.start() <= char_start:
            best_title = m.group(2).strip()
        else:
            break
    return best_title


def load_documents(knowledge_dir: str) -> list[Document]:
    docs: list[Document] = []
    knowledge_path = Path(knowledge_dir)

    for txt_file in sorted(knowledge_path.glob("*.txt")):
        logger.info("Читаю файл: %s", txt_file.name)
        content = txt_file.read_text(encoding="utf-8")
        docs.append(Document(page_content=content, metadata={"source": txt_file.name}))

    logger.info("Загружено %d файлов", len(docs))
    return docs


def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Document] = []
    for doc in docs:
        full_text = doc.page_content
        source = doc.metadata["source"]
        splits = splitter.split_text(full_text)

        offset = 0
        for idx, chunk_text in enumerate(splits):
            char_start = full_text.find(chunk_text, offset)
            if char_start == -1:
                char_start = offset
            char_end = char_start + len(chunk_text)

            section = _detect_section(chunk_text, char_start, full_text)

            chunks.append(
                Document(
                    page_content=chunk_text,
                    metadata={
                        "source": source,
                        "chunk_id": idx,
                        "section": section,
                        "char_start": char_start,
                        "char_end": char_end,
                    },
                )
            )
            offset = char_start + 1

    logger.info("Всего чанков: %d", len(chunks))
    return chunks


async def build_index() -> None:
    raw_docs = load_documents(settings.KNOWLEDGE_PATH)
    if not raw_docs:
        logger.error("Нет .txt файлов в %s", settings.KNOWLEDGE_PATH)
        return

    chunks = split_documents(raw_docs)
    embeddings = get_embeddings()

    logger.info("Создаю FAISS индекс (модель: %s) …", settings.EMBEDDING_MODEL)
    index = await asyncio.to_thread(FAISS.from_documents, chunks, embeddings)

    store_path = Path(settings.FAISS_STORE_PATH)
    store_path.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(index.save_local, str(store_path))
    logger.info("Индекс сохранён в %s (%d чанков)", store_path, index.index.ntotal)


if __name__ == "__main__":
    asyncio.run(build_index())
