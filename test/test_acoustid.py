import sys

import audioread
import pytest

import acoustid
import chromaprint


class TestLookupParsing:
    @pytest.mark.parametrize(
        "data,expected",
        [
            (
                {
                    "status": "ok",
                    "results": [
                        {
                            "score": 0.9,
                            "recordings": [
                                {
                                    "id": "id1",
                                    "title": "Song",
                                    "artists": [
                                        {"name": "Artist", "joinphrase": " & "},
                                        {"name": "Guest"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
                [(0.9, "id1", "Song", "Artist & Guest")],
            ),
            (
                {
                    "status": "ok",
                    "results": [
                        {
                            "score": 0.5,
                            "recordings": [{"id": "id2", "title": None}],
                        }
                    ],
                },
                [(0.5, "id2", None, None)],
            ),
            (
                {
                    "status": "ok",
                    "results": [{"score": 0.1}],
                },
                [],
            ),
        ],
    )
    def test_parse_lookup_result(self, data, expected):
        assert list(acoustid.parse_lookup_result(data)) == expected

    @pytest.mark.parametrize(
        "data,expected_exception",
        [
            ({"status": "error"}, acoustid.WebServiceError),
            ({"status": "ok"}, acoustid.WebServiceError),
            ({"results": []}, KeyError),
        ],
    )
    def test_parse_lookup_result_errors(self, data, expected_exception):
        with pytest.raises(expected_exception):
            list(acoustid.parse_lookup_result(data))


class TestFingerprintComparison:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, 0),
            (1, 1),
            (3, 2),
            (255, 8),
        ],
    )
    def test_popcount(self, value, expected):
        assert acoustid._popcount(value) == expected

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            ([0, 0], [0, 0], 1.0),
            ([0], [255], 0.0),
        ],
    )
    def test_match_fingerprints(self, a, b, expected):
        assert acoustid._match_fingerprints(a, b) == expected

    @pytest.mark.parametrize(
        "a_fp,b_fp,expected",
        [
            (b"a", b"a", 1.0),
            (b"a", b"b", 0.0),
        ],
    )
    def test_compare_fingerprints(self, monkeypatch, a_fp, b_fp, expected):
        class DummyChromaprint:
            def __init__(self, mapping):
                self.mapping = mapping

            def decode_fingerprint(self, data):
                return self.mapping[data], 0

        monkeypatch.setattr(
            acoustid,
            "chromaprint",
            DummyChromaprint({b"a": [0, 0], b"b": [255, 255]}),
            raising=False,
        )
        monkeypatch.setattr(acoustid, "have_chromaprint", True)
        result = acoustid.compare_fingerprints((0, a_fp), (0, b_fp))
        assert result == expected

    def test_compare_fingerprints_requires_chromaprint(self, monkeypatch):
        monkeypatch.setattr(acoustid, "have_chromaprint", False)
        with pytest.raises(ModuleNotFoundError):
            acoustid.compare_fingerprints((0, b"a"), (0, b"a"))


class TestFpcalc:
    @pytest.fixture
    def fpcalc_script(self, tmp_path, monkeypatch):
        def factory(
            lines=("DURATION=1", "FINGERPRINT=abc"),
            exit_code=0,
            executable=True,
            missing=False,
        ):
            script = [
                f"#!{sys.executable}",
                "import sys",
                *(f'print("{line}")' for line in lines),
                f"sys.exit({exit_code})",
                "",
            ]
            path = tmp_path / "fpcalc"
            if not missing:
                path.write_text("\n".join(script))
                if executable:
                    path.chmod(0o755)

            monkeypatch.setenv(acoustid.FPCALC_ENVVAR, str(path))
            return path

        return factory

    def test_fingerprint_file_force_fpcalc(self, fpcalc_script):
        fpcalc_script()
        duration, fp = acoustid.fingerprint_file("song.mp3", force_fpcalc=True)
        assert duration == 1.0
        assert fp == b"abc"

    def test_fingerprint_file_fpcalc_parses_output(self, fpcalc_script):
        fpcalc_script()
        duration, fp = acoustid._fingerprint_file_fpcalc("song.mp3", 120)
        assert duration == 1.0
        assert fp == b"abc"

    @pytest.mark.parametrize(
        "params,error_match",
        [
            ({"lines": ()}, "missing fpcalc output"),
            (
                {"lines": ("DURATION=abc", "FINGERPRINT=abc")},
                "duration not numeric",
            ),
            ({"lines": ("BOGUS")}, "missing fpcalc output"),
            ({"exit_code": 2}, "exited with status 2"),
            ({"executable": False}, "Permission denied"),
            ({"missing": True}, "not found"),
        ],
    )
    def test_fingerprint_file_fpcalc_invalid_output(
        self, fpcalc_script, params, error_match
    ):
        fpcalc_script(**params)
        with pytest.raises(acoustid.FingerprintGenerationError, match=error_match):
            acoustid._fingerprint_file_fpcalc("song.mp3", 120)


class TestErrors:
    @pytest.mark.parametrize(
        "response,expected_message,expected_code",
        [
            ('{"error": {"message": "bad", "code": 7}}', "bad", 7),
            ('{"error": {"message": "bad"}}', "bad", None),
        ],
    )
    def test_webservice_error_parses_response(
        self, response, expected_message, expected_code
    ):
        error = acoustid.WebServiceError("fallback", response=response)
        assert error.message == expected_message
        if expected_code is None:
            assert not hasattr(error, "code")
        else:
            assert error.code == expected_code

    def test_webservice_error_invalid_json_keeps_message(self):
        error = acoustid.WebServiceError("fallback", response="not json")
        assert error.message == "fallback"


class TestFingerprinting:
    def test_fingerprint_file_audioread_success(self, monkeypatch):
        class DummyAudioFile:
            def __init__(
                self, duration=10.0, samplerate=44100, channels=2, blocks=None
            ):
                self.duration = duration
                self.samplerate = samplerate
                self.channels = channels
                self.blocks = blocks or [b"\x00\x00"]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def __iter__(self):
                return iter(self.blocks)

        monkeypatch.setattr(
            "audioread.audio_open",
            lambda _: DummyAudioFile(duration=5.0, samplerate=8000, channels=1),
        )
        duration, fp = acoustid._fingerprint_file_audioread("song.mp3", 120)

        assert duration == 5.0
        assert fp == b"AQAAAA"

    def test_fingerprint_file_audioread_error(self, monkeypatch):
        def raise_error(_):
            raise audioread.DecodeError

        monkeypatch.setattr("audioread.audio_open", raise_error)

        with pytest.raises(
            acoustid.FingerprintGenerationError,
            match="audio could not be decoded",
        ):
            acoustid._fingerprint_file_audioread("song.mp3", 120)

    def test_fingerprint_raises_on_chromaprint_failure(self, monkeypatch):
        def raise_error(*_):
            raise chromaprint.FingerprintError

        monkeypatch.setattr("chromaprint.Fingerprinter.start", raise_error)

        with pytest.raises(acoustid.FingerprintGenerationError):
            acoustid.fingerprint(44100, 2, [b"\x00\x00"])

    @pytest.mark.parametrize(
        "block_sizes",
        [
            (2, 4),
        ],
    )
    def test_fingerprint_inconsistent_block_sizes(
        self, monkeypatch, block_sizes: list[int]
    ):
        """Different block sizes may produce inconsistent results."""
        from unittest.mock import Mock

        def chunk_by_size(lst, size):
            for i in range(0, len(lst), size):
                yield lst[i : i + size]

        data = bytes(range(100))  # b'\x00\x01\x02...\x63'

        monkeypatch.setattr("chromaprint.Fingerprinter.start", Mock())
        monkeypatch.setattr("chromaprint.Fingerprinter.finish", Mock())

        values = []
        for b in block_sizes:
            mock = Mock()
            monkeypatch.setattr("chromaprint.Fingerprinter.feed", mock)

            acoustid.fingerprint(
                1,
                1,
                chunk_by_size(data, b),
                5,
                # Twice the maxlength is consumed/feed -> 5*2 = 10
            )

            flattened_bytes = b"".join(c.args[0] for c in mock.call_args_list)
            values.append(flattened_bytes)

        # Regardless of the block chunking
        # we always feed the same bytes!
        assert len(set(values)) == 1


class TestSubmissions:
    @pytest.fixture(autouse=True)
    def patch_response(self, monkeypatch, response):
        monkeypatch.setattr(acoustid, "_api_request", lambda *_, **__: response)

    @pytest.mark.parametrize(
        "data",
        [
            {"duration": 1},
            {"fingerprint": "fp"},
            [{"fingerprint": "fp"}],
        ],
    )
    @pytest.mark.parametrize("response", [{}])
    def test_submit_missing_required_fields(self, data):
        with pytest.raises(
            acoustid.FingerprintSubmissionError, match="missing required"
        ):
            acoustid.submit("key", "user", data)

    @pytest.mark.parametrize(
        "response,error_match",
        [
            (
                {"status": "error", "error": {"code": 1, "message": "bad"}},
                "error 1: bad",
            ),
            ({"status": "error"}, "response: {'status': 'error'}"),
        ],
    )
    def test_submit_error_responses(self, error_match):
        with pytest.raises(acoustid.WebServiceError, match=error_match):
            acoustid.submit("key", "user", {"duration": 1, "fingerprint": "fp"})

    @pytest.mark.parametrize("response", [{"status": "ok"}])
    def test_submit_success(self, response):
        assert (
            acoustid.submit("key", "user", {"duration": 1, "fingerprint": "fp"})
            == response
        )

    @pytest.mark.parametrize(
        "response", [{"status": "ok", "submission": {"id": "abc"}}]
    )
    def test_get_submission_status(self, response):
        assert acoustid.get_submission_status("key", "abc") == response
