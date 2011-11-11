import acoustid
import sys

# API key for this demo script only. Get your own API key at the
# Acoustid Web for your application.
# http://acoustid.org/
API_KEY = 'cSpUJKpD'

def aidmatch(filename):
    rid, title, artist = acoustid.match(API_KEY, filename)
    print '%s - %s' % (artist, title)
    print 'http://musicbrainz.org/recording/%s' % rid

if __name__ == '__main__':
    aidmatch(sys.argv[1])
