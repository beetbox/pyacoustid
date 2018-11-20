Chromaprint and Acoustid for Python
===================================

`Chromaprint`_ and its associated `Acoustid`_ Web service make up a
high-quality, open-source acoustic fingerprinting system. This package provides
Python bindings for both the fingerprinting algorithm library, which is written
in C but portable, and the Web service, which provides fingerprint lookups.

.. _Chromaprint: http://acoustid.org/
.. _Acoustid: http://acoustid.org/chromaprint


Installation
------------

This library works with Python 2 (2.7+, possibly also 2.6) and Python 3
(3.3+).

First, install the `Chromaprint`_ fingerprinting library by `Lukáš Lalinský`__.
(The library itself depends on an FFT library, but it's smart enough to use an
algorithm from software you probably already have installed; see the Chromaprint
page for details.) This module can use either the Chromaprint dynamic library or
the ``fpcalc`` command-line tool, which itself depends on `libavcodec`_. If you
use ``fpcalc``, either ensure that it is on your ``$PATH`` or set the ``FPCALC``
environment variable to its location.

__ lukas_
.. _lukas: http://oxygene.sk/lukas/
.. _libavcodec: http://ffmpeg.org/

Then you can install this library from `PyPI`_ using `pip`_::

    $ pip install pyacoustid

This library uses `audioread`_ to do audio decoding when not using ``fpcalc``
and `requests`_ to talk to the HTTP API (pip should automatically install
these dependencies).

.. _pip: http://www.pip-installer.org/
.. _PyPI: http://pypi.python.org/
.. _audioread: https://github.com/sampsyo/audioread
.. _requests: http://python-requests.org


Running
-------

You can run the included demonstration script, ``aidmatch.py``, to test your
installation::

    $ python aidmatch.py mysterious_music.mp3

This will show the top metadata match from Acoustid's database. The script uses
`audioread`_ to decode music, so it should transparently use a media library
available on your system (GStreamer, FFmpeg, MAD, or Core Audio).


Using in Your Code
------------------

The simplest way to use pyacoustid to identify audio files is to call the
``match`` function::

    >>> import acoustid
    >>> for score, recording_id, title, artist in acoustid.match(apikey, path):
    >>>     ...

This convenience function uses `audioread`_ to decode audio and parses the
response for you, pulling out the most important track metadata. It returns in
iterable over tuples of relevant information. Everything happens in one fell
swoop. There are also a number of "smaller" functions you can use to perform
parts of the process:

- ``fingerprint(samplerate, channels, pcmiter)``: Generate a fingerprint for raw
  audio data. Specify the audio parameters and give an iterable containing
  blocks of PCM data.
- ``fingerprint_file(path)``: Using either the Chromaprint dynamic library or
  the ``fpcalc`` command-line tool, fingerprint an audio file. Returns a pair
  consisting of the file's duration and its fingerprint.
- ``lookup(apikey, fingerprint, duration)``: Make a request to the `Acoustid`_
  API to look up the fingerprint returned by the previous function. An API key
  is required, as is the length, in seconds, of the source audio. Returns a
  parsed JSON response.
- ``parse_lookup_result(data)``: Given a parsed JSON response, return an
  iterator over tuples containing the match score (a float between 0 and 1), the
  MusicBrainz recording ID, title, and artist name for each match.

The module internally performs thread-safe API rate limiting to 3 queries per
second whenever the Web API is called, in accordance with the `Web service
documentation`_.

If you're running your own Acoustid database server, you can set the base URL
for all API calls with the ``set_base_url`` function.

Calls to the library can raise ``AcoustidError`` exceptions of two subtypes:
``FingerprintGenerationError`` and ``WebServiceError``. Catch these exceptions
if you want to proceed when audio can't be decoded or no match is found on the
server. ``NoBackendError``, a subclass of ``FingerprintGenerationError``, is
used when the Chromaprint library or fpcalc command-line tool cannot be found.

.. _Web service documentation: http://acoustid.org/webservice


Version History
---------------

1.1.6
  In submission, avoid an error on non-integer durations.
  A new function, `get_submission_status`, abstracts the API endpoint for
  monitoring submissions using the (new) result from the `submit` function.

1.1.5
  Fix compatibility with Python 3 in the `submit` function.
  Errors in `submit` are now also handled correctly (i.e., they raise an
  informative `WebServiceError` instead of a `TypeError`).

1.1.4
  Fix an error on versions of the `fpcalc` tool that report the duration as a
  fractional number.

1.1.3
  Accept `bytearray` objects in addition to other bytes-like types.

1.1.2
  Fix a possible crash on Unicode text in Python 2 in a non-Unicode locale.
  Look for version "1" of the Chromaprint shared library file.

1.1.1
  Fix a possible setup error on Python 3 (thanks to Simon Chopin).

1.1.0
  Include ``fpcalc.py`` script in source distributions.
  Add Python 3 support (thanks to Igor Tsarev).

1.0.0
  Include ``fpcalc.py``, a script mimicking the ``fpcalc`` program from the
  Chromaprint package.
  Handle a ``UnicodeDecodeError`` raised when using the ``fpcalc`` backend on
  Windows with Unicode filenames.
  Standard error output from ``fpcalc`` is suppressed.

0.7
  Properly encode Unicode parameters (resolves a ``UnicodeEncodeError``
  in fingerprint submission).
  Parse all recordings for each Acoustid lookup result.

0.6
  Add a new function, ``fingerprint_file``, that automatically selects a
  backend for fingerprinting a single file.

0.5
  Fix response parsing when recording has no artists or title.
  Fix compatibility with Python < 2.7.
  Add specific ``NoBackendError`` exception.

0.4
  Fingerprinting can now fall back to using the ``fpcalc`` command-line tool
  instead of the Chromaprint dynamic library so the library can be used with
  the binary distributions (thanks to Lukáš Lalinský).
  Fingerprint submission (thanks to Alastair Porter).
  Data chunks can now be buffers as well as bytestrings (fixes compatibility
  with pymad).

0.3
  Configurable API base URL.
  Result parser now generates all results instead of returning just one.
  Find the chromaprint library on Cygwin.
  New module names: ``chromaprint`` and ``acoustid`` (no package).

0.2
  Compress HTTP requests and responses.
  Limit audio decoding to 120 seconds.
  Return score from convenience function.

0.1
  Initial release.


Credits
-------

This library is by Adrian Sampson. Chromaprint and Acoustid are by `Lukáš
Lalinský`__. This package includes the original `ctypes`_-based bindings
written by Lukáš. The entire library is made available under the `MIT license`_.
pyacoustid was written to be used with `beets`_, which you should probably check
out.

__ lukas_
.. _ctypes: http://docs.python.org/library/ctypes.html
.. _beets: http://beets.radbox.org/
.. _MIT license: http://www.opensource.org/licenses/mit-license.php
