# This file is part of pyacoustid.
# Copyright 2014, Adrian Sampson.
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

from __future__ import division
from __future__ import absolute_import

import os
import json
import requests
import contextlib
import errno
try:
    import audioread
    have_audioread = True
except ImportError:
    have_audioread = False
try:
    import chromaprint
    have_chromaprint = True
except ImportError:
    have_chromaprint = False
import subprocess
import threading
import time
import gzip
from io import BytesIO


API_BASE_URL = 'http://api.acoustid.org/v2/'
DEFAULT_META = 'recordings'
REQUEST_INTERVAL = 0.33  # 3 requests/second.
MAX_AUDIO_LENGTH = 120  # Seconds.
FPCALC_COMMAND = 'fpcalc'
FPCALC_ENVVAR = 'FPCALC'


# Exceptions.

class AcoustidError(Exception):
    """Base for exceptions in this module."""


class FingerprintGenerationError(AcoustidError):
    """The audio could not be fingerprinted."""


class NoBackendError(FingerprintGenerationError):
    """The audio could not be fingerprinted because neither the
    Chromaprint library nor the fpcalc command-line tool is installed.
    """


class FingerprintSubmissionError(AcoustidError):
    """Missing required data for a fingerprint submission."""


class WebServiceError(AcoustidError):
    """The Web service request failed. The field ``message`` contains a
    description of the error. If this is an error that was specifically
    sent by the acoustid server, then the ``code`` field contains the
    acoustid error code.
    """
    def __init__(self, message, response=None):
        """Create an error for the given HTTP response body, if
        provided, with the ``message`` as a fallback.
        """
        if response:
            # Try to parse the JSON error response.
            try:
                data = json.loads(response)
            except ValueError:
                pass
            else:
                if isinstance(data.get('error'), dict):
                    error = data['error']
                    if 'message' in error:
                        message = error['message']
                    if 'code' in error:
                        self.code = error['code']

        super(WebServiceError, self).__init__(message)
        self.message = message


# Endpoint configuration.

def set_base_url(url):
    """Set the URL of the API server to query."""
    if not url.endswith('/'):
        url += '/'
    global API_BASE_URL
    API_BASE_URL = url


def _get_lookup_url():
    """Get the URL of the lookup API endpoint."""
    return API_BASE_URL + 'lookup'


def _get_submit_url():
    """Get the URL of the submission API endpoint."""
    return API_BASE_URL + 'submit'


def _get_submission_status_url():
    """Get the URL of the submission status API endpoint."""
    return API_BASE_URL + 'submission_status'


def _get_track_by_mbid_url():
    """Get the URL of the track-by-MBID API endpoint."""
    return API_BASE_URL + 'track/list_by_mbid'


# Compressed HTTP request bodies.

def _compress(data):
    """Compress a bytestring to a gzip archive."""
    sio = BytesIO()
    with contextlib.closing(gzip.GzipFile(fileobj=sio, mode='wb')) as f:
        f.write(data)
    return sio.getvalue()


class CompressedHTTPAdapter(requests.adapters.HTTPAdapter):
    """An `HTTPAdapter` that compresses request bodies with gzip. The
    Content-Encoding header is set accordingly.
    """
    def add_headers(self, request, **kwargs):
        body = request.body
        if not isinstance(body, bytes):
            body = body.encode('utf8')
        request.prepare_body(_compress(body), None)
        request.headers['Content-Encoding'] = 'gzip'


# Utilities.

class _rate_limit(object):  # noqa: N801
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


@_rate_limit
def _api_request(url, params, timeout=None):
    """Makes a POST request for the URL with the given form parameters,
    which are encoded as compressed form data, and returns a parsed JSON
    response. May raise a WebServiceError if the request fails.
    If the specified timeout passes, then raises a TimeoutError.
    """
    headers = {
        'Accept-Encoding': 'gzip',
        "Content-Type": "application/x-www-form-urlencoded"
    }

    with requests.Session() as session:
        session.mount('http://', CompressedHTTPAdapter())
        try:
            response = session.post(url, data=params, headers=headers,
                                    timeout=timeout)
        except requests.exceptions.RequestException as exc:
            raise WebServiceError("HTTP request failed: {0}".format(exc))
        except requests.exceptions.ReadTimeout:
            raise WebServiceError(
                "HTTP request timed out ({0}s)".format(timeout)
            )

    try:
        return response.json()
    except ValueError:
        raise WebServiceError('response is not valid JSON')


