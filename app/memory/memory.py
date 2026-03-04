from collections import defaultdict

from app.core.config import settings

_store: dict[str, list[dict]] = defaultdict(list)


def get_history(user_id: str) -> list[dict]:
    return list(_store[user_id])


def add_message(user_id: str, role: str, content: str) -> None:
    _store[user_id].append({"role": role, "content": content})
    if len(_store[user_id]) > settings.MEMORY_MAX_MESSAGES:
        _store[user_id] = _store[user_id][-settings.MEMORY_MAX_MESSAGES:]


def clear_history(user_id: str) -> None:
    _store[user_id].clear()
