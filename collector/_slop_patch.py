import io

EMOJI = "\u2b50\u1f525\u1f4e5\u1f680\u2705\u274c"  # sta r s
DASH = "\u25b6"  # pl a y
B = "D:/ai_insight/web/src"

def patch(path, pairs):
    p = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old not in p:
            print("MISS:", path, ascii(old[:60]))
            continue
        p = p.replace(old, new)
    io.open(path, "w", encoding="utf-8").write(p)
    left = [i + 1 for i, ln in enumerate(p.split("\n")) if any(ch in ln for ch in EMOJI + DASH)]
    print("patched:", path, "| leftover lines:", left if left else "none")

patch(f"{B}/components/EntryCard.tsx", [
    ("\u2b50</span>", "</span>"),
    ("\U0001F525 {entry.mo}일 연속", "{entry.mo}일 연속"),
])
patch(f"{B}/app/entry/EntryDetailInner.tsx", [
    ('<span className="chip gold">\u2b50 {st.toLocaleString()}</span>',
     '<span className="chip gold">{st.toLocaleString()}</span>'),
    ("<span className=\"chip\">\U0001F4E5 {installs.toLocaleString()}</span>",
     "<span className=\"chip\">{installs.toLocaleString()}</span>"),
])
patch(f"{B}/app/admin/RunButtons.tsx", [
    ("\U0001F680 JSON 생성 & Pages push", "JSON 생성 & Pages push"),
    ("\u2705 ", ""), ("\u274c ", ""), ("\u25b6 ", ""),
])
patch(f"{B}/app/admin/settings/LlmSettingsForm.tsx", [
    ("\u2705 ", ""), ("\u274c ", ""),
])
