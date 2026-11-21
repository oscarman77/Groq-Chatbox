"""LLM calls: an OpenAI-compatible endpoint, with a mock fallback."""

from typing import Iterable, Mapping

import httpx

from . import config

SYSTEM_PROMPT = (
    "You are Chatbox, a concise assistant inside a small demo app. "
    "Answer in clear prose. Prefer short paragraphs over long lists."
)


class LLMError(RuntimeError):
    """Raised when the upstream provider fails."""


def _mock_reply(messages: Iterable[Mapping[str, str]]) -> str:
    last_user = ""
    for message in reversed(list(messages)):
        if message["role"] == "user":
            last_user = message["content"]
            break

    preview = last_user.strip().replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:160] + "..."

    return (
        f"[mock mode] I received: \"{preview}\"\n\n"
        "No LLM_API_KEY is set, so this reply is generated locally. "
        "Create a .env file next to this project with:\n\n"
        "    LLM_API_KEY=sk-...\n"
        "    LLM_MODEL=gpt-4o-mini\n\n"
        "and restart the server to talk to a real model. "
        "Any OpenAI-compatible base URL works too, via LLM_BASE_URL."
    )


async def complete(messages: list[dict[str, str]]) -> str:
    """Send a chat completion request and return the assistant text."""
    if config.MOCK_MODE:
        return _mock_reply(messages)

    payload = {
        "model": config.LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as client:
            response = await client.post(
                f"{config.LLM_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM provider: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:300]
        raise LLMError(f"Provider returned {response.status_code}: {detail}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Unexpected response shape from the LLM provider") from exc
