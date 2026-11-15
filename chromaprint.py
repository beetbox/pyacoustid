# Copyright (C) 2011 Lukas Lalinsky
# (Minor modifications by Adrian Sampson.)
# Distributed under the MIT license, see the LICENSE file for details.

"""Low-level ctypes wrapper from the chromaprint library."""

import ctypes
import ctypes.util
import os
import sys

BUFFER_TYPES = (memoryview, bytearray)


# Find the base library and declare prototypes.


def _guess_lib_name():
    if sys.platform == "darwin":
        return ("libchromaprint.1.dylib", "libchromaprint.0.dylib")
    elif sys.platform == "win32":
        return ("chromaprint.dll", "libchromaprint.dll")
    elif sys.platform == "cygwin":
        return ("libchromaprint.dll.a", "cygchromaprint-1.dll", "cygchromaprint-0.dll")
    return ("libchromaprint.so.1", "libchromaprint.so.0")


def _load_library(name):
    """Try to load a dynamic library with ctypes, or return None if the
    library is not available.
    """
    if sys.platform == "win32":
        # On Windows since Python 3.8, we need an extra call to
        # `find_library` to search standard library paths.
        name = ctypes.util.find_library(name)
        if not name:
            return None

    try:
        # Use `winmode=0` to search for libraries in extended search paths.
        # https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexa
        return ctypes.CDLL(name, winmode=0)
    except OSError:
        return None


def _configure_library(lib):
    lib.chromaprint_get_version.argtypes = ()
    lib.chromaprint_get_version.restype = ctypes.c_char_p

    lib.chromaprint_new.argtypes = (ctypes.c_int,)
    lib.chromaprint_new.restype = ctypes.c_void_p

    lib.chromaprint_free.argtypes = (ctypes.c_void_p,)
    lib.chromaprint_free.restype = None

    lib.chromaprint_start.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    lib.chromaprint_start.restype = ctypes.c_int

    lib.chromaprint_feed.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_char),
        ctypes.c_int,
    )
    lib.chromaprint_feed.restype = ctypes.c_int

    lib.chromaprint_finish.argtypes = (ctypes.c_void_p,)
    lib.chromaprint_finish.restype = ctypes.c_int

    lib.chromaprint_get_fingerprint.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_char_p),
    )
    lib.chromaprint_get_fingerprint.restype = ctypes.c_int

    lib.chromaprint_decode_fingerprint.argtypes = (
        ctypes.POINTER(ctypes.c_char),
        ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    )
    lib.chromaprint_decode_fingerprint.restype = ctypes.c_int

    lib.chromaprint_encode_fingerprint.argtypes = (
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_char)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    )
    lib.chromaprint_encode_fingerprint.restype = ctypes.c_int

    lib.chromaprint_hash_fingerprint.argtypes = (
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint32),
    )
    lib.chromaprint_hash_fingerprint.restype = ctypes.c_int

    lib.chromaprint_dealloc.argtypes = (ctypes.c_void_p,)
    lib.chromaprint_dealloc.restype = None


_libchromaprint = None
for name in _guess_lib_name():
    _libchromaprint = _load_library(name)
    if _libchromaprint:
        _configure_library(_libchromaprint)
        break


def loader(path):
    """Load Chromaprint from an explicit shared-library path.

    Unlike automatic library discovery, this uses only the supplied path.
    """
    global _libchromaprint

    path = os.fspath(path)
    if not isinstance(path, str):
        raise TypeError(
            "path must be a string or a path-like object returning a string"
        )
    if not path:
        raise ValueError("path must not be empty")

    try:
        lib = ctypes.CDLL(path)
    except OSError as exc:
        raise ImportError(f"couldn't load libchromaprint from {path}") from exc

    try:
        _configure_library(lib)
    except AttributeError as exc:
        raise ImportError(f"{path} is not a valid libchromaprint library") from exc

    _libchromaprint = lib
    return lib


def _require_library():
    if _libchromaprint is None:
        raise ImportError(
            "couldn't find libchromaprint; use loader(path) to load it explicitly"
        )
    return _libchromaprint


# Main interface.


class FingerprintError(Exception):
    """Raised when a call to the underlying library fails."""


def _check(res):
    """Check the result of a library call, raising an error if the call
    failed.
    """
    if res != 1:
        raise FingerprintError()


