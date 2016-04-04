""" RealDolos' funky volafile upload tool"""

# pylint: disable=broad-except

import math
import re
import sys

# pylint: disable=no-name-in-module
try:
    from os import posix_fadvise, POSIX_FADV_WILLNEED
except ImportError:
    def posix_fadvise(*args, **kw):
        """Mock implementation for systems not supporting it"""
        args, kw = args, kw

    POSIX_FADV_WILLNEED = 0
# pylint: enable=no-name-in-module


def natsort(val):
    """Returns a tuple from a string that can be used as a sort key for
    natural sorting."""
    return [int(i) if i.isdigit() else i for i in re.split(r"(\d+)", val)]


def to_name(file):
    """Sortkey by-name"""
    return natsort(file.name.casefold()), natsort(file.parent)

def to_path(file):
    """Sortkey by-path"""
    return natsort(file.casefold())


def to_size(file):
    """Sortkey by-size"""
    return file.size


SORTING = dict(name=to_name,
               path=to_path,
               size=to_size)


def try_unlink(file):
    """Attempt to unlink a file, or else print an error"""
    try:
        file.unlink()
    except Exception as ex:
        print("Failed to delete file after upload: {}, {}".
              format(file, ex),
              file=sys.stderr, flush=True)


def try_advise(file, offset, length):
    """Try to advise the OS on what file data is needed next"""
    try:
        if hasattr(file, "fileno"):
            posix_fadvise(file.fileno(),
                          offset,
                          length,
                          POSIX_FADV_WILLNEED)
    except Exception as ex:
        print(ex, file=sys.stderr, flush=True)


def shorten(string, length):
    """Shorten a string to a specific length, cropping in the middle"""
    len2 = length // 2
    len3 = length - len2 - 1
    lens = len(string) + 2
    if lens > length:
        return ("[\033[32m{}…{}\033[0m]".
                format(string[:len2], string[lens - len3:]))
    return ("[\033[32m{}\033[0m]{}".
            format(string, " " * (length - lens)))


def progressbar(cur, tot, length):
    """Generate a progress bar"""
    per = math.floor(cur * float(length) / tot)
    return "[{}{}]".format("#" * per, " " * (length - per))


def format_time(secs):
    """Format times for Kokytos"""
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d:
        # Yes, vola is this shit :*(
        return "{}::{:02}:{:02}:{:02}".format(d, h, m, s)
    if h:
        return "{}:{:02}:{:02}".format(h, m, s)
    if m:
        return "{:02}:{:02}".format(m, s)
    return "{}s".format(s)
