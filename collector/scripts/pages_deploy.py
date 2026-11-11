"""GitHub Pages 배포 repo 초기화 + 데이터 push.

사용법:
  1. 최초 1회:  python scripts/pages_deploy.py init <로컬경로> <github-owner/repo>
     - repo가 없으면 토큰으로 생성(GitHub API), scaffold+site 소스+data 구성, 첫 push
  2. 데이터 갱신: python scripts/pages_deploy.py push <로컬경로>
     - JSON 재생성 → repo/data 갱신 → commit+push (workflow가 빌드·배포)

필요: .env의 GITHUB_TOKEN (public_repo 스코프 — push·repo 생성 가능)
"""
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402
from aic.public_export import build  # noqa: E402

ROOT = Path(__file__).parents[2]
SCAFFOLD = Path(__file__).parents[2] / "pages-repo-scaffold"
SITE_SRC = ROOT / "web"


def _token() -> str:
    cfg = load_config()
    return (cfg.github_token or "").strip()


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def _ensure_remote_repo(owner_repo: str) -> None:
    tok = _token()
    r = httpx.get(
        f"https://api.github.com/repos/{owner_repo}",
        headers={"Authorization": f"Bearer {tok}"},
    )
    if r.status_code == 200:
        print(f"[repo] 이미 존재: {owner_repo}")
        return
    r = httpx.post(
        "https://api.github.com/user/repos",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": owner_repo.split("/")[1], "private": False,
              "description": "AI 부품 카탈로그 — MCP·스킬·플러그인 랭킹 (자동 갱신)"},
    )
    if r.status_code not in (201, 422):
        raise RuntimeError(f"repo 생성 실패: {r.status_code} {r.text[:200]}")
    print(f"[repo] 생성: {owner_repo}")


def _sync_site(repo: Path) -> None:
    """프론트 소스를 pages repo로 동기화.

    보안: app/admin·app/api는 로컬 전용 — 공개 repo에 절대 포함하지 않는다.
    """
    site = repo / "site"
    site.mkdir(exist_ok=True)
    for item in ["src", "public"]:
        src = SITE_SRC / item
        dst = site / item
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src, dst,
            ignore=shutil.ignore_patterns("data", "__pycache__", "admin", "api"),
        )
    for f in ["package.json", "package-lock.json", "tsconfig.json", "next.config.mjs",
              "postcss.config.mjs", "next-env.d.ts"]:
        src = SITE_SRC / f
        if src.exists():
            shutil.copy2(src, site / f)


def init(repo_path: Path, owner_repo: str) -> None:
    _ensure_remote_repo(owner_repo)
    repo_path.mkdir(parents=True, exist_ok=True)

    wf_src = SCAFFOLD / ".github" / "workflows" / "deploy.yml"
    wf_dst = repo_path / ".github" / "workflows" / "deploy.yml"
    wf_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wf_src, wf_dst)

    _sync_site(repo_path)

    data_dir = repo_path / "data"
    data_dir.mkdir(exist_ok=True)
    build(data_dir)

    if not (repo_path / ".git").exists():
        _git(repo_path, "init", "-b", "main")
    _git(repo_path, "add", "-A")
    _git(repo_path, "-c", "user.name=ai-insight-bot", "-c", "user.email=bot@local",
         "commit", "-m", "init: site + data", "--allow-empty")
    remote = f"https://x-access-token:{_token()}@github.com/{owner_repo}.git"
    try:
        _git(repo_path, "remote", "add", "origin", remote)
    except RuntimeError:
        _git(repo_path, "remote", "set-url", "origin", remote)
    try:
        _git(repo_path, "push", "-u", "origin", "main")
    except RuntimeError:
        _git(repo_path, "push", "-u", "origin", "main", "--force")
    owner, name = owner_repo.split("/")
    print(f"[init] 완료 — https://{owner}.github.io/{name}/ (Pages 활성화: Settings→Pages→GitHub Actions)")


def push_data(repo_path: Path) -> None:
    data_dir = repo_path / "data"
    data_dir.mkdir(exist_ok=True)
    build(data_dir)
    if not (repo_path / ".git").exists():
        raise RuntimeError("pages repo가 없습니다 — init_pages_repo.py를 먼저 실행하세요")
    _git(repo_path, "add", "data")
    diff = _git(repo_path, "status", "--porcelain", "data")
    if not diff:
        print("[push] 변경 없음 — 스킵")
        return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    _git(repo_path, "-c", "user.name=ai-insight-bot", "-c", "user.email=bot@local",
         "commit", "-m", f"data: {stamp}")
    _git(repo_path, "push")
    print("[push] 완료 — Actions 빌드·배포 진행 (1-2분)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "push"
    if mode == "init":
        if len(sys.argv) < 4:
            print("사용법: python scripts/pages_deploy.py init <로컬경로> <owner/repo>")
            sys.exit(1)
        init(Path(sys.argv[2]), sys.argv[3])
    else:
        repo = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parents[2] / "pages")
        push_data(Path(repo))