# Main API.

def fingerprint(samplerate, channels, pcmiter, maxlength=MAX_AUDIO_LENGTH):
    """Fingerprint audio data given its sample rate and number of
    channels.  pcmiter should be an iterable containing blocks of PCM
    data as byte strings. Raises a FingerprintGenerationError if
    anything goes wrong.
    """
    # Maximum number of samples to decode.
    endposition = samplerate * channels * maxlength

    try:
        fper = chromaprint.Fingerprinter()
        fper.start(samplerate, channels)

        position = 0  # Samples of audio fed to the fingerprinter.
        for block in pcmiter:
            fper.feed(block)
            position += len(block) // 2  # 2 bytes/sample.
            if position >= endposition:
                break

        return fper.finish()
    except chromaprint.FingerprintError:
        raise FingerprintGenerationError("fingerprint calculation failed")


def lookup(apikey, fingerprint, duration, meta=DEFAULT_META, timeout=None):
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
    return _api_request(_get_lookup_url(), params, timeout)


def parse_lookup_result(data):
    """Given a parsed JSON response, generate tuples containing the match
    score, the MusicBrainz recording ID, the title of the recording, and
    the name of the recording's first artist. (If an artist is not
    available, the last item is None.) If the response is incomplete,
    raises a WebServiceError.
    """
    if data['status'] != 'ok':
        raise WebServiceError("status: %s" % data['status'])
    if 'results' not in data:
        raise WebServiceError("results not included")

    for result in data['results']:
        score = result['score']
        if 'recordings' not in result:
            # No recording attached. This result is not very useful.
            continue

        for recording in result['recordings']:
            # Get the artist if available.
            if recording.get('artists'):
                names = [artist['name'] for artist in recording['artists']]
                artist_name = '; '.join(names)
            else:
                artist_name = None

            yield score, recording['id'], recording.get('title'), artist_name


def _fingerprint_file_audioread(path, maxlength):
    """Fingerprint a file by using audioread and chromaprint."""
    try:
        with audioread.audio_open(path) as f:
            duration = f.duration
            fp = fingerprint(f.samplerate, f.channels, iter(f), maxlength)
    except audioread.DecodeError:
        raise FingerprintGenerationError("audio could not be decoded")
    return duration, fp


def _fingerprint_file_fpcalc(path, maxlength):
    """Fingerprint a file by calling the fpcalc application."""
    fpcalc = os.environ.get(FPCALC_ENVVAR, FPCALC_COMMAND)
    command = [fpcalc, "-length", str(maxlength), path]
    try:
        with open(os.devnull, 'wb') as devnull:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=devnull)
            output, _ = proc.communicate()
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise NoBackendError("fpcalc not found")
        else:
            raise FingerprintGenerationError("fpcalc invocation failed: %s" %
                                             str(exc))
    except UnicodeEncodeError:
        # Due to a bug in Python 2's subprocess on Windows, Unicode
        # filenames can fail to encode on that platform. See:
        # http://bugs.python.org/issue1759845
        raise FingerprintGenerationError("argument encoding failed")
    retcode = proc.poll()
    if retcode:
        raise FingerprintGenerationError("fpcalc exited with status %i" %
                                         retcode)

    duration = fp = None
    for line in output.splitlines():
        try:
            parts = line.split(b'=', 1)
        except ValueError:
            raise FingerprintGenerationError("malformed fpcalc output")
        if parts[0] == b'DURATION':
            try:
                duration = float(parts[1])
            except ValueError:
                raise FingerprintGenerationError("fpcalc duration not numeric")
        elif parts[0] == b'FINGERPRINT':
            fp = parts[1]

    if duration is None or fp is None:
        raise FingerprintGenerationError("missing fpcalc output")
    return duration, fp


