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

This library uses `audioread`_ to do audio decoding (pip should automatically
install this dependency), but it's not really necessary if you already have
decoded audio.

.. _pip: http://www.pip-installer.org/
.. _PyPI: http://pypi.python.org/
.. _audioread: https://github.com/sampsyo/audioread


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
server.

.. _Web service documentation: http://acoustid.org/webservice


Version History
---------------

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
