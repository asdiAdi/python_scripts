"""Openrouter SDK Wrapper

Usage from any script:
    from common.prompt import PromptClient

    client = PromptClient()  # reads .env / environment
    answer = client.ask("What is the capital of France?")
    answer = client.chat([{"role": "user", "content": "Hi"}])

"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any

from dotenv import load_dotenv
from openrouter import OpenRouter

load_dotenv()

DEFAULT_MODEL = "minimax/minimax-m3:free"  # TODO:: Add alternate models or make logic where api automatically searches for best/free models if default model is unavaliable

ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "OPENROUTER_MODEL"
ENV_BASE_URL = "OPENROUTER_BASE_URL"
ENV_TIMEOUT = "OPENROUTER_TIMEOUT"
ENV_MAX_TOKENS = "OPENROUTER_MAX_TOKENS"
ENV_APP_URL = "OPENROUTER_APP_URL"
ENV_APP_NAME = "OPENROUTER_APP_NAME"


def _getenv(name: str, default: str | None = None, required: bool = True) -> str | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        if default is not None:
            return default
        if required:
            raise RuntimeError(
                f"error: Required environment variable '{name}' is not set."
            )
        return None
    return raw.strip()


def _extract_text(result: Any) -> str:
    """Pull the assistant text out of an OpenRouter ChatResult."""
    try:
        choices = getattr(result, "choices", None)
        if not choices:
            raise RuntimeError("error: empty response from model (no choices)")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message is not None else None
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize SDK shape changes
        raise RuntimeError(f"error: could not parse model response: {exc}") from exc

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Multimodal content blocks: [{"type": "text", "text": "..."}, ...]
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


class PromptClient:
    """Reusable OpenRouter chat client for all scripts.

    Args:
        api_key: Explicit key.
        model: Default model.
        base_url: Override server URL.
        timeout: Request timeout in seconds.
        max_tokens: Default completion cap.
        app_url: App URL for OpenRouter rankings.
        app_name: App display name.
        client_factory: Factory returning a context-manager OpenRouter client.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_tokens: int | None = None,
        app_url: str | None = None,
        app_name: str | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key or _getenv(ENV_API_KEY)
        self.model = model or _getenv(ENV_MODEL, DEFAULT_MODEL, required=False)
        self.base_url = base_url or _getenv(ENV_BASE_URL)
        self.app_url = app_url or _getenv(ENV_APP_URL, required=False)
        self.app_name = app_name or _getenv(ENV_APP_NAME, required=False)

        if timeout is not None:
            self.timeout = timeout
        else:
            raw_timeout = _getenv(ENV_TIMEOUT, required=False)
            if raw_timeout is None:
                self.timeout = None
            else:
                try:
                    self.timeout = float(raw_timeout)
                except ValueError:
                    raise RuntimeError(
                        f"error: {ENV_TIMEOUT} must be a number, got {raw_timeout!r}"
                    )

        if max_tokens is not None:
            self.max_tokens = max_tokens
        else:
            raw_max_tokens = _getenv(ENV_MAX_TOKENS, None, required=False)
            if raw_max_tokens is None:
                self.max_tokens = None
            else:
                try:
                    self.max_tokens = int(raw_max_tokens)
                except ValueError:
                    raise RuntimeError(
                        f"error: {ENV_MAX_TOKENS} must be an integer, got {raw_max_tokens!r}"
                    )

        self._client_factory = client_factory or OpenRouter

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        # if self.base_url:
        #     kwargs["server_url"] = self.base_url
        if self.timeout is not None:
            kwargs["timeout_ms"] = int(self.timeout * 1000)
        if self.app_url:
            kwargs["http_referer"] = self.app_url
        if self.app_name:
            kwargs["x_open_router_title"] = self.app_name
        return kwargs

    def _send(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resolved_model = model or self.model
        resolved_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        send_kwargs: dict[str, Any] = {
            "messages": list(messages),
            "model": resolved_model,
            "stream": False,
        }
        if resolved_max_tokens is not None:
            send_kwargs["max_tokens"] = resolved_max_tokens

        with self._client_factory(**self._client_kwargs()) as client:
            result = client.chat.send(**send_kwargs)
        return _extract_text(result)

    def send_raw(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Send messages and return the raw SDK result (no text extraction)."""
        resolved_model = model or self.model
        resolved_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        send_kwargs: dict[str, Any] = {
            "messages": list(messages),
            "model": resolved_model,
            "stream": False,
        }
        if resolved_max_tokens is not None:
            send_kwargs["max_tokens"] = resolved_max_tokens

        with self._client_factory(**self._client_kwargs()) as client:
            return client.chat.send(**send_kwargs)

    def ask(
        self,
        text: str,
        model: str | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> str:
        """Simple string prompt."""
        if not text or not text.strip():
            raise RuntimeError("error: prompt text must not be empty")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": text})
        return self._send(messages, model=model, max_tokens=max_tokens)

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Full conversation prompt: chat([{"role": "user", ...}]) -> text."""
        if not messages:
            raise RuntimeError("error: messages must not be empty")
        return self._send(messages, model=model, max_tokens=max_tokens)
