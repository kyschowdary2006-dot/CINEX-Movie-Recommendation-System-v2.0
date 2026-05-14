"""
CINEX AI Agent — powered by Groq (FREE API) with Llama 3.

Drop this file into app/agent/agent.py.
The same /api/agent/chat endpoint in main.py works with no changes.

Get your FREE API key at: https://console.groq.com
Add to your env file:  GROQ_API_KEY=gsk_xxxxxxxxxxxx
"""

import json
import os
import logging
from typing import Any

from groq import Groq

from app.agent.memory import add_message, get_history
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_REGISTRY
from app.config import settings

logger = logging.getLogger(__name__)

# ── Groq client — key loaded from .env via settings ──────────────────────────
_client = Groq(api_key=settings.GROQ_API_KEY)

# Free models available on Groq:
#   "llama-3.3-70b-versatile"   ← best quality (recommended)
#   "llama-3.1-8b-instant"      ← faster / lighter
#   "gemma2-9b-it"              ← good alternative
MODEL = "llama-3.3-70b-versatile"

# ── Tool schemas (Groq uses OpenAI function-calling format) ───────────────────
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": (
                "Search the CINEX movie database by title or keyword. "
                "Returns matching movies with their IDs, titles, release dates, and ratings. "
                "Always call this first before recommend_similar so you have a real movie ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Title fragment or genre keyword, e.g. 'inception' or 'thriller'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 6)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_similar",
            "description": (
                "Get movies similar to a given movie using the CINEX ML recommendation engine. "
                "Requires a valid numeric movie ID — use search_movies first to get the ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "Numeric CINEX movie ID (from search_movies results)",
                    },
                    "n": {
                        "type": "integer",
                        "description": "Number of recommendations to return (default 5)",
                    },
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_ratings",
            "description": (
                "Retrieve all movies the current user has rated. "
                "Use this to personalise recommendations or answer questions about their watch history."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────
def _run_tool(name: str, inputs: dict, user_id: int) -> Any:
    """Execute a named tool and return a JSON-serialisable result."""
    try:
        if name == "search_movies":
            return TOOL_REGISTRY["search_movies"](
                inputs.get("query", ""), limit=inputs.get("limit", 6)
            )
        if name == "recommend_similar":
            return TOOL_REGISTRY["recommend_similar"](
                inputs["movie_id"], n=inputs.get("n", 5)
            )
        if name == "get_user_ratings":
            return TOOL_REGISTRY["get_user_ratings"](user_id)
        return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return {"error": str(exc)}


# ── Main chat function ────────────────────────────────────────────────────────
def chat(user_id: int, message: str) -> str:
    """
    Process a user message through the Groq/Llama3 agent with tool-calling.
    Returns the final reply as a plain string (Markdown supported).
    """
    # Save user message to memory
    add_message(user_id, "user", message)

    # Build message list: system prompt + conversation history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + get_history(user_id)

    MAX_TOOL_ROUNDS = 5

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            response = _client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
            )
        except Exception as exc:
            logger.error("Groq API error: %s", exc)
            err = str(exc)
            if not settings.GROQ_API_KEY:
                return "⚠️ GROQ_API_KEY is missing. Add it to your .env file and restart the server."
            if "401" in err or "invalid_api_key" in err.lower() or "authentication" in err.lower():
                return "⚠️ Your GROQ_API_KEY is invalid. Get a free key at console.groq.com and update your .env file."
            return f"⚠️ AI error: {err[:120]}. Please try again."

        choice = response.choices[0]
        msg = choice.message

        # Append assistant turn as a plain dict (avoids serialization issues)
        assistant_turn: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_turn["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_turn)

        # No tool calls → this is the final answer
        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            if not reply:
                reply = "I couldn't find anything helpful for that. Try asking differently!"
            add_message(user_id, "assistant", reply)
            return reply

        # Execute each tool call and append results
        for tc in msg.tool_calls:
            try:
                inputs = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, ValueError):
                inputs = {}

            result = _run_tool(tc.function.name, inputs, user_id)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    # Fallback if MAX_TOOL_ROUNDS exhausted
    fallback = "I ran into a problem processing your request. Please try again!"
    add_message(user_id, "assistant", fallback)
    return fallback
