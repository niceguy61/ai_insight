"""리팩터링 export 최종 검증 (임시)."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, ".")

from aic.public_export import build  # noqa: E402

tmp = Path("D:/ai_insight/logs/_export_clean")
if tmp.exists():
    shutil.rmtree(tmp)
t0 = time.perf_counter()
m = build(tmp)
print(f"빌드: {time.perf_counter() - t0:.1f}초")
files = list((tmp / "entry").rglob("*.json"))
print(f"entry 파일 수: {len(files)} (96k 정크 제외 확인)")
print(f"metrics.json: {os.path.getsize(tmp / 'metrics.json') / 1024:.0f} KB, "
      f"history.json: {os.path.getsize(tmp / 'history.json') / 1024:.0f} KB")
print(f"search 인덱스: {len(json.load(open(tmp / 'search' / 'index.json', encoding='utf-8')))}행")
