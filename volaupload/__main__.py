#!/usr/bin/env python3
""" RealDolos' funky volafile upload tool"""

# pylint: disable=broad-except

import sys

from volaupload import main

def run():
    """ Run as CLI command """

    try:
        import win_unicode_console
        win_unicode_console.enable(use_unicode_argv=True)
    except ImportError:
        pass

    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

    import warnings
    warnings.simplefilter("ignore")

    sys.exit(main())

if __name__ == "__main__":
    run()