def fingerprint_file(path, maxlength=MAX_AUDIO_LENGTH, force_fpcalc=False):
    """Fingerprint a file either using the Chromaprint dynamic library
    or the fpcalc command-line tool, whichever is available (unless
    ``force_fpcalc`` is specified). Returns the duration and the
    fingerprint.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if have_audioread and have_chromaprint and not force_fpcalc:
        return _fingerprint_file_audioread(path, maxlength)
    else:
        return _fingerprint_file_fpcalc(path, maxlength)


def match(apikey, path, meta=DEFAULT_META, parse=True, force_fpcalc=False,
          timeout=None):
    """Look up the metadata for an audio file. If ``parse`` is true,
    then ``parse_lookup_result`` is used to return an iterator over
    small tuple of relevant information; otherwise, the full parsed JSON
    response is returned. Fingerprinting uses either the Chromaprint
    library or the fpcalc command-line tool; if ``force_fpcalc`` is
    true, only the latter will be used.
    """
    duration, fp = fingerprint_file(path, force_fpcalc=force_fpcalc)
    response = lookup(apikey, fp, duration, meta, timeout)
    if parse:
        return parse_lookup_result(response)
    else:
        return response


def submit(apikey, userkey, data, timeout=None):
    """Submit a fingerprint to the acoustid server. The ``apikey`` and
    ``userkey`` parameters are API keys for the application and the
    submitting user, respectively.

    ``data`` may be either a single dictionary or a list of
    dictionaries. In either case, each dictionary must contain a
    ``fingerprint`` key and a ``duration`` key and may include the
    following: ``puid``, ``mbid``, ``track``, ``artist``, ``album``,
    ``albumartist``, ``year``, ``trackno``, ``discno``, ``fileformat``,
    ``bitrate``

    If the required keys are not present in a dictionary, a
    FingerprintSubmissionError is raised.

    Returns the parsed JSON response.
    """
    if isinstance(data, dict):
        data = [data]

    args = {
        'format': 'json',
        'client': apikey,
        'user': userkey,
    }

    # Build up "field.#" parameters corresponding to the parameters
    # given in each dictionary.
    for i, d in enumerate(data):
        if "duration" not in d or "fingerprint" not in d:
            raise FingerprintSubmissionError("missing required parameters")

        # The duration needs to be an integer.
        d["duration"] = int(d["duration"])

        for k, v in d.items():
            args["%s.%s" % (k, i)] = v

    response = _api_request(_get_submit_url(), args, timeout)
    if response.get('status') != 'ok':
        try:
            code = response['error']['code']
            message = response['error']['message']
        except KeyError:
            raise WebServiceError("response: {0}".format(response))
        raise WebServiceError("error {0}: {1}".format(code, message))
    return response


def get_submission_status(apikey, submission_id, timeout=None):
    """Get the status of a submission to the acoustid server.
    ``submission_id`` is the id of a fingerprint submission, as returned
    in the response object of a call to the ``submit`` endpoint.
    """
    params = {
        'format': 'json',
        'client': apikey,
        'id': submission_id,
    }
    return _api_request(_get_submission_status_url(), params, timeout)


def track_by_mbid(release_ids, disabled=False, timeout=None):
    """Get AcoustID track id(s) corresponding to the given MusicBrainz
    release id(s).
    If ``release_ids`` is a str, a list of strs (possibly empty) is returned.
    If ``release_ids`` is a list of strs, a dict mapping each str in that list
    to a (possibly empty) list of strs is returned.
    If ``disabled`` is True, those lists of str are instead pairs of lists of
    strs, the first containing the enabled AcoustID track ids and the second the
    disabled track ids."""

    # Avoid isinstance(release_ids, list) in case the caller wants to pass some
    # other sequence.  We let requests convert the sequence to a repeated param.
    batch = not isinstance(release_ids, str)
    params = {
        'format': 'json',
        'mbid': release_ids,
        'disabled': '1' if disabled else '0',
        'batch': '1' if batch else '0',
        # this route doesn't require an API key
    }

    response = _api_request(_get_track_by_mbid_url(), params, timeout)
    # Copied from submit, above.
    if response.get('status') != 'ok':
        try:
            code = response['error']['code']
            message = response['error']['message']
        except KeyError:
            raise WebServiceError("response: {0}".format(response))
        raise WebServiceError("error {0}: {1}".format(code, message))

    # When disabled is true, we defensively check for disabled: false even
    # though AcoustID currently omits that attribute for enabled MBIDs.
    if batch:
        mbids = response['mbids']
        if disabled:
            return {m['mbid']:
                    ([x['id'] for x in m['tracks'] if 'disabled' not in x or not x['disabled']],
                     [x['id'] for x in m['tracks'] if 'disabled' in x and x['disabled']])
                    for m in mbids}
        else:
            return {m['mbid']: [x['id'] for x in m['tracks']] for m in mbids}
    else:
        tracks = response['tracks']
        if disabled:
            return ([x['id'] for x in tracks if 'disabled' not in x or not x['disabled']],
                    [x['id'] for x in tracks if 'disabled' in x and x['disabled']])
        else:
            return [x['id'] for x in tracks]
