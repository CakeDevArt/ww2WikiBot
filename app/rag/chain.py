import logging
import re
import time

import httpx
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.prompts import SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE, REWRITE_PROMPT, CLARIFY_PROMPT

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 1500
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _normalize_chunk(text: str) -> str:
    text = _MULTI_NEWLINE.sub("\n\n", text).strip()
    if len(text) > _MAX_CHUNK_CHARS:
        text = text[:_MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def _extract_quote(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=2)
    quote = " ".join(sentences[:2]).strip()
    if len(quote) > 300:
        quote = quote[:300].rsplit(" ", 1)[0] + "…"
    return quote


async def _llm_call(
    model: str,
    messages: list[dict],
    max_tokens: int = 2000,
    temperature: float | None = None,
) -> str:
    payload: dict = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.openai_base_url}/v1/chat/completions",
            headers=settings.openai_headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


async def rewrite_query(history: list[dict], question: str) -> str:
    if history:
        msgs: list[dict] = [{"role": "system", "content": REWRITE_PROMPT}]
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history[-6:]
        )
        msgs.append({"role": "user", "content": f"История:\n{history_text}\n\nВопрос: {question}"})
    else:
        msgs = [
            {"role": "system", "content": CLARIFY_PROMPT},
            {"role": "user", "content": question},
        ]

    try:
        rewritten = await _llm_call(settings.REWRITE_MODEL, msgs, max_tokens=300, temperature=0)
        return rewritten or question
    except Exception:
        logger.warning("Query rewrite failed, using original", exc_info=True)
        return question


async def retrieve(retriever: FAISS, query: str, k: int = 6) -> list[Document]:
    return await retriever.asimilarity_search(query, k=k)


def build_citations(docs: list[Document]) -> list[dict]:
    citations = []
    seen = set()
    for doc in docs:
        meta = doc.metadata or {}
        key = (meta.get("source", ""), meta.get("chunk_id", ""))
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "source": meta.get("source", "unknown"),
            "chunk_id": meta.get("chunk_id"),
            "section": meta.get("section") or None,
            "quote": _extract_quote(doc.page_content),
        })
    return citations


async def generate_answer(
    question: str,
    docs: list[Document],
    history: list[dict],
) -> str:
    numbered_chunks = []
    for i, doc in enumerate(docs, 1):
        normalized = _normalize_chunk(doc.page_content)
        src = doc.metadata.get("source", "?")
        numbered_chunks.append(f"[{i}] (источник: {src})\n{normalized}")

    context = "\n\n".join(numbered_chunks)

    history_text = ""
    if history:
        lines = []
        for msg in history:
            role = "Пользователь" if msg["role"] == "user" else "Ассистент"
            lines.append(f"{role}: {msg['content']}")
        history_text = "\n".join(lines)

    user_prompt = RAG_PROMPT_TEMPLATE.format(
        context=context,
        history=history_text,
        question=question,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    return await _llm_call(settings.CHAT_MODEL, messages, max_tokens=800)


async def ask_rag(
    retriever: FAISS,
    question: str,
    history: list[dict],
    user_id: str = "",
) -> dict:
    t0 = time.monotonic()

    rewritten = await rewrite_query(history, question)
    t_rewrite = time.monotonic() - t0
    logger.info(
        "RAG rewrite user=%s (%.2fs) original=%s rewritten=%s",
        user_id, t_rewrite, question[:100], rewritten[:100],
    )

    t1 = time.monotonic()
    docs = await retrieve(retriever, rewritten, k=4)
    t_retrieve = time.monotonic() - t1
    chunk_ids = [f"{d.metadata.get('source','?')}:{d.metadata.get('chunk_id','?')}" for d in docs]
    logger.info(
        "RAG retrieve user=%s retrieved=%d chunks (%.2fs) ids=%s",
        user_id, len(docs), t_retrieve, chunk_ids,
    )

    citations = build_citations(docs)

    t2 = time.monotonic()
    answer = await generate_answer(question, docs, history)
    t_llm = time.monotonic() - t2

    total = time.monotonic() - t0
    logger.info(
        "RAG done user=%s rewrite=%.2fs retrieve=%.2fs llm=%.2fs total=%.2fs answer_len=%d citations=%d",
        user_id, t_rewrite, t_retrieve, t_llm, total, len(answer), len(citations),
    )

    debug = {
        "retrieved_k": len(docs),
        "original_query": question,
        "rewritten_query": rewritten,
        "used_history_messages": len(history),
        "timing": {
            "rewrite_s": round(t_rewrite, 2),
            "retrieve_s": round(t_retrieve, 2),
            "llm_s": round(t_llm, 2),
            "total_s": round(total, 2),
        },
    }

    return {"answer": answer, "citations": citations, "debug": debug}
