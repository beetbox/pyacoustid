Chromaprint and Acoustid for Python
===================================

`Chromaprint`_ and its associated `Acoustid`_ Web service make up a
high-quality, open-source acoustic fingerprinting system. This package provides
Python bindings for both the fingerprinting algorithm library, which is portable
and written in C, and the Web service that provides fingerprint lookups.

.. _Chromaprint: http://acoustid.org/
.. _Acoustid: http://acoustid.org/chromaprint


Installation
------------

First, install the `Chromaprint`_ fingerprinting library by `Lukáš Lalinský`__.
(The library itself depends on an FFT library, but it's smart enough to use an
algorithm from software you probably already have installed; see the Chromaprint
page for details.)

__ lukas_
.. _lukas: http://oxygene.sk/lukas/

Then you can install this library from `PyPI`_ using `pip`_::

    $ pip install pyacoustid

This library depends on `audioread`_ to do audio decoding (pip should
automatically install this dependency), but it's not really necessary if you
already have decoded audio.

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
available on your system (GStreamer, FFmpeg, MAD, or Core Audio on Mac OS X).


Using in Your Code
------------------

The simplest way to use pyacoustid to identify audio files is to call the
``match`` function::

    >>> import acoustid
    >>> recording_id, title, artist = acoustid.match(apikey, path)

This convenience function uses `audioread`_ to decode audio and parses the
response for you, pulling out the most important track metadata. Everything
happens in one fell swoop. There are also a number of "smaller" functions you
can use to perform parts of the process:

- ``fingerprint(samplerate, channels, pcmiter)``: Returns a fingerprint for raw
  audio data. Specify the audio parameters and give an iterable containing
  blocks of PCM data.
- ``lookup(apikey, fingerprint, duration)``: Make a request to the `Acoustid`_
  API to look up the fingerprint returned by the previous function. An API key
  is required, as is the length, in seconds, of the source audio. Returns a
  parsed JSON response.
- ``parse_lookup_result(data)``: Given a parsed JSON response, return a tuple
  containing the MusicBrainz recording ID, title, and artist name of the top
  match.

The module internally performs thread-safe API limiting to 3 queries per second
whenever the Web API is called, in accordance with the `Web service
documentation`_.

Calls to the library can raise ``AcoustidError`` exceptions of two subtypes:
``FingerprintGenerationError`` and ``WebServiceError``. Catch these exceptions
if you want to proceed when audio can't be decoded or no match is found on the
server.

.. _Web service documentation: http://acoustid.org/webservice


Credits
-------

This library is by `Adrian Sampson`_. Chromaprint and Acoustid are by `Lukáš
Lalinský`__. These bindings include the original `ctypes`_-based bindings
written by Lukáš. The library is made available under the MIT license.
pyacoustid was written to be used with `beets`_, which you should probably check
out.

__ lukas_
.. _ctypes: http://docs.python.org/library/ctypes.html
.. _Adrian Sampson: mailto:adrian@radbox.org
.. _beets: http://beets.radbox.org/
