"""
In-memory conversation history per user session.
Stores plain dicts compatible with Groq/OpenAI message format.
"""
from collections import defaultdict
from typing import Union

_store: dict[str, list[dict]] = defaultdict(list)
MAX_TURNS = 10  # keep last 10 user+assistant pairs


def add_message(session_id: Union[int, str], role: str, content: str) -> None:
    key = str(session_id)
    _store[key].append({"role": role, "content": content})
    # Trim to MAX_TURNS pairs (×2 for user+assistant)
    if len(_store[key]) > MAX_TURNS * 2:
        _store[key] = _store[key][-MAX_TURNS * 2:]


def get_history(session_id: Union[int, str]) -> list[dict]:
    """Return a copy of the conversation as plain dicts (safe to mutate)."""
    return [{"role": m["role"], "content": m["content"]}
            for m in _store[str(session_id)]]


def clear(session_id: Union[int, str]) -> None:
    _store.pop(str(session_id), None)
