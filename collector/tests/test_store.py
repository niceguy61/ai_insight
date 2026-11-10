from aic.models import RawItem
from aic.store import attach_appearance, insert_raw_item, upsert_entry


def _item(source="github", external_id="owner/repo", **payload):
    return RawItem(source=source, external_id=external_id, payload=payload)


def test_same_repo_from_two_sources_merges(db):
    e1 = upsert_entry(
        db, _item("github", "owner/repo"), kind="mcp",
        repo_url="https://github.com/owner/repo", canonical_name="Repo",
    )
    e2 = upsert_entry(
        db, _item("clawhub", "owner-slash-repo"), kind="skill",
        repo_url="https://www.github.com/Owner/Repo.git", canonical_name="Repo",
    )
    assert e1 == e2
    n = db.execute(
        "SELECT count(*) FROM appearances WHERE entry_id = %s", (e1,)
    ).fetchone()[0]
    assert n == 2


def test_new_repo_without_url_gets_fallback_slug(db):
    entry_id = upsert_entry(db, _item("npm", "some-mcp-pkg"), kind="mcp")
    slug = db.execute("SELECT slug FROM entries WHERE id=%s", (entry_id,)).fetchone()[0]
    assert slug == "npm/some-mcp-pkg"


def test_upsert_updates_stars_and_installs_take_max(db):
    entry_id = upsert_entry(db, _item("github", "owner/repo"), kind="mcp",
                            repo_url="https://github.com/owner/repo", stars=100)
    upsert_entry(db, _item("github", "owner/repo"), kind="mcp",
                 repo_url="https://github.com/owner/repo", stars=120)
    upsert_entry(db, _item("clawhub", "owner-slash-repo"), kind="skill",
                 repo_url="https://github.com/owner/repo", installs=50)
    upsert_entry(db, _item("clawhub", "owner-slash-repo"), kind="skill",
                 repo_url="https://github.com/owner/repo", installs=30)
    row = db.execute(
        "SELECT stars, installs FROM entries WHERE id=%s", (entry_id,)
    ).fetchone()
    assert row == (120, 50)


def test_attach_appearance_upserts_by_source_external_id(db):
    entry_id = upsert_entry(db, _item(), kind="mcp")
    attach_appearance(db, entry_id, "github", "owner/repo", url="https://github.com/owner/repo", metrics={"stars": 1})
    attach_appearance(db, entry_id, "github", "owner/repo", url=None, metrics={"stars": 2})
    rows = db.execute(
        "SELECT url, metrics FROM appearances WHERE entry_id=%s", (entry_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "https://github.com/owner/repo"  # 기존 url 유지
    assert rows[0][1]["stars"] == 2  # 새 metrics로 갱신


def test_insert_raw_item_sets_expiry(db):
    insert_raw_item(db, _item(a=1), ttl_days=30)
    row = db.execute(
        "SELECT source, external_id, payload, expires_at > now() FROM raw_items"
    ).fetchone()
    assert row[0] == "github" and row[1] == "owner/repo"
    assert row[2] == {"a": 1}
    assert row[3] is True
