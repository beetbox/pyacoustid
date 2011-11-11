import os
import json
import urllib
import contextlib
import audioread
from . import libchroma

API_BASE_URL = 'http://api.acoustid.org/v2/'
LOOKUP_URL = API_BASE_URL + 'lookup'
DEFAULT_META = 'recordings'

class WebServiceError(Exception):
    """The Web service request failed."""

def fingerprint(samplerate, channels, pcmiter):
    """Fingerprint audio data given its sample rate and number of
    channels.  pcmiter should be an iterable containing blocks of PCM
    data as byte strings.
    """
    fper = libchroma.Fingerprinter()
    fper.start(samplerate, channels)
    for block in pcmiter:
        fper.feed(block)
    return fper.finish()

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
    with contextlib.closing(urllib.urlopen(req_url)) as f:
        data = json.load(f)
    return data

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
    with audioread.audio_open(path) as f:
        duration = f.duration
        fp = fingerprint(f.samplerate, f.channels, iter(f))
    response = lookup(apikey, fp, duration, url=url)
    return parse_lookup_result(response)
