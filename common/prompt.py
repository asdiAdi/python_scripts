"""Openrouter SDK Wrapper

Usage from any script:
    from common.prompt import PromptClient

    client = PromptClient()  # reads ~/.config/ai/config.toml
    answer = client.ask("What is the capital of France?")
    answer = client.chat([{"role": "user", "content": "Hi"}])

"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

from openrouter import OpenRouter

from common.config import (
    OPENROUTER_SECTION,
    config_path,
    get_section,
    load_file,
    resolve_file_value,
)

DEFAULT_MODEL = "minimax/minimax-m3:free"  # TODO:: Add alternate models or make logic where api automatically searches for best/free models if default model is unavaliable


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
    """Reusable OpenRouter chat client for all scripts."""

    def __init__(
        self,
        client_factory: Callable[..., Any] | None = None,
        progress: bool | None = None,
        config: dict | None = None,
    ) -> None:
        section = get_section(
            config if config is not None else load_file(), OPENROUTER_SECTION
        )
        self.api_key = resolve_file_value(section.get("api_key"))
        if not self.api_key:
            raise RuntimeError(
                "error: Required config value 'openrouter.api_key' is not set. "
                f"Add openrouter.api_key to {config_path()} (ai config init)."
            )
        self.model = resolve_file_value(section.get("model"), DEFAULT_MODEL)
        self.base_url = resolve_file_value(section.get("base_url"))
        if not self.base_url:
            raise RuntimeError(
                "error: Required config value 'openrouter.base_url' is not set. "
                f"Add openrouter.base_url to {config_path()} (ai config init)."
            )
        self.app_url = resolve_file_value(section.get("app_url"))
        self.app_name = resolve_file_value(section.get("app_name"))

        raw_timeout = resolve_file_value(section.get("timeout"))
        if raw_timeout is None:
            self.timeout = None
        else:
            try:
                self.timeout = float(raw_timeout)
            except TypeError, ValueError:
                raise RuntimeError(
                    f"error: openrouter.timeout must be a number, got {raw_timeout!r}"
                )

        raw_max_tokens = resolve_file_value(section.get("max_tokens"))
        if raw_max_tokens is None:
            self.max_tokens = None
        else:
            try:
                self.max_tokens = int(raw_max_tokens)
            except TypeError, ValueError:
                raise RuntimeError(
                    f"error: openrouter.max_tokens must be an integer, got {raw_max_tokens!r}"
                )

        self._client_factory = client_factory or OpenRouter
        self.progress = progress
        self._status_len = 0

    def _progress_enabled(self) -> bool:
        if self.progress is not None:
            return bool(self.progress)
        try:
            isatty = sys.stderr.isatty()
        except Exception:
            return False
        return bool(isatty)

    def _emit_status(self, msg: str) -> None:
        if not self._progress_enabled():
            return
        try:
            use_ansi = "NO_COLOR" not in os.environ
            if use_ansi:
                sys.stderr.write(f"\r\033[2K{msg}")
            else:
                sys.stderr.write(f"\r{msg}")
            sys.stderr.flush()
            self._status_len = len(msg)
        except Exception:
            pass

    def _clear_status(self) -> None:
        if not self._progress_enabled():
            return
        try:
            use_ansi = "NO_COLOR" not in os.environ
            if use_ansi:
                sys.stderr.write("\r\033[2K\r")
            else:
                sys.stderr.write("\r" + " " * self._status_len + "\r")
            sys.stderr.flush()
            self._status_len = 0
        except Exception:
            pass

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
    ) -> str:
        resolved_model = self.model
        resolved_max_tokens = self.max_tokens

        send_kwargs: dict[str, Any] = {
            "messages": list(messages),
            "model": resolved_model,
            "stream": False,
        }
        if resolved_max_tokens is not None:
            send_kwargs["max_tokens"] = resolved_max_tokens

        self._emit_status(f"sending to {resolved_model}...")
        self._emit_status("waiting for response...")
        try:
            with self._client_factory(**self._client_kwargs()) as client:
                result = client.chat.send(**send_kwargs)
            self._emit_status("parsing response...")
            return _extract_text(result)
        finally:
            self._clear_status()

    def send_raw(
        self,
        messages: Sequence[dict[str, str]],
    ) -> Any:
        """Send messages and return the raw SDK result (no text extraction)."""
        send_kwargs: dict[str, Any] = {
            "messages": list(messages),
            "model": self.model,
            "stream": False,
        }
        if self.max_tokens is not None:
            send_kwargs["max_tokens"] = self.max_tokens

        self._emit_status(f"sending to {self.model}...")
        self._emit_status("waiting for response...")
        try:
            with self._client_factory(**self._client_kwargs()) as client:
                return client.chat.send(**send_kwargs)
        finally:
            self._clear_status()

    def ask(
        self,
        text: str,
        system: str | None = None,
    ) -> str:
        """Simple string prompt."""
        if not text or not text.strip():
            raise RuntimeError("error: prompt text must not be empty")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": text})
        return self._send(messages)

    def chat(
        self,
        messages: Sequence[dict[str, str]],
    ) -> str:
        """Full conversation prompt: chat([{"role": "user", ...}]) -> text."""
        if not messages:
            raise RuntimeError("error: messages must not be empty")
        return self._send(messages)
