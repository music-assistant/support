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


MEDIA_BODY = """
### What happened?
The settings screen is blank.

Screenshot: ![shot](https://github.com/user-attachments/assets/2b7c1f42-9a3e-4c1a-bb0a-1d2e3f4a5b6c)
Recording uploaded as [clip.mp4](https://github.com/user-attachments/files/55/clip.mp4)
Legacy image https://user-images.githubusercontent.com/123/abcdef.png
"""


def test_assets_url_is_allowlisted_and_media():
    asset = "https://github.com/user-attachments/assets/2b7c1f42-9a3e-4c1a-bb0a-1d2e3f4a5b6c"
    assert attachments.is_allowlisted(asset)
    assert attachments.has_media_attachment(MEDIA_BODY)
    media = attachments.find_media_urls(MEDIA_BODY)
    assert asset in media
    assert any(u.endswith("clip.mp4") for u in media)
    assert any("user-images.githubusercontent.com" in u for u in media)


def test_assets_are_not_treated_as_diagnostics_or_logs():
    # An assets URL has no filename, so it must not be mistaken for a report/log.
    assert attachments.find_diagnostics_url(MEDIA_BODY) is None
    assert attachments.find_log_urls(MEDIA_BODY) == []


def test_generic_json_upload_counts_as_diagnostics():
    body = "report [diagnostics.json](https://github.com/user-attachments/files/7/diagnostics.json)"
    url = attachments.find_diagnostics_url(body)
    assert url is not None and url.endswith("diagnostics.json")


def test_canonical_diagnostics_name_preferred_over_plain_json():
    body = (
        "a [notes.json](https://github.com/user-attachments/files/1/notes.json) "
        "b [music-assistant-diagnostics-2024-05-01-120000.json]"
        "(https://github.com/user-attachments/files/2/music-assistant-diagnostics-2024-05-01-120000.json)"
    )
    assert attachments.find_diagnostics_url(body).endswith(
        "music-assistant-diagnostics-2024-05-01-120000.json"
    )


def test_no_media_for_plain_body():
    assert attachments.has_media_attachment("just text, no attachments") is False


class _RangeResp:
    def __init__(self, content, status_code=206):
        self._content = content
        self.status_code = status_code
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        yield self._content


def test_download_log_windowed_small_file(monkeypatch):
    monkeypatch.setattr(
        attachments.requests, "get", lambda *a, **k: _FakeResp([b"line1\nline2"])
    )
    url = "https://github.com/user-attachments/files/1/server.log"
    assert attachments.download_log_windowed(url) == "line1\nline2"


def test_download_log_windowed_head_and_tail(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        # First call: streamed head (context-manager style, hits the cap).
        if "Range" not in k.get("headers", {}):
            calls["n"] += 1
            return _FakeResp([b"H" * 4096])
        # Second call: tail via Range → 206 Partial Content.
        return _RangeResp(b"TAILDATA", status_code=206)

    monkeypatch.setattr(attachments.requests, "get", fake_get)
    url = "https://github.com/user-attachments/files/1/server.log"
    out = attachments.download_log_windowed(url, head_bytes=4096, tail_bytes=8)
    assert out.startswith("H" * 10)
    assert "truncated by triage bot" in out
    assert out.endswith("TAILDATA")


def test_download_log_windowed_ignores_non_206_tail(monkeypatch):
    # If the server ignores the Range request (returns 200), we must NOT append
    # a tail (and must not buffer the whole body). Head-only is returned.
    def fake_get(*a, **k):
        if "Range" not in k.get("headers", {}):
            return _FakeResp([b"H" * 4096])
        return _RangeResp(b"X" * 10_000_000, status_code=200)

    monkeypatch.setattr(attachments.requests, "get", fake_get)
    url = "https://github.com/user-attachments/files/1/server.log"
    out = attachments.download_log_windowed(url, head_bytes=4096, tail_bytes=8)
    assert out == "H" * 4096
    assert "truncated" not in out
