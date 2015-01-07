#!/usr/bin/env python3
""" RealDolos' funky volafile upload tool"""
# pip install path.py volapi ;)
# pylint: disable=broad-except

import sys

from volaupload import main


def socketeering():
    """Use larger socket...like... huge"""
    import socket

    class LargeSocket(socket.socket):
        """A socket with moar buffer"""
        # pylint: disable=too-few-public-methods

        options = (
            (socket.SO_RCVBUF, 1 << 17),
            (socket.SO_SNDBUF, 1 << 24))

        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            if self.family == socket.AF_INET:
                try:
                    for opt, val in self.options:
                        cur = self.getsockopt(socket.SOL_SOCKET, opt)
                        if val > cur:
                            self.setsockopt(socket.SOL_SOCKET, opt, val)
                except Exception as ex:
                    print("Failed to set sockopt", ex,
                          file=sys.stderr, flush=True)

    socket.socket = LargeSocket


if __name__ == "__main__":
    import codecs

    # because encoding suck m(
    if sys.stdout.encoding.casefold() != "utf-8".casefold():
        sys.stdout = codecs.getwriter(sys.stdout.encoding)(
            sys.stdout.buffer, 'replace')
    if sys.stderr.encoding.casefold() != "utf-8".casefold():
        sys.stderr = codecs.getwriter(sys.stderr.encoding)(
            sys.stderr.buffer, 'replace')

    socketeering()

    sys.exit(main())
