import os
import json
import urllib
import contextlib
import audioread
from . import libchroma

API_BASE_URL = 'http://api.acoustid.org/v2/'
LOOKUP_URL = API_BASE_URL + 'lookup'
DEFAULT_META = 'recordings'

class AcoustidError(Exception):
    """Base for exceptions in this module."""

class FingerprintGenerationError(AcoustidError):
    """The audio could not be fingerprinted."""

class WebServiceError(AcoustidError):
    """The Web service request failed."""

def _api_request(url):
    """Makes a GET request for the URL and returns a parsed JSON
    response. May raise a WebServiceError if the request fails.
    """
    try:
        with contextlib.closing(urllib.urlopen(url)) as f:
            rawdata = f.read()
    except IOError:
        raise WebServiceError('ID query failed')

    try:
        return json.loads(rawdata)
    except ValueError:
        raise WebServiceError('response is not valid JSON')

def fingerprint(samplerate, channels, pcmiter):
    """Fingerprint audio data given its sample rate and number of
    channels.  pcmiter should be an iterable containing blocks of PCM
    data as byte strings. Raises a FingerprintGenerationError if
    anything goes wrong.
    """
    try:
        fper = libchroma.Fingerprinter()
        fper.start(samplerate, channels)
        for block in pcmiter:
            fper.feed(block)
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
    req_url = '%s?%s' % (url, urllib.urlencode(params))
    return _api_request(req_url)

def parse_lookup_result(data):
    """Given a parsed JSON response, return the MusicBrainz recording
    ID, the title of the recording, and the name of the recording's
    first artist. (If an artist is not available, the last item is
    None.) If the response is incomplete, raises a WebServiceError.
    """
    if data['status'] != 'ok':
        raise WebServiceError("status: %s" % data['status'])
    if not data['results']:
        raise WebServiceError("no results returned")
    result = data['results'][0]
    if not result['recordings']:
        raise WebServiceError("no MusicBrainz recording attached")
    recording = result['recordings'][0]

    # Get the artist if available.
    if recording['artists']:
        artist = recording['artists'][0]
        artist_name = artist['name']
    else:
        artist_name = None

    return recording['id'], recording['title'], artist_name

def match(apikey, path, url=LOOKUP_URL):
    """Look up the metadata for an audio file."""
    path = os.path.abspath(os.path.expanduser(path))
    try:
        with audioread.audio_open(path) as f:
            duration = f.duration
            fp = fingerprint(f.samplerate, f.channels, iter(f))
    except audioread.DecodeError:
        raise FingerprintGenerationError("audio could not be decoded")
    response = lookup(apikey, fp, duration, url=url)
    return parse_lookup_result(response)
