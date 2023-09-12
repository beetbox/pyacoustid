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
import sys
from setuptools import setup


def _read(fn):
    path = os.path.join(os.path.dirname(__file__), fn)
    if sys.version_info[0] < 3:
        data = open(path).read().decode('utf8')
    else:
        data = open(path, encoding='utf8').read()
    # Special case some Unicode characters; PyPI seems to only like ASCII.
    data = data.replace(u'\xe1', u'a')
    data = data.replace(u'\u0161', u's')
    data = data.replace(u'\xfd', u'y')
    return data


setup(name='pyacoustid',
      version='1.3.0',
      description=('bindings for Chromaprint acoustic fingerprinting and the '
                   'Acoustid API'),
      author='Adrian Sampson',
      author_email='adrian@radbox.org',
      url='https://github.com/sampsyo/pyacoustid',
      license='MIT',
      platforms='ALL',
      long_description=_read('README.rst'),

      install_requires=['audioread', 'requests'],

      py_modules=[
          'chromaprint',
          'acoustid',
      ],

      classifiers=[
          'Topic :: Multimedia :: Sound/Audio :: Conversion',
          'Intended Audience :: Developers',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
      ],
      )
