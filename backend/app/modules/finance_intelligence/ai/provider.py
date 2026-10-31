"""LLM provider abstraction.

``AI_PROVIDER`` selects the backend: ``openai`` | ``gemini`` | ``none``.
- openai → POST /v1/chat/completions (httpx, AI_API_KEY, AI_MODEL).
- gemini → POST /v1beta/models/{model}:generateContent (httpx, AI_API_KEY).
- none   → TemplateProvider: deterministic grounded text composed from the
           supplied metrics. It is NOT an LLM — responses are marked
           provider='template' so callers and users can tell the difference.

Every provider implements ``generate(system, user, max_tokens) -> LLMResult``.
Timeouts are explicit (``AI_TIMEOUT_S``); failures raise ``LLMError`` so the
copilot can degrade to the template path instead of erroring the request.
"""

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from ....core.config import Settings

logger = logging.getLogger("brightloop.finance_ai")


class LLMError(Exception):
    """Provider failure (network, auth, quota, malformed response)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str | None


class LLMProvider(Protocol):
    name: str

    def generate(self, *, system: str, user: str, max_tokens: int) -> LLMResult: ...


class TemplateProvider:
    """Deterministic fallback — renders the supplied answer skeleton.

    Callers pass an already-structured ``user`` payload; the summarizer and
    copilot keep their own template renderers, so this provider simply
    echoes the composed text. It never invents numbers because it never
    sees raw data — only strings the analytics layer already produced.
    """

    name = "template"

    def generate(self, *, system: str, user: str, max_tokens: int) -> LLMResult:
        return LLMResult(text=user.strip(), provider=self.name, model=None)


class OpenAIProvider:
    name = "openai"
    _URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout_s: float):
        self._key = api_key
        self._model = model
        self._timeout = timeout_s

    def generate(self, *, system: str, user: str, max_tokens: int) -> LLMResult:
        try:
            resp = httpx.post(
                self._URL,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"openai request failed: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"openai HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            text = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"openai malformed response: {exc}") from exc
        return LLMResult(text=text.strip(), provider=self.name, model=self._model)


class GeminiProvider:
    name = "gemini"
    _URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, timeout_s: float):
        self._key = api_key
        self._model = model
        self._timeout = timeout_s

    def generate(self, *, system: str, user: str, max_tokens: int) -> LLMResult:
        try:
            resp = httpx.post(
                self._URL.format(model=self._model),
                params={"key": self._key},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": 0.2,
                    },
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"gemini request failed: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"gemini HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"gemini malformed response: {exc}") from exc
        if not text.strip():
            raise LLMError("gemini returned empty content")
        return LLMResult(text=text.strip(), provider=self.name, model=self._model)


def build_provider(settings: Settings) -> LLMProvider:
    """Factory — 'none', missing keys or unknown providers all degrade to
    the template path so AI features work offline and in CI."""
    kind = (settings.AI_PROVIDER or "none").lower()
    if kind == "openai" and settings.AI_API_KEY:
        return OpenAIProvider(settings.AI_API_KEY, settings.AI_MODEL, settings.AI_TIMEOUT_S)
    if kind == "gemini" and settings.AI_API_KEY:
        return GeminiProvider(settings.AI_API_KEY, settings.AI_MODEL, settings.AI_TIMEOUT_S)
    if kind not in ("none", "template"):
        logger.warning("AI_PROVIDER=%r unusable (missing key or unknown) — template fallback", kind)
    return TemplateProvider()


class RateLimiter:
    """Per-user sliding-window limiter for expensive AI endpoints.

    In-memory and per-process — adequate for a single Render web service;
    document that horizontal scaling weakens it.
    """

    def __init__(self, limit_per_minute: int):
        self._limit = max(limit_per_minute, 0)
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        if self._limit <= 0:
            return True
        now = time.monotonic()
        window = self._hits.setdefault(key, [])
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= self._limit:
            return False
        window.append(now)
        return True
