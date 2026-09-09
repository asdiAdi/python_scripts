"""Tests for common.prompt (PromptClient, _extract_text)."""

from __future__ import annotations

import pytest

from common import prompt as prompt_module
from common.prompt import (
    DEFAULT_MODEL,
    PromptClient,
    _extract_text,
)


def make_config(**overrides):
    """Build TOML-style config data with dummy credentials by default."""
    data = {
        "openrouter": {
            "api_key": "test-key",
            "base_url": "https://example.invalid",
        }
    }
    data["openrouter"].update(overrides)
    return data


def make_client(config=None, **kwargs):
    """Build a PromptClient with dummy credentials by default."""
    return PromptClient(config=config or make_config(), **kwargs)


# --- _extract_text ---


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, message):
        self.message = message


class _Result:
    def __init__(self, choices):
        self.choices = choices


def test_extract_text_str_content():
    result = _Result([_Choice(_Msg("hello"))])
    assert _extract_text(result) == "hello"


def test_extract_text_none_content_returns_empty():
    result = _Result([_Choice(_Msg(None))])
    assert _extract_text(result) == ""


def test_extract_text_missing_message_returns_empty():
    result = _Result([_Choice(None)])
    assert _extract_text(result) == ""


def test_extract_text_no_choices_raises():
    with pytest.raises(RuntimeError, match="no choices"):
        _extract_text(_Result([]))


def test_extract_text_missing_choices_attr_raises():
    with pytest.raises(RuntimeError, match="no choices"):
        _extract_text(object())


def test_extract_text_list_of_strings_joined():
    result = _Result([_Choice(_Msg(["foo", "bar"]))])
    assert _extract_text(result) == "foobar"


def test_extract_text_multimodal_dict_blocks():
    content = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"},
        {"type": "image", "url": "http://x"},  # no "text" -> skipped
    ]
    assert _extract_text(_Result([_Choice(_Msg(content))])) == "Hello world"


class _TextBlock:
    def __init__(self, text):
        self.text = text


def test_extract_text_multimodal_object_blocks():
    result = _Result([_Choice(_Msg([_TextBlock("a"), _TextBlock("b")]))])
    assert _extract_text(result) == "ab"


def test_extract_text_multimodal_object_without_text_skipped():
    assert _extract_text(_Result([_Choice(_Msg([object()]))])) == ""


def test_extract_text_non_str_scalar_stringified():
    assert _extract_text(_Result([_Choice(_Msg(123))])) == "123"


# --- PromptClient init ---


def test_init_reads_toml_config():
    client = PromptClient(
        config=make_config(
            api_key="file-key",
            model="file-model",
            base_url="https://file.invalid",
            timeout=2.5,
            max_tokens=99,
            app_url="https://app.file",
            app_name="FileApp",
        )
    )
    assert client.api_key == "file-key"
    assert client.model == "file-model"
    assert client.base_url == "https://file.invalid"
    assert client.timeout == 2.5
    assert client.max_tokens == 99
    assert client.app_url == "https://app.file"
    assert client.app_name == "FileApp"


def test_init_model_defaults_when_missing():
    assert PromptClient(config=make_config()).model == DEFAULT_MODEL


def test_init_missing_api_key_raises():
    with pytest.raises(RuntimeError, match="openrouter.api_key"):
        PromptClient(config=make_config(api_key=""))


def test_init_missing_base_url_raises():
    with pytest.raises(RuntimeError, match="openrouter.base_url"):
        PromptClient(config=make_config(base_url=""))


def test_init_invalid_timeout_raises():
    with pytest.raises(RuntimeError, match="openrouter.timeout must be a number"):
        PromptClient(config=make_config(timeout="not-a-number"))


def test_init_invalid_max_tokens_raises():
    with pytest.raises(RuntimeError, match="openrouter.max_tokens must be an integer"):
        PromptClient(config=make_config(max_tokens="4.5"))


def test_init_timeout_and_max_tokens_default_none():
    client = make_client()
    assert client.timeout is None
    assert client.max_tokens is None
    assert client.app_url is None
    assert client.app_name is None


# --- _client_kwargs ---


def test_client_kwargs_minimal():
    assert make_client()._client_kwargs() == {"api_key": "test-key"}


