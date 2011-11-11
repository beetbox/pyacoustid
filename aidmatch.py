import acoustid
import sys

# API key for this demo script only. Get your own API key at the
# Acoustid Web for your application.
# http://acoustid.org/
API_KEY = 'cSpUJKpD'

def aidmatch(filename):
    try:
        rid, title, artist = acoustid.match(API_KEY, filename)
    except acoustid.FingerprintGenerationError:
        print >>sys.stderr, "fingerprint could not be calculated"
        sys.exit(1)
    except acoustid.WebServiceError:
        print >>sys.stderr, "web service request failed"
        sys.exit(1)
    print '%s - %s' % (artist, title)
    print 'http://musicbrainz.org/recording/%s' % rid

if __name__ == '__main__':
    aidmatch(sys.argv[1])
