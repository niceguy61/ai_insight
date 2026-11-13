import io

P = "D:/ai_insight/web/src/app/globals.css"
t = io.open(P, encoding="utf-8").read()
pairs = [
    # 1) 배경 컬러 워시 제거 -> 단색
    ("  background:\n    radial-gradient(1200px 500px at 70% -10%, rgba(108, 140, 255, 0.07), transparent 60%),\n    var(--bg);",
     "  background: var(--bg);"),
    # 2) 헤더 글래스/블러 제거
    ("  background: rgba(11, 14, 20, 0.85);\n  backdrop-filter: blur(12px);\n  position: sticky;",
     "  background: rgba(11, 14, 20, 0.92);\n  position: sticky;"),
    # 3) 버튼: 그라디언트/컬러 글로우 -> 플랫 + 호버 색 변화(이름 있는 transition)
    ("  padding: 10px 20px;\n  border: none;\n  border-radius: 10px;\n  background: linear-gradient(135deg, var(--accent), var(--accent-strong));\n  color: #fff;\n  cursor: pointer;\n  transition: box-shadow 0.15s ease, transform 0.15s ease;",
     "  padding: 12px 20px;\n  border: none;\n  border-radius: 10px;\n  background: var(--accent-strong);\n  color: #fff;\n  cursor: pointer;\n  transition: filter 0.15s ease;"),
    ("  box-shadow: 0 0 0 3px var(--accent-soft), 0 4px 16px rgba(108, 140, 255, 0.25);\n  transform: translateY(-1px);",
     "  filter: brightness(0.94);"),
    # 4) 검색 입력 포커스 링 유지(키보드 가시성)
    ("  border-radius: 10px;\n}\n.searchline input::placeholder { color: #5a6172; }\n.searchline input:focus { border-color: var(--accent); outline: none; }",
     "  border-radius: 10px;\n}\n.searchline input::placeholder { color: #5a6172; }\n.searchline input:focus { border-color: var(--accent); }"),
    # 5) 랭킹 탭: 700→600, 간격 4px 그리드
    ("  gap: 6px;\n  margin: 20px 0 0;\n  padding: 4px;",
     "  gap: 8px;\n  margin: 20px 0 0;\n  padding: 4px;"),
    ("  background: var(--accent-soft);\n  color: var(--accent);\n  font-weight: 700;\n}",
     "  background: var(--accent-soft);\n  color: var(--accent);\n  font-weight: 600;\n}"),
    # 6) 종류/카테고리 칩: 필 -> 컨트롤 반지름 8px, 간격 4px 그리드
    (".kinds { display: flex; gap: 4px; margin: 14px 0 0; font-size: 13px; flex-wrap: wrap; }",
     ".kinds { display: flex; gap: 4px; margin: 14px 0 0; font-size: 13px; flex-wrap: wrap; }"),
    ("  padding: 5px 14px;\n  border: 1px solid transparent;\n  border-radius: 999px;",
     "  padding: 4px 12px;\n  border: 1px solid transparent;\n  border-radius: 8px;"),
    (".cats { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 0; }",
     ".cats { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0; }"),
    ("  font-size: 12px;\n  padding: 4px 12px;\n  border: 1px solid var(--border);\n  border-radius: 999px;",
     "  font-size: 12px;\n  padding: 4px 12px;\n  border: 1px solid var(--border);\n  border-radius: 8px;"),
    # 7) 전표 행: 13px -> 12px, 명령 margin 6 -> 8, 모멘텀 태그 퀴트 텍스트로
    ("  gap: 16px;\n  padding: 13px 18px;", "  gap: 16px;\n  padding: 12px 18px;"),
    ("  margin-top: 6px;\n  font: 12px var(--mono);\n  color: var(--accent);", "  margin-top: 8px;\n  font: 12px var(--mono);\n  color: var(--accent);"),
    ("  color: var(--rise);\n  border: 1px solid rgba(61, 220, 151, 0.35);\n  background: rgba(61, 220, 151, 0.08);\n  border-radius: 999px;\n  padding: 1px 8px;\n  flex: none;\n  white-space: nowrap;",
     "  color: var(--rise);\n  flex: none;\n  white-space: nowrap;"),
    # 8) 상세: 간격/가중치/그라디언트/캐치올
    ("  margin: 32px 0 10px;\n  letter-spacing: -0.025em;\n  display: flex;\n  align-items: center;\n  gap: 14px;",
     "  margin: 32px 0 12px;\n  letter-spacing: -0.025em;\n  display: flex;\n  align-items: center;\n  gap: 16px;"),
    ("  transition: all 0.15s ease;\n}\n.detail .ctan a.primary {\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  font: 600 14px var(--sans);\n  padding: 10px 22px;\n  border-radius: 10px;\n  cursor: pointer;\n  transition: all 0.15s ease;",
     "  transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease, filter 0.15s ease;\n}\n.detail .ctan a.primary {\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  font: 600 14px var(--sans);\n  padding: 10px 20px;\n  border-radius: 10px;\n  cursor: pointer;"),
    ("  border: none;\n  box-shadow: 0 2px 12px rgba(108, 140, 255, 0.3);\n}\n.detail .ctan a.primary:hover { box-shadow: 0 4px 20px rgba(108, 140, 255, 0.45); transform: translateY(-1px); }",
     "  border: none;\n}\n.detail .cta a.primary:hover { filter: brightness(0.95); }"),
    ("  font-size: 13px;\n  font-weight: 700;\n  color: var(--text);\n  margin: 0 0 14px;",
     "  font-size: 13px;\n  font-weight: 600;\n  color: var(--text);\n  margin: 0 0 14px;"),
    ("  font-size: 16px;\n  font-weight: 700;\n  color: var(--accent);",
     "  font-size: 16px;\n  font-weight: 600;\n  color: var(--accent);"),
    # 9) 슬립박스 라벨: 대문자 트래킹 제거
    ("  font-size: 10px;\n  color: var(--accent);\n  min-width: 90px;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n  font-weight: 600;",
     "  font-size: 11px;\n  color: var(--accent);\n  min-width: 84px;\n  font-weight: 500;"),
    # 10) 복사/잡 버튼 transition: all -> 이름 있는 속성
    ("  color: var(--muted);\n  padding: 4px 14px;\n  cursor: pointer;\n  border-radius: 6px;\n  transition: all 0.12s ease;",
     "  color: var(--muted);\n  padding: 4px 14px;\n  cursor: pointer;\n  border-radius: 6px;\n  transition: color 0.12s ease, border-color 0.12s ease;"),
    ("  background: var(--panel);\n  color: var(--text);\n  cursor: pointer;\n  transition: all 0.15s ease;",
     "  background: var(--panel);\n  color: var(--text);\n  cursor: pointer;\n  transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;"),
    # 11) 배지 필 -> 작은 반지름
    ("  padding: 2px 10px;\n  border-radius: 999px;\n  font-size: 11px;",
     "  padding: 2px 10px;\n  border-radius: 6px;\n  font-size: 11px;"),
    # 12) 로고 800 -> 600
    ("  font-weight: 800;\n  font-size: 18px;\n  letter-spacing: -0.03em;", "  font-weight: 600;\n  font-size: 18px;\n  letter-spacing: -0.03em;"),
    # 13) 이름 700 -> 600
    ("  font-weight: 700;\n  font-size: 14.5px;", "  font-weight: 600;\n  font-size: 14.5px;"),
    # 14) 별 아이콘 자리 정리(아이콘 제거됨) + 스파크 토큰 색 + 차트 토글/박스 유틸
    (".slip .stars .icon { margin-right: 4px; }\n", ""),
    ("/* ---------- 빈 상태 / 페이저 ---------- */",
     "/* ---------- 차트 ---------- */\n.rangeline { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }\n"
     ".rangebtn {\n  font: 600 12px var(--sans);\n  font-family: var(--sans);\n  padding: 6px 12px;\n  border: 1px solid var(--border-strong);\n  border-radius: 8px;\n  background: transparent;\n  color: var(--muted);\n  cursor: pointer;\n}\n"
     ".rangebtn:hover { border-color: var(--accent); color: var(--accent); }\n"
     ".rangebtn[aria-pressed=\"true\"] { color: var(--text); border-color: var(--accent); }\n"
     ".starplot { width: 100%; height: 260px; }\n\n"
     "/* ---------- 빈 상태 / 페이저 ---------- */"),
    (".detail .prose { max-width: 72ch; font-size: 15px; line-height: 1.8; }",
     ".detail .prose { max-width: 72ch; font-size: 15px; line-height: 1.8; }\n.detail .prose + .prose { margin-top: 12px; }"),
    (".slip .spark { display: block; width: 72px; height: 26px; }",
     ".slip .spark { display: block; width: 72px; height: 26px; }\n"
     ".slip .spark polyline { stroke: var(--muted); }\n"
     ".slip .spark.up polyline { stroke: var(--rise); }"),
]

