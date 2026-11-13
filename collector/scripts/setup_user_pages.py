"""사용자 페이지 repo(niceguy61.github.io) 생성 + ads.txt 배치 (임시 스크립트)."""
import base64
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402

OWNER = "niceguy61"
REPO = "niceguy61.github.io"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

ADSTXT = "google.com, pub-1466307496190391, DIRECT, f08c47fec0942fa0\n"
INDEX_HTML = (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0;url=/ai-parts/">'
    "<title>ai_insight</title></head>"
    '<body><a href="/ai-parts/">ai_insight — AI 부품 랭킹 포털</a></body></html>\n'
)


def put_file(client: httpx.Client, headers: dict, path: str, content: str, message: str) -> None:
    r = client.put(
        f"{API}/contents/{path}",
        headers=headers,
        json={
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        },
    )
    print(f"  {path}: HTTP {r.status_code} {'✓' if r.status_code in (201, 200) else r.text[:120]}")


def main() -> None:
    tok = (load_config().github_token or "").strip()
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}

    with httpx.Client(timeout=30) as c:
        r = c.get(API, headers=headers)
        if r.status_code == 200:
            print("repo 이미 존재 ✓")
        else:
            r = c.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json={"name": REPO, "private": False,
                      "description": "ads.txt · 사용자 페이지"},
            )
            print(f"repo 생성: HTTP {r.status_code}")

        put_file(c, headers, "ads.txt", ADSTXT, "ads.txt for adsense")
        put_file(c, headers, ".nojekyll", "", "no jekyll")
        put_file(c, headers, "index.html", INDEX_HTML, "redirect to portal")

        # Pages 활성화 (main 브랜치 루트)
        r = c.post(
            f"{API}/pages",
            headers=headers,
            json={"source": {"branch": "main", "path": "/"}},
        )
        print(f"pages 활성화: HTTP {r.status_code} (409=이미 활성화 ✓)")


if __name__ == "__main__":
    main()
