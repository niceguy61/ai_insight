"""opencode.jsonc의 EXAONE apiKey를 리터럴로 확정 (임시)."""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 키 확보 (환경변수 우선, 없으면 .env)
key = None
try:
    import os
    key = os.environ.get("EXAONE_API_KEY")
except Exception:
    pass
if not key:
    for line in open("D:/ai_insight/.env", encoding="utf-8"):
        if line.startswith("EXAONE_API_KEY="):
            key = line.replace("EXAONE_API_KEY=", "", 1).strip()
            break
assert key, "키를 찾을 수 없음"

p = r"C:\Users\sunny\.config\opencode\opencode.jsonc"
c = open(p, encoding="utf-8").read()
before = '"apiKey": "{env:EXAONE_API_KEY}"'
after = '"apiKey": "' + key + '"'
if before in c:
    c = c.replace(before, after)
    open(p, "w", encoding="utf-8").write(c)
    print(f"치환 완료 — 키 길이 {len(key)}자 (화면 미노출)")
elif after in c:
    print("이미 리터럴 키가 설정됨")
else:
    print("패턴을 찾지 못함 — 파일 확인 필요")
    m = re.findall(r'"apiKey"[^\n]*', c)
    print(m)
