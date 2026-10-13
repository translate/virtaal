#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "devsupport", "packaging", "check_metainfo_urls.py")


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_metainfo_urls", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fetch(*statuses):
    """A fetch that returns statuses in turn, recording each call."""
    calls = []

    def fetch(url):
        calls.append(url)
        return statuses[len(calls) - 1]
    fetch.calls = calls
    return fetch


def _no_fetch(url):
    raise AssertionError("fetched %s" % url)


def test_metainfo_urls(check):
    urls = list(check.metainfo_urls(check.METAINFO))
    kinds = [kind for url, kind in urls]
    assert kinds.count("screenshot") >= 1
    assert kinds.count("url") >= 1
    assert kinds.count("newest release") == 1
    assert kinds.index("newest release") < kinds.index("release")


def test_repo_screenshot_checked_offline(check):
    url = check.REPO_RAW_PREFIX + "docs/_static/appdata/welcome.png"
    assert check.check_url(url, "screenshot", fetch=_no_fetch, sleep=_no_fetch) is None


def test_missing_repo_screenshot_fails(check):
    url = check.REPO_RAW_PREFIX + "docs/_static/appdata/no-such.png"
    level, message = check.check_url(url, "screenshot", fetch=_no_fetch, sleep=_no_fetch)
    assert level == "error"
    assert "docs/_static/appdata/no-such.png" in message


def test_ok(check):
    fetch = _fetch(200)
    assert check.check_url("https://example.org", "url", fetch=fetch, sleep=_no_fetch) is None
    assert len(fetch.calls) == 1


@pytest.mark.parametrize("status", [404, 410])
def test_gone_fails_without_retry(check, status):
    fetch = _fetch(status)
    level, message = check.check_url("https://example.org", "url", fetch=fetch, sleep=_no_fetch)
    assert level == "error"
    assert len(fetch.calls) == 1


def test_gone_newest_release_warns(check):
    level, message = check.check_url("https://example.org", "newest release",
                                     fetch=_fetch(404), sleep=_no_fetch)
    assert level == "warning"


def test_gone_older_release_fails(check):
    level, message = check.check_url("https://example.org", "release",
                                     fetch=_fetch(404), sleep=_no_fetch)
    assert level == "error"


def test_outage_retried_then_ok(check):
    sleeps = []
    fetch = _fetch(504, "timed out", 200)
    assert check.check_url("https://example.org", "url", fetch=fetch, sleep=sleeps.append) is None
    assert sleeps == list(check.RETRY_DELAYS)


@pytest.mark.parametrize("status", [504, 429, "timed out"])
def test_outage_warns(check, status):
    fetch = _fetch(*[status] * (len(check.RETRY_DELAYS) + 1))
    level, message = check.check_url("https://example.org", "url", fetch=fetch, sleep=lambda delay: None)
    assert level == "warning"
    assert len(fetch.calls) == len(check.RETRY_DELAYS) + 1


def test_main_exit_status(check, tmp_path, monkeypatch, capsys):
    metainfo = tmp_path / "test.metainfo.xml"
    metainfo.write_text(
        '<component><url type="homepage">https://example.org/gone</url>'
        '<url type="bugtracker">https://example.org/down</url></component>')
    statuses = {"https://example.org/gone": 404, "https://example.org/down": 503}
    monkeypatch.setattr(check, "fetch_status", statuses.get)
    monkeypatch.setattr(check.time, "sleep", lambda delay: None)
    monkeypatch.setattr("sys.argv", ["check_metainfo_urls.py", str(metainfo)])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert check.main() == 1
    out = capsys.readouterr().out
    assert "error: https://example.org/gone: HTTP 404" in out
    assert "warning: https://example.org/down: HTTP 503" in out
