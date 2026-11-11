"""LLM 클라이언트 — OpenAI 호환 엔드포인트(NIM/OpenRouter/커스텀) 공용.

설정 우선순위: config 테이블('llm' 키) > .env/환경변수.
admin UI가 save_settings로 테이블을 갱신하면 수집기가 즉시 따라간다.
"""
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

import httpx
from openai import OpenAI

from aic.config import load_config

log = logging.getLogger(__name__)

PRESETS: dict[str, str] = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

_THINK_OPEN = "<" + "think" + ">"
_THINK_RE = re.compile(_THINK_OPEN + r".*?" + "</" + "think" + ">", re.DOTALL)


class LlmError(Exception):
    """LLM 호출 또는 응답 파싱 실패."""


@dataclass
class LlmSettings:
    base_url: str
    api_key: str | None
    model: str
    extra: dict | None = None  # create()에 extra_body로 전달 (예: thinking 비활성화)


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
            extra=v.get("extra"),
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
    t = _THINK_RE.sub("", text or "").strip()
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


def _is_rate_limit(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def chat_json(
    s: LlmSettings,
    system: str,
    user: str,
    *,
    client: OpenAI | None = None,
    timeout: float = 180.0,
) -> dict:
    """chat.completions 1회 호출 후 첫 JSON 객체 추출. 실패 시 LlmError.

    s.extra가 있으면 extra_body로 전달(thinking 비활성화 등). 엔드포인트가
    미지원으로 거부하면 extra_body 없이 1회 재시도한다.
    429(rate limit)는 2/5/10초 백오프로 같은 요청을 재시도한다.
    모든 실패는 LlmError로 변환 — 한 항목의 실패가 배치 전체를 죽이지 않게.

    timeout 180초 — README 20KB 프롬프트의 요약 생성이 100초+ 걸릴 수 있음(실측).
    max_retries=0 — 타임아웃 SDK 블라인드 재시작은 낭비(429는 자체 백오프에서 처리).
    """
    if client is None:
        client = OpenAI(base_url=s.base_url, api_key=s.api_key or "missing",
                        timeout=timeout, max_retries=0)
    kwargs: dict = {
        "model": s.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    if s.extra:
        kwargs["extra_body"] = s.extra

    variants: list[dict] = [kwargs]
    if "extra_body" in kwargs:  # extra_body 미지원 엔드포인트용 폴백
        variants.append({k: v for k, v in kwargs.items() if k != "extra_body"})
    delays = (2.0, 5.0, 10.0)

    resp = None
    for vi, variant in enumerate(variants):
        for attempt in range(len(delays) + 1):
            started = time.perf_counter()
            try:
                resp = client.chat.completions.create(**variant)
                log.info("LLM call ok in %.1fs (%s)", time.perf_counter() - started, s.model)
                break
            except Exception as exc:
                dt = time.perf_counter() - started
                if attempt < len(delays) and _is_rate_limit(exc):
                    log.warning("LLM 429 rate limited (%.1fs) — %.0fs 후 재시도 %d/%d",
                                dt, delays[attempt], attempt + 1, len(delays))
                    time.sleep(delays[attempt])
                    continue
                if vi + 1 < len(variants):
                    log.warning("LLM call failed after %.1fs (%s) — extra_body 없이 재시도", dt, exc)
                    break  # 다음 variant로
                log.warning("LLM call failed after %.1fs: %s", dt, exc)
                raise LlmError(f"LLM call failed: {exc}") from exc
        if resp is not None:
            break

    if resp is None:
        raise LlmError("LLM call failed: all attempts exhausted")
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
