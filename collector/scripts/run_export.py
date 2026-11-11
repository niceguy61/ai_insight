"""공개 데이터(JSON 샤드) 생성 → web/public/data/."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.public_export import build  # noqa: E402

OUT = Path(__file__).parents[2] / "web" / "public" / "data"


def main() -> None:
    m = build(OUT)
    print(f"entries={m['entries']}, tabs={m['tabs']}, archive days={len(m['archiveDates'])}")
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