class Fingerprinter:
    ALGORITHM_TEST1 = 0
    ALGORITHM_TEST2 = 1
    ALGORITHM_TEST3 = 2
    ALGORITHM_DEFAULT = ALGORITHM_TEST2

    def __init__(self, algorithm=ALGORITHM_DEFAULT):
        self._ctx = _require_library().chromaprint_new(algorithm)

    def __del__(self):
        if hasattr(self, "_ctx"):
            _require_library().chromaprint_free(self._ctx)
            del self._ctx

    def start(self, sample_rate, num_channels):
        """Initialize the fingerprinter with the given audio parameters."""
        _check(
            _require_library().chromaprint_start(self._ctx, sample_rate, num_channels)
        )

    def feed(self, data):
        """Send raw PCM audio data to the fingerprinter. Data may be
        either a bytestring or a buffer object.
        """
        if isinstance(data, BUFFER_TYPES):
            data = bytes(data)
        elif not isinstance(data, bytes):
            raise TypeError("data must be bytes, buffer, or memoryview")
        _check(_require_library().chromaprint_feed(self._ctx, data, len(data) // 2))

    def finish(self):
        """Finish the fingerprint generation process and retrieve the
        resulting fignerprint as a bytestring.
        """
        lib = _require_library()
        _check(lib.chromaprint_finish(self._ctx))
        fingerprint_ptr = ctypes.c_char_p()
        _check(
            lib.chromaprint_get_fingerprint(self._ctx, ctypes.byref(fingerprint_ptr))
        )
        fingerprint = fingerprint_ptr.value
        lib.chromaprint_dealloc(fingerprint_ptr)
        return fingerprint


def decode_fingerprint(data, base64=True):
    """Uncompress and optionally decode a fingerprint.

    Args:
        data: An encoded fingerprint in bytes.
        base64: Whether to base64-decode the fingerprint.

    Returns:
        A tuple containing the decoded raw fingerprint as an array
        of unsigned 32-bit integers, and an int representing the chromaprint
        algorithm used to generate the fingerprint.
    """
    result_ptr = ctypes.POINTER(ctypes.c_uint32)()
    result_size = ctypes.c_int()
    algorithm = ctypes.c_int()
    lib = _require_library()
    _check(
        lib.chromaprint_decode_fingerprint(
            data,
            len(data),
            ctypes.byref(result_ptr),
            ctypes.byref(result_size),
            ctypes.byref(algorithm),
            1 if base64 else 0,
        )
    )
    result = result_ptr[: result_size.value]
    lib.chromaprint_dealloc(result_ptr)
    return result, algorithm.value


def encode_fingerprint(fingerprint, algorithm, base64=True):
    """Compress and optionally encode a fingerprint.

    Args:
        fingerprint: A bytestring with the fingerprint.
        algorithm: An int flag choosing the algorithm to use.
        base64: Whether to base64-encode the fingerprint.

    Returns:
        A bytestring with the encoded fingerprint.
    """
    fp_array = (ctypes.c_int * len(fingerprint))()
    for i in range(len(fingerprint)):
        fp_array[i] = fingerprint[i]
    result_ptr = ctypes.POINTER(ctypes.c_char)()
    result_size = ctypes.c_int()
    lib = _require_library()
    _check(
        lib.chromaprint_encode_fingerprint(
            fp_array,
            len(fingerprint),
            algorithm,
            ctypes.byref(result_ptr),
            ctypes.byref(result_size),
            1 if base64 else 0,
        )
    )
    result = result_ptr[: result_size.value]
    lib.chromaprint_dealloc(result_ptr)
    return result


def hash_fingerprint(fingerprint):
    """Generate a single 32-bit hash for a raw, decoded fingerprint.

    If two fingerprints are similar, their hashes generated by this
    function will also be similar. If they are significantly different,
    their hashes will most likely be significantly different as well
    (but clients should not rely on this).

    Compare two hashes with their Hamming distance, i.e., by counting
    the bits in which they differ.

    Args:
        fingerprint: A list of ints for the raw, decoded fingerprint.

    Returns:
        A 32-bit integer hash.

    Example usage:
        audio_fingerprint = <get fingerprint with Fingerprinter>
        decoded_fingerprint, algo = decode_fingerprint(audio_fingerprint)
        first_fingerprint_hash = hash_fingerprint(decoded_fingerprint)

        second_fingerprint_hash = <repeat steps for second audio file>

        # Compare the binary strings using Hamming distance.
        first_fp_binary = format(first_fingerprint_hash, 'b')
        second_fp_binary = format(second_fingerprint_hash, 'b')

        # This value will be between 0 and 32 and represent the POPCNT.
        # A value > 15 indicates the two fingerprints are very different.
        bin(int(first_fp_binary,2)^int(second_fp_binary,2)).count
    """

    fp_array = (ctypes.c_int * len(fingerprint))()
    for i in range(len(fingerprint)):
        fp_array[i] = fingerprint[i]
    result_hash = ctypes.c_uint32()
    lib = _require_library()
    _check(
        lib.chromaprint_hash_fingerprint(
            fp_array, len(fingerprint), ctypes.byref(result_hash)
        )
    )
    return result_hash.value