miss = 0
for old, new in pairs:
    if old not in t:
        print("CSS MISS:", ascii(old[:70]))
        miss += 1
    else:
        t = t.replace(old, new)
io.open(P, "w", encoding="utf-8").write(t)
print("globals.css applied, misses:", miss)

# --- StarChart: 다크 테마 리터럴 + 클래스 정리
S = "D:/ai_insight/web/src/components/StarChart.tsx"
s = io.open(S, encoding="utf-8").read()
spairs = [
    ("    const chart = createChart(el, {",
     "    // 색상 리터럴: lightweight-charts는 문자열 색만 받음 — 테마 토큰 미러(#6c8cff 액센트 · #939cad muted · #242b38/#2c3648 보더 계열). 토큰 변경 시 함께 갱신.\n    const chart = createChart(el, {"),
    ('layout: {\n        background: { color: "transparent" },\n        textColor: "#5c6066",',
     'layout: {\n        background: { color: "transparent" },\n        textColor: "#939cad",'),
    ('grid: {\n        vertLines: { color: "#ecebe4" },\n        horzLines: { color: "#ecebe4" },',
     'grid: {\n        vertLines: { color: "#242b3a" },\n        horzLines: { color: "#242b3a" },'),
    ('rightPriceScale: { borderColor: "#e3e0d8" },', 'rightPriceScale: { borderColor: "#2c3648" },'),
    ("timeScale: {\n        borderColor: "#e3e0d8",", "timeScale: {\n        borderColor: "#2c3648","),
    ('crosshair: {\n        vertLine: { color: "#2e4de6", width: 1, style: 3, labelBackgroundColor: "#2e4de6" },\n        horzLine: { color: "#2e4de6", width: 1, style: 3, labelBackgroundColor: "#2e4de6" },',
     'crosshair: {\n        vertLine: { color: "#6c8cff", width: 1, style: 3, labelBackgroundColor: "#6c8cff", labelTextColor: "#0b0e14" },\n        horzLine: { color: "#6c8cff", width: 1, style: 3, labelBackgroundColor: "#6c8cff", labelTextColor: "#0b0e14" },'),
    ("      lineColor: \"#2e4de6\",\n      topColor: \"rgba(46, 77, 230, 0.18)\",\n      bottomColor: \"rgba(46, 77, 230, 0.02)\",",
     "      lineColor: \"#6c8cff\",\n      topColor: \"rgba(108, 140, 255, 0.15)\",\n      bottomColor: \"rgba(108, 140, 255, 0.02)\","),
    ('<div style={{ display: "flex", gap: 6, marginBottom: 8 }}>', '<div className="rangeline">'),
    ('<div ref={containerRef} style={{ width: "100%", height: 260 }} />', '<div ref={containerRef} className="starplot" />'),
]
smiss = 0
for old, new in spairs:
    if old not in s:
        print("STAR MISS:", ascii(old[:70]))
        smiss += 1
    else:
        s = s.replace(old, new)
io.open(S, "w", encoding="utf-8").write(s)
print("StarChart applied, misses:", smiss)

# --- EntryCard: 스파크 색 토큰화
E = "D:/ai_insight/web/src/components/EntryCard.tsx"
e = io.open(E, encoding="utf-8").read()
epairs = [
    ('<svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">',
     '<svg className={`spark ${rising ? "up" : "down"}`} width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">'),
    ('        stroke={rising ? "#0e9f6e" : "#c2beb2"}\n', ''),
]
emiss = 0
for old, new in epairs:
    if old not in e:
        print("CARD MISS:", ascii(old[:70]))
        emiss += 1
    else:
        e = e.replace(old, new)
io.open(E, "w", encoding="utf-8").write(e)
print("EntryCard applied, misses:", emiss)

# --- RunButtons: 미사용 import 제거
R = "D:/ai_insight/web/src/app/admin/RunButtons.tsx"
r = io.open(R, encoding="utf-8").read()
old_imp = 'import SyncTimes from "./SyncTimes";\n'
print("RunButtons import present:", old_imp in r)
if old_imp in r:
    r = r.replace(old_imp, "")
    io.open(R, "w", encoding="utf-8").write(r)
