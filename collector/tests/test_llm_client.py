import httpx
import pytest

from aic.config import load_config
from aic.enrich.llm_client import (
    PRESETS,
    LlmError,
    LlmSettings,
    chat_json,
    detect_provider,
    get_settings,
    list_models,
    save_settings,
)


def test_detect_provider():
    assert PRESETS["nvidia"] == "https://integrate.api.nvidia.com/v1"
    assert PRESETS["openrouter"] == "https://openrouter.ai/api/v1"
    assert detect_provider("https://integrate.api.nvidia.com/v1") == "nvidia"
    assert detect_provider("https://integrate.api.nvidia.com/v1/") == "nvidia"
    assert detect_provider("https://openrouter.ai/api/v1") == "openrouter"
    assert detect_provider("https://custom.example/v1") is None


def test_list_models_parses_and_sends_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b"}]})

    s = LlmSettings(base_url="https://integrate.api.nvidia.com/v1", api_key="nvapi-x", model="m")
    models = list_models(s, httpx.Client(transport=httpx.MockTransport(handler)))
    assert models == ["model-a", "model-b"]
    assert seen["auth"] == "Bearer nvapi-x"


def test_list_models_failure_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    s = LlmSettings(base_url="https://x.example/v1", api_key="k", model="m")
    assert list_models(s, httpx.Client(transport=httpx.MockTransport(handler))) == []

    # 연결 자체가 실패해도 예외 대신 빈 리스트
    client = httpx.Client(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))))
    assert list_models(s, client) == []


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type("R", (), {"choices": [_FakeChoice(self._content)]})()


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


THINK_OPEN = "<" + "think" + ">"
THINK_CLOSE = "</" + "think" + ">"


def test_chat_json_strips_think_blocks():
    s = LlmSettings(base_url="https://x/v1", api_key="k", model="m")
    content = THINK_OPEN + "생각 중... 답은 {\"x\": 9}" + THINK_CLOSE + '{"a": 1}'
    out = chat_json(s, "sys", "user", client=_FakeClient(content))
    assert out == {"a": 1}


def test_settings_roundtrip_extra(db):
    save_settings(db, LlmSettings(base_url="https://integrate.api.nvidia.com/v1",
                                  api_key="k", model="z-ai/glm-5.3-flash",
                                  extra={"chat_template_kwargs": {"thinking": False}}))
    s = get_settings(db)
    assert s.model == "z-ai/glm-5.3-flash"
    assert s.extra == {"chat_template_kwargs": {"thinking": False}}


def test_chat_json_passes_extra_body_and_falls_back():
    recorded = {"kwargs": []}

    class _RecordingCompletions:
        def create(self, **kwargs):
            recorded["kwargs"].append(kwargs)
            if len(recorded["kwargs"]) == 1:
                raise RuntimeError("unsupported parameter: chat_template_kwargs")
            return type("R", (), {"choices": [_FakeChoice('{"ok": true}') ]})()

    class _RecordingClient:
        def __init__(self):
            self.chat = type("Chat", (), {})()
            self.chat.completions = _RecordingCompletions()

    s = LlmSettings(base_url="https://x/v1", api_key="k", model="m",
                    extra={"chat_template_kwargs": {"thinking": False}})
    out = chat_json(s, "sys", "user", client=_RecordingClient())
    assert out == {"ok": True}
    assert recorded["kwargs"][0].get("extra_body") == {"chat_template_kwargs": {"thinking": False}}
    assert "extra_body" not in recorded["kwargs"][1]


def test_chat_json_plain_and_codefence():
    s = LlmSettings(base_url="https://x/v1", api_key="k", model="m")
    out = chat_json(s, "sys", "user", client=_FakeClient('{"a": 1, "b": ["x"]}'))
    assert out == {"a": 1, "b": ["x"]}

    fenced = "설명입니다.\n```json\n{\"summary\": \"요약\", \"n\": 2}\n```\n끝"
    out2 = chat_json(s, "sys", "user", client=_FakeClient(fenced))
    assert out2 == {"summary": "요약", "n": 2}


def test_chat_json_failure_raises_llm_error():
    s = LlmSettings(base_url="https://x/v1", api_key="k", model="m")
    with pytest.raises(LlmError):
        chat_json(s, "sys", "user", client=_FakeClient("전혀 JSON이 아닌 텍스트"))


def test_config_table_overrides_env(db):
    cfg = load_config()
    default = LlmSettings(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key, model=cfg.llm_model)
    assert get_settings(db) == default

    save_settings(db, LlmSettings(base_url="https://openrouter.ai/api/v1",
                                  api_key="sk-or", model="x/y"))
    s = get_settings(db)
    assert (s.base_url, s.api_key, s.model) == ("https://openrouter.ai/api/v1", "sk-or", "x/y")
