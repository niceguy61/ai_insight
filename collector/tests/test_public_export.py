"""export 테스트 — 탭 상위 컷에서 잘린 종류의 슬라이스 파일.

설치수 탭처럼 한 종류(스킬)가 LIMIT을 잠식하면 다른 종류(플러그인)가
목록에서 안 보인다. 이때 rank/{tab}-{kind}.json 보완 파일이 쓰이고
manifest.kinds에 기록되는지 검증한다.
"""
import json
from types import SimpleNamespace

import aic.public_export as pe
from aic.models import RawItem
from aic.store import upsert_entry


class _NoClose:
    """build()가 공유 테스트 연결을 닫지 않게 감싼다 — fixture는 rollback으로 끝난다."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass


def _seed(db):
    # 스킬 3개 — 설치수 상위를 잠식하는 쪽
    upsert_entry(db, RawItem("skills_sh", "sk/one", {}), kind="skill", installs=10000)
    upsert_entry(db, RawItem("skills_sh", "sk/two", {}), kind="skill", installs=9000)
    upsert_entry(db, RawItem("skills_sh", "sk/three", {}), kind="skill", installs=8000)
    # 플러그인 2개 — 설치수는 있지만 컷에 걸리는 쪽 (ClawHub 1000+ → active)
    upsert_entry(db, RawItem("clawhub", "pl/one", {"plugin": True}),
                 kind="plugin", installs=2000)
    upsert_entry(db, RawItem("clawhub", "pl/two", {"plugin": True}),
                 kind="plugin", installs=1500)


def _build(db, tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "load_config", lambda: SimpleNamespace(database_url="test"))
    monkeypatch.setattr(pe, "connect", lambda url: _NoClose(db))
    return pe.build(tmp_path)


def test_kind_slice_written_when_kind_cut_by_limit(db, tmp_path, monkeypatch):
    _seed(db)
    monkeypatch.setitem(pe.LIMITS, "installs", 2)  # 스킬 2개로 상위를 채운 상황

    m = _build(db, tmp_path, monkeypatch)

    top = json.loads((tmp_path / "rank" / "installs.json").read_text(encoding="utf-8"))
    assert [r["k"] for r in top] == ["skill", "skill"]  # 상위 2행은 전부 스킬

    slice_path = tmp_path / "rank" / "installs-plugin.json"
    assert slice_path.exists()
    sl = json.loads(slice_path.read_text(encoding="utf-8"))
    assert [r["k"] for r in sl] == ["plugin", "plugin"]
    assert [r["in"] for r in sl] == [2000, 1500]  # 종류 안에서는 설치수 순
    assert m["kinds"]["installs-plugin"] == 2

    # 스킬도 컷에서 일부 잘렸으니 스킬 슬라이스도 쓰인다 — 슬라이스도 탭 LIMIT 적용
    assert m["kinds"]["installs-skill"] == 2


def test_no_kind_slice_when_tab_list_holds_everything(db, tmp_path, monkeypatch):
    _seed(db)  # LIMIT 기본값(2000) — 5개 항목 전부 들어감

    m = _build(db, tmp_path, monkeypatch)

    top = json.loads((tmp_path / "rank" / "installs.json").read_text(encoding="utf-8"))
    kinds_in_top = {r["k"] for r in top}
    assert kinds_in_top == {"skill", "plugin"}
    assert not (tmp_path / "rank" / "installs-plugin.json").exists()
    assert not (tmp_path / "rank" / "installs-skill.json").exists()
    assert m["kinds"] == {} or not any(k.startswith("installs") for k in m["kinds"])
