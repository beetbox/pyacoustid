import ctypes
import importlib.util
from pathlib import Path

import pytest


class DummyLib:
    def __init__(self):
        self.last_feed = None

        def get_version():
            return b"1.0"

        def new(_algorithm):
            return 123

        def free(_ctx):
            return None

        def start(_ctx, _sample_rate, _num_channels):
            return 1

        def feed(_ctx, data, _size):
            self.last_feed = bytes(data)
            return 1

        def finish(_ctx):
            return 1

        def get_fingerprint(_ctx, fingerprint_ptr):
            fingerprint_ptr._obj.value = b"fp"
            return 1

        def decode(_data, _length, result_ptr, result_size, algorithm, _base64):
            array = (ctypes.c_uint32 * 3)(1, 2, 3)
            out_ptr = ctypes.cast(
                result_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32))
            )
            out_ptr[0] = array
            result_size._obj.value = 3
            algorithm._obj.value = 7
            return 1

        def encode(_fp_array, _size, _algorithm, result_ptr, result_size, _base64):
            data = b"abc"
            buffer = (ctypes.c_char * len(data)).from_buffer_copy(data)
            out_ptr = ctypes.cast(
                result_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))
            )
            out_ptr[0] = buffer
            result_size._obj.value = len(data)
            return 1

        def hash_fingerprint(_fp_array, _size, result_hash):
            result_hash._obj.value = 42
            return 1

        def dealloc(_ptr):
            return None

        self.chromaprint_get_version = get_version
        self.chromaprint_new = new
        self.chromaprint_free = free
        self.chromaprint_start = start
        self.chromaprint_feed = feed
        self.chromaprint_finish = finish
        self.chromaprint_get_fingerprint = get_fingerprint
        self.chromaprint_decode_fingerprint = decode
        self.chromaprint_encode_fingerprint = encode
        self.chromaprint_hash_fingerprint = hash_fingerprint
        self.chromaprint_dealloc = dealloc


@pytest.fixture
def chromaprint_context(monkeypatch):
    module_path = Path(__file__).resolve().parents[1] / "chromaprint.py"
    dummy = DummyLib()
    monkeypatch.setattr("ctypes.CDLL", lambda *args, **kwargs: dummy)
    spec = importlib.util.spec_from_file_location("chromaprint_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, dummy


@pytest.fixture
def chromaprint_module(chromaprint_context):
    module, _ = chromaprint_context
    return module


@pytest.fixture
def chromaprint_dummy(chromaprint_context):
    _, dummy = chromaprint_context
    return dummy


class TestLibraryHints:
    def test_guess_lib_name_returns_candidates(self, chromaprint_module):
        candidates = chromaprint_module._guess_lib_name()
        assert isinstance(candidates, tuple)
        assert candidates
        assert all(isinstance(item, str) for item in candidates)

    def test_buffer_types_include_bytes_views(self, chromaprint_module):
        assert memoryview in chromaprint_module.BUFFER_TYPES
        assert bytearray in chromaprint_module.BUFFER_TYPES


class TestFingerprinter:
    @pytest.mark.parametrize(
        "payload",
        [
            b"abc",
            bytearray(b"abc"),
            memoryview(b"abc"),
        ],
    )
    def test_feed_accepts_bytes_like(
        self, chromaprint_module, chromaprint_dummy, payload
    ):
        fingerprinter = chromaprint_module.Fingerprinter()
        fingerprinter.feed(payload)
        assert chromaprint_dummy.last_feed == b"abc"

    @pytest.mark.parametrize("payload", [123, "text", object()])
    def test_feed_rejects_invalid_types(self, chromaprint_module, payload):
        fingerprinter = chromaprint_module.Fingerprinter()
        with pytest.raises(TypeError, match="bytes, buffer, or memoryview"):
            fingerprinter.feed(payload)

    def test_finish_returns_bytes(self, chromaprint_module):
        fingerprinter = chromaprint_module.Fingerprinter()
        assert fingerprinter.finish() == b"fp"

    @pytest.mark.parametrize("fingerprint,expected", [([1, 2, 3], 42), ([0], 42)])
    def test_hash_fingerprint(self, chromaprint_module, fingerprint, expected):
        assert chromaprint_module.hash_fingerprint(fingerprint) == expected


class TestCodecHelpers:
    def test_decode_fingerprint_returns_values(self, chromaprint_module):
        decoded, algorithm = chromaprint_module.decode_fingerprint(b"data")
        assert list(decoded) == [1, 2, 3]
        assert algorithm == 7

    def test_encode_fingerprint_returns_bytes(self, chromaprint_module):
        encoded = chromaprint_module.encode_fingerprint(
            [1, 2], chromaprint_module.Fingerprinter.ALGORITHM_TEST2
        )
        assert encoded == b"abc"
