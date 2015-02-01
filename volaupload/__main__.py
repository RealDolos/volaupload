#!/usr/bin/env python3
""" RealDolos' funky volafile upload tool"""

# pylint: disable=broad-except

import sys

from volaupload import main

def run():
    """ Run as CLI command """
    import codecs
    import warnings

    warnings.simplefilter("ignore")

    # because encoding suck m(
    if sys.stdout.encoding.casefold() != "utf-8".casefold():
        sys.stdout = codecs.getwriter(sys.stdout.encoding)(
            sys.stdout.buffer, 'replace')
    if sys.stderr.encoding.casefold() != "utf-8".casefold():
        sys.stderr = codecs.getwriter(sys.stderr.encoding)(
            sys.stderr.buffer, 'replace')

    sys.exit(main())

if __name__ == "__main__":
    run()
