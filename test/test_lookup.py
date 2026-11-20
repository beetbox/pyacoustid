import gzip
from urllib.parse import parse_qs

import pytest
import requests

import acoustid


@pytest.fixture
def lookup_requests(monkeypatch):
    requests_seen = []

    def send(adapter, request, **kwargs):
        adapter.add_headers(request)
        assert request.headers["Content-Encoding"] == "gzip"
        form = parse_qs(gzip.decompress(request.body).decode())
        requests_seen.append((request.method, request.url, form, kwargs["timeout"]))
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status":"ok","results":[]}'
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(acoustid, "REQUEST_INTERVAL", 0)
    return requests_seen


def test_lookup_sends_both_keys_over_https(lookup_requests):
    result = acoustid.lookup(
        "test-client",
        "FINGERPRINT",
        30.8,
        ["recordings", "releases"],
        10,
        userkey="test-user+&",
    )

    assert result == {"status": "ok", "results": []}
    assert lookup_requests == [
        (
            "POST",
            "https://api.acoustid.org/v2/lookup",
            {
                "format": ["json"],
                "client": ["test-client"],
                "user": ["test-user+&"],
                "duration": ["30"],
                "fingerprint": ["FINGERPRINT"],
                "meta": ["recordings releases"],
            },
            10,
        )
    ]


def test_lookup_without_user_key_keeps_custom_http_endpoint(
    monkeypatch, lookup_requests
):
    monkeypatch.setattr(acoustid, "API_BASE_URL", "http://acoustid.test/v2/")

    acoustid.lookup("test-client", "FINGERPRINT", 30, "recordings", 10)

    _, url, form, timeout = lookup_requests[0]
    assert url == "http://acoustid.test/v2/lookup"
    assert form["client"] == ["test-client"]
    assert "user" not in form
    assert timeout == 10


def test_submit_keeps_compressed_payload_over_https(lookup_requests):
    acoustid.submit(
        "test-client",
        "test-user",
        {"duration": 30, "fingerprint": "FINGERPRINT"},
        timeout=10,
    )

    assert lookup_requests == [
        (
            "POST",
            "https://api.acoustid.org/v2/submit",
            {
                "format": ["json"],
                "client": ["test-client"],
                "user": ["test-user"],
                "duration.0": ["30"],
                "fingerprint.0": ["FINGERPRINT"],
            },
            10,
        )
    ]


@pytest.mark.parametrize("userkey", [None, "test-user"])
def test_match_forwards_user_key(monkeypatch, lookup_requests, userkey):
    def fingerprint_file(path, force_fpcalc):
        assert path == "song.mp3"
        assert force_fpcalc is True
        return 30, b"FINGERPRINT"

    monkeypatch.setattr(acoustid, "fingerprint_file", fingerprint_file)

    # Keep exercising the existing positional arguments, including timeout.
    args = ("test-client", "song.mp3", "recordings", False, True, 10)
    result = (
        acoustid.match(*args, userkey=userkey) if userkey else acoustid.match(*args)
    )

    assert result == {"status": "ok", "results": []}
    _, _, form, timeout = lookup_requests[0]
    assert form.get("user") == ([userkey] if userkey else None)
    assert form["fingerprint"] == ["FINGERPRINT"]
    assert timeout == 10
