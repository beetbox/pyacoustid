# This file is part of pyacoustid.
# Copyright 2011, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

import os
import json
import urllib
import urllib2
import httplib
import contextlib
import audioread
import threading
import time
import gzip
from StringIO import StringIO
from . import libchroma

API_BASE_URL = 'http://api.acoustid.org/v2/'
LOOKUP_URL = API_BASE_URL + 'lookup'
DEFAULT_META = 'recordings'
REQUEST_INTERVAL = 0.33 # 3 requests/second.
MAX_AUDIO_LENGTH = 120 # Seconds.

class AcoustidError(Exception):
    """Base for exceptions in this module."""

class FingerprintGenerationError(AcoustidError):
    """The audio could not be fingerprinted."""

class WebServiceError(AcoustidError):
    """The Web service request failed."""

class _rate_limit(object):
    """A decorator that limits the rate at which the function may be
    called.  The rate is controlled by the REQUEST_INTERVAL module-level
    constant; set the value to zero to disable rate limiting. The
    limiting is thread-safe; only one thread may be in the function at a
    time (acts like a monitor in this sense).
    """
    def __init__(self, fun):
        self.fun = fun
        self.last_call = 0.0
        self.lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        with self.lock:
            # Wait until request_rate time has passed since last_call,
            # then update last_call.
            since_last_call = time.time() - self.last_call
            if since_last_call < REQUEST_INTERVAL:
                time.sleep(REQUEST_INTERVAL - since_last_call)
            self.last_call = time.time()

            # Call the original function.
            return self.fun(*args, **kwargs)

def _compress(data):
    """Compress a string to a gzip archive."""
    sio = StringIO()
    with contextlib.closing(gzip.GzipFile(fileobj=sio, mode='wb')) as f:
        f.write(data)
    return sio.getvalue()

def _decompress(data):
    """Decompress a gzip archive contained in a string."""
    sio = StringIO(data)
    with contextlib.closing(gzip.GzipFile(fileobj=sio)) as f:
        return f.read()

@_rate_limit
def _send_request(req):
    """Given a urllib2 Request object, make the request and return a
    tuple containing the response data and headers.
    """
    try:
        with contextlib.closing(urllib2.urlopen(req)) as f:
            return f.read(), f.info()
    except urllib2.HTTPError:
        raise WebServiceError('HTTP request error')
    except httplib.BadStatusLine:
        raise WebServiceError('bad HTTP status line')
    except IOError:
        raise WebServiceError('connection failed')

def _api_request(url, params):
    """Makes a GET request for the URL with the given form parameters
    and returns a parsed JSON response. May raise a WebServiceError if
    the request fails.
    """
    body = _compress(urllib.urlencode(params))
    req = urllib2.Request(url, body, {
        'Content-Encoding': 'gzip',
        'Accept-Encoding': 'gzip',
    })

    data, headers = _send_request(req)
    if headers.get('Content-Encoding') == 'gzip':
        data = _decompress(data)

    try:
        return json.loads(data)
    except ValueError:
        raise WebServiceError('response is not valid JSON')

def fingerprint(samplerate, channels, pcmiter):
    """Fingerprint audio data given its sample rate and number of
    channels.  pcmiter should be an iterable containing blocks of PCM
    data as byte strings. Raises a FingerprintGenerationError if
    anything goes wrong.
    """
    # Maximum number of samples to decode.
    endposition = samplerate * MAX_AUDIO_LENGTH

    try:
        fper = libchroma.Fingerprinter()
        fper.start(samplerate, channels)

        position = 0 # Samples of audio fed to the fingerprinter.
        for block in pcmiter:
            fper.feed(block)
            position += len(block) // 2 # 2 bytes/sample.
            if position >= endposition:
                break

        return fper.finish()
    except libchroma.FingerprintError:
        raise FingerprintGenerationError("fingerprint calculation failed")

def lookup(apikey, fingerprint, duration, meta=DEFAULT_META, url=LOOKUP_URL):
    """Look up a fingerprint with the Acoustid Web service. Returns the
    Python object reflecting the response JSON data.
    """
    params = {
        'format': 'json',
        'client': apikey,
        'duration': int(duration),
        'fingerprint': fingerprint,
        'meta': meta,
    }
    return _api_request(url, params)

def parse_lookup_result(data):
    """Given a parsed JSON response, return a tuple containing the match
    score, the MusicBrainz recording ID, the title of the recording, and
    the name of the recording's first artist. (If an artist is not
    available, the last item is None.) If the response is incomplete,
    raises a WebServiceError.
    """
    if data['status'] != 'ok':
        raise WebServiceError("status: %s" % data['status'])
    if not data['results']:
        raise WebServiceError("no results returned")
    result = data['results'][0]
    score = result['score']
    if not result['recordings']:
        raise WebServiceError("no MusicBrainz recording attached")
    recording = result['recordings'][0]

    # Get the artist if available.
    if recording['artists']:
        artist = recording['artists'][0]
        artist_name = artist['name']
    else:
        artist_name = None

    return score, recording['id'], recording['title'], artist_name

def match(apikey, path, meta=DEFAULT_META, url=LOOKUP_URL, parse=True):
    """Look up the metadata for an audio file. If ``parse`` is true,
    then ``parse_lookup_result`` is used to return a small tuple of
    relevant information; otherwise, the full parsed JSON response is
    returned.
    """
    path = os.path.abspath(os.path.expanduser(path))
    try:
        with audioread.audio_open(path) as f:
            duration = f.duration
            fp = fingerprint(f.samplerate, f.channels, iter(f))
    except audioread.DecodeError:
        raise FingerprintGenerationError("audio could not be decoded")
    response = lookup(apikey, fp, duration, meta, url)
    if parse:
        return parse_lookup_result(response)
    else:
        return response