def test_client_kwargs_full():
    client = PromptClient(
        config=make_config(timeout=2.0, app_url="https://u", app_name="N")
    )
    kwargs = client._client_kwargs()
    assert kwargs == {
        "api_key": "test-key",
        "timeout_ms": 2000,
        "http_referer": "https://u",
        "x_open_router_title": "N",
    }


# --- fake OpenRouter client ---


class FakeChat:
    def __init__(self, outer):
        self.outer = outer

    def send(self, **kwargs):
        self.outer.seen_send_kwargs = kwargs

        class Msg:
            content = self.outer.reply_text

        class Choice:
            message = Msg()

        class Result:
            choices = [Choice()]

        return Result()


class FakeClient:
    """Context-manager stand-in for OpenRouter client."""

    last_instance = None

    def __init__(self, reply_text="reply", **client_kwargs):
        self.reply_text = reply_text
        self.client_kwargs = client_kwargs
        self.seen_send_kwargs = {}
        self.chat = FakeChat(self)
        FakeClient.last_instance = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_factory(reply_text="reply", capture=None):
    def factory(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        return FakeClient(reply_text=reply_text, **kwargs)

    return factory


# --- ask / chat / send_raw ---


def test_ask_builds_user_message():
    capture = {}
    client = PromptClient(
        config=make_config(model="m"), client_factory=make_factory("Paris", capture)
    )
    assert client.ask("capital?") == "Paris"
    sent = FakeClient.last_instance.seen_send_kwargs
    assert sent["messages"] == [{"role": "user", "content": "capital?"}]
    assert sent["model"] == "m"
    assert sent["stream"] is False
    assert "max_tokens" not in sent
    assert capture["api_key"] == "test-key"


def test_ask_with_system():
    client = PromptClient(
        config=make_config(model="default-m", max_tokens=10),
        client_factory=make_factory("ok"),
    )
    assert client.ask("hi", system="sys") == "ok"
    sent = FakeClient.last_instance.seen_send_kwargs
    assert sent["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    assert sent["model"] == "default-m"
    assert sent["max_tokens"] == 10


def test_ask_default_max_tokens_used():
    client = PromptClient(
        config=make_config(model="m", max_tokens=7),
        client_factory=make_factory("ok"),
    )
    client.ask("hi")
    assert FakeClient.last_instance.seen_send_kwargs["max_tokens"] == 7


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_ask_empty_prompt_raises(bad):
    with pytest.raises(RuntimeError, match="prompt text must not be empty"):
        make_client().ask(bad)


def test_chat_passthrough():
    client = PromptClient(
        config=make_config(model="m"), client_factory=make_factory("yo")
    )
    msgs = [{"role": "user", "content": "hi"}]
    assert client.chat(msgs) == "yo"
    sent = FakeClient.last_instance.seen_send_kwargs
    assert sent["messages"] == msgs
    # original list must not be the same object sent (copied via list())
    assert sent["messages"] is not msgs


def test_chat_empty_raises():
    with pytest.raises(RuntimeError, match="messages must not be empty"):
        make_client().chat([])


def test_send_raw_returns_sdk_result_unparsed():
    client = PromptClient(
        config=make_config(model="m"), client_factory=make_factory("raw-text")
    )
    result = client.send_raw([{"role": "user", "content": "hi"}])
    assert result.choices[0].message.content == "raw-text"


def test_send_propagates_empty_choices_error():
    class EmptyFake(FakeClient):
        def __init__(self, **kwargs):
            super().__init__(reply_text="", **kwargs)

            class Empty:
                choices = []

            self._empty = Empty()

    class EmptyChat:
        def __init__(self, outer):
            self.outer = outer

        def send(self, **kwargs):
            return self.outer._empty

    def factory(**kwargs):
        inst = EmptyFake(**kwargs)
        inst.chat = EmptyChat(inst)
        FakeClient.last_instance = inst
        return inst

    client = make_client(client_factory=factory)
    with pytest.raises(RuntimeError, match="no choices"):
        client.ask("hi")


def test_prompt_client_exported_from_common():
    import common

    assert common.PromptClient is PromptClient
    assert "PromptClient" in common.__all__
    assert prompt_module.DEFAULT_MODEL == DEFAULT_MODEL
