"""LLM 클라이언트 — OpenAI 호환 엔드포인트(NIM/OpenRouter/커스텀) 공용.

설정 우선순위: config 테이블('llm' 키) > .env/환경변수.
admin UI가 save_settings로 테이블을 갱신하면 수집기가 즉시 따라간다.
"""
import json
import re
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import httpx
from openai import OpenAI

from aic.config import load_config

PRESETS: dict[str, str] = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class LlmError(Exception):
    """LLM 호출 또는 응답 파싱 실패."""


@dataclass
class LlmSettings:
    base_url: str
    api_key: str | None
    model: str


def detect_provider(base_url: str) -> str | None:
    normalized = (base_url or "").rstrip("/")
    for name, url in PRESETS.items():
        if normalized == url.rstrip("/"):
            return name
    return None


def get_settings(conn) -> LlmSettings:
    row = conn.execute("SELECT value FROM config WHERE key = 'llm'").fetchone()
    if row:
        v = row[0] or {}
        cfg = load_config()
        return LlmSettings(
            base_url=v.get("base_url") or cfg.llm_base_url,
            api_key=v.get("api_key") or cfg.llm_api_key,
            model=v.get("model") or cfg.llm_model,
        )
    cfg = load_config()
    return LlmSettings(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key, model=cfg.llm_model)


def save_settings(conn, s: LlmSettings) -> None:
    conn.execute(
        """
        INSERT INTO config (key, value, updated_at)
        VALUES ('llm', %s, now())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (json.dumps(asdict(s)),),
    )


def list_models(s: LlmSettings, client: httpx.Client) -> list[str]:
    """GET {base}/models → 모델 id 목록. 실패 시 빈 리스트(드롭다운 폴백용)."""
    url = s.base_url.rstrip("/") + "/models"
    headers = {}
    if s.api_key:
        headers["Authorization"] = f"Bearer {s.api_key}"
    try:
        resp = client.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        return [m["id"] for m in data if isinstance(m, dict) and m.get("id")]
    except Exception:
        return []


def _extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{", t)
    if m:
        try:
            obj, _ = json.JSONDecoder().raw_decode(t[m.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise LlmError(f"no valid JSON object in LLM response: {text[:120]!r}")


def chat_json(
    s: LlmSettings,
    system: str,
    user: str,
    *,
    client: OpenAI | None = None,
    timeout: float = 120.0,
) -> dict:
    """chat.completions 1회 호출 후 첫 JSON 객체 추출. 실패 시 LlmError."""
    if client is None:
        client = OpenAI(base_url=s.base_url, api_key=s.api_key or "missing", timeout=timeout)
    resp = client.chat.completions.create(
        model=s.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content or ""
    return _extract_json(content)


def normalize_base_url_input(raw: str) -> str:
    """사용자 입력 base_url 정리: 공백 제거 + 스킴 없으면 https:// 보정."""
    u = (raw or "").strip()
    if not u:
        return u
    if "://" not in u:
        u = "https://" + u
    return u.rstrip("/")


def is_valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return bool(p.scheme in ("http", "https") and p.netloc)
    except ValueError:
        return False
