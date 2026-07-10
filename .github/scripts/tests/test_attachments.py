from ma_triage import attachments


BODY = """
### The problem
It broke.

Here is my file [music-assistant-diagnostics-2024-05-01-120000.json](https://github.com/user-attachments/files/12345/music-assistant-diagnostics-2024-05-01-120000.json)
and a log [server.log](https://github.com/user-attachments/files/999/server.log)
and evil (https://evil.example.com/user-attachments/files/1/x.json)
legacy (https://github.com/music-assistant/support/files/42/music-assistant-diagnostics-2024-05-01-120000.json)
"""


def test_extract_only_allowlisted():
    urls = attachments.extract_attachment_urls(BODY)
    assert any("user-attachments/files/12345" in u for u in urls)
    assert any("/support/files/42/" in u for u in urls)
    assert all("evil.example.com" not in u for u in urls)


def test_find_diagnostics_url():
    url = attachments.find_diagnostics_url(BODY)
    assert url.endswith("music-assistant-diagnostics-2024-05-01-120000.json")


def test_find_log_urls():
    logs = attachments.find_log_urls(BODY)
    assert any(u.endswith("server.log") for u in logs)


def test_is_allowlisted():
    assert attachments.is_allowlisted(
        "https://github.com/user-attachments/files/1/a.json"
    )
    assert not attachments.is_allowlisted("https://example.com/x")
    assert not attachments.is_allowlisted(
        "https://github.com/user-attachments/files/1/a.json?redirect=evil"
    )


def test_download_refuses_non_allowlisted():
    assert attachments.download_capped("https://evil.example.com/x") is None


class _FakeResp:
    def __init__(self, chunks, headers=None):
        self._chunks = chunks
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        yield from self._chunks


def test_download_cap_enforced(monkeypatch):
    big = [b"x" * 1024] * 10  # 10 KB
    monkeypatch.setattr(
        attachments.requests, "get", lambda *a, **k: _FakeResp(big)
    )
    url = "https://github.com/user-attachments/files/1/a.json"
    assert attachments.download_capped(url, max_bytes=4096) is None


def test_download_rejects_declared_oversize(monkeypatch):
    monkeypatch.setattr(
        attachments.requests,
        "get",
        lambda *a, **k: _FakeResp([b"x"], headers={"Content-Length": "99999999"}),
    )
    url = "https://github.com/user-attachments/files/1/a.json"
    assert attachments.download_capped(url, max_bytes=4096) is None


def test_download_ok(monkeypatch):
    monkeypatch.setattr(
        attachments.requests, "get", lambda *a, **k: _FakeResp([b"hello"])
    )
    url = "https://github.com/user-attachments/files/1/a.json"
    assert attachments.download_capped(url) == b"hello"
