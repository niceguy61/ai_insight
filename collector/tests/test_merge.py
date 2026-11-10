import pytest

from aic.merge import entry_slug, normalize_repo_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.github.com/Owner/Repo/", "https://github.com/owner/repo"),
        ("git@github.com:owner/repo.git", "https://github.com/owner/repo"),
        ("http://github.com/owner/repo?tab=readme", "https://github.com/owner/repo"),
        ("github.com/owner/repo#readme", "https://github.com/owner/repo"),
        ("https://github.com/owner/repo/tree/main/src", "https://github.com/owner/repo"),
        ("HTTPS://GITHUB.COM/OWNER/REPO", "https://github.com/owner/repo"),
        ("https://gitlab.com/a/b", None),  # github 아님
        (None, None),
        ("", None),
        ("   ", None),
        ("https://github.com/only-owner", None),  # repo 없음
    ],
)
def test_normalize_repo_url(raw, expected):
    assert normalize_repo_url(raw) == expected


def test_entry_slug_lowercases():
    assert entry_slug("Owner", "My-Repo") == "owner/my-repo"
