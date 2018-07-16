#!/usr/bin/env python

# This file is part of pyacoustid.
# Copyright 2012, Lukas Lalinsky.
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

"""Simple script for calculating audio fingerprints, using the same
arguments/output as the fpcalc utility from Chromaprint."""

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import argparse
import sys

import acoustid
import chromaprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-length', metavar='SECS', type=int, default=120,
                        help='length of the audio data used for fingerprint '
                             'calculation (default 120)')
    parser.add_argument('-raw', action='store_true',
                        help='output the raw uncompressed fingerprint')
    parser.add_argument('paths', metavar='FILE', nargs='+',
                        help='audio file to be fingerprinted')

    args = parser.parse_args()
    # make gst not try to parse the args
    del sys.argv[1:]

    first = True
    for i, path in enumerate(args.paths):
        try:
            duration, fp = acoustid.fingerprint_file(path, args.length)
        except Exception:
            print("ERROR: unable to calculate fingerprint "
                  "for file %s, skipping" % path, file=sys.stderr)
            continue
        if args.raw:
            raw_fp = chromaprint.decode_fingerprint(fp)[0]
            fp = ','.join(map(str, raw_fp))
        if not first:
            print
        first = False
        print('FILE=%s' % path)
        print('DURATION=%d' % duration)
        print('FINGERPRINT=%s' % fp.decode('utf8'))


if __name__ == '__main__':
    main()
