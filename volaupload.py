#!/usr/bin/env python3
""" RealDolos' funky volafile upload tool"""
# pip install path.py volapi ;)

import argparse
import os
import re
import sys
import random

from configparser import ConfigParser
from datetime import datetime
from functools import partial
from time import sleep

# pylint: disable=no-name-in-module
from path import path
# pylint: enable=no-name-in-module

from volapi import Room

# pylint: disable=no-name-in-module
try:
    from os import posix_fadvise, POSIX_FADV_WILLNEED
except ImportError:
    def posix_fadvice(*args, **kw):
        """Mock implementation for systems not supporting it"""
        args, kw = args, kw

    POSIX_FADV_WILLNEED = 0
# pylint: enable=no-name-in-module

__version__ = "0.3"
FAC = 1024.0 * 1024.0
BUFFER_SIZE = 1 << 26
BLOCK_SIZE = 1 << 20


def natsort(val):
    """Returns a tuple from a string that can be used as a sort key for
    natural sorting."""
    return [int(i) if i.isdigit() else i for i in re.split(r"(\d+)", val)]


def to_name(file):
    """Sortkey by-name"""
    return natsort(file.name.lower()), natsort(file.parent)


def to_size(file):
    """Sortkey by-size"""
    return file.size


SORTING = dict(name=to_name, size=to_size)


def try_advise(file, offset, length):
    """Try to advise the OS on what file data is needed next"""
    try:
        posix_fadvise(file.fileno(),
                      offset,
                      length,
                      POSIX_FADV_WILLNEED)
    except Exception as ex:
        print(ex, file=sys.stderr)


class Stat:
    """Keep some statistics"""

    def __init__(self):
        self.start = datetime.now()
        self.lasts = [(self.start, 0)]

    def record(self, pos):
        """Record a position in time"""
        self.lasts += (datetime.now(), pos),
        if len(self.lasts) > 10:
            self.lasts.pop(0)

    @property
    def time(self):
        """Last time recorded"""
        return self.lasts[-1][0]

    @property
    def pos(self):
        """Last position recorded"""
        return self.lasts[-1][1]

    @property
    def runtime(self):
        """Total runtime so far"""
        return (self.time - self.start).total_seconds()

    @property
    def brate(self):
        """Total avg. byterate so far"""
        try:
            return self.pos / self.runtime
        except ZeroDivisionError:
            return 0

    @property
    def rate(self):
        """Total avg. megabyterate so far"""
        return self.brate / FAC

    def eta(self, total):
        """Estimated time of arrival"""
        try:
            return (total - self.pos) / self.brate
        except ZeroDivisionError:
            return 0.0

    @property
    def rate_last(self):
        """Avg. megabyterate over the last samples"""
        diff = (self.time - self.lasts[0][0]).total_seconds()
        try:
            return (self.pos - self.lasts[0][1]) / FAC / diff
        except ZeroDivisionError:
            return 0.0


def progress_callback(cur, tot, file, nums, stat):
    """ Print progress (and fadvise)"""
    stat.record(cur)

    ccur, ctot, per = cur / FAC, tot / FAC, float(cur) / tot
    args = tuple(nums) + (file.name, ccur, ctot, per, stat.rate,
                          stat.rate_last, stat.runtime, stat.eta(tot))
    fmt = ("{}/{} - {} - {:.1f}/{:.1f} - "
           "{:.1%} - {:.2f}MB/s ({:.2f}MB/s), "
           "{:.2f}s (eta:{:.2f}s)")
    if sys.stdout.isatty():
        clear = "  " if os.name == "nt" else "\033[K"
        print("\r{}{}".format(fmt, clear).format(*args),
              end="", flush=True)
    else:
        print(fmt.format(*args), flush=True)

    if cur + BUFFER_SIZE < tot:
        try_advise(file, cur + BUFFER_SIZE, BUFFER_SIZE * 2)


def upload(room, file, nums, block_size=BLOCK_SIZE):
    """Uploads a file and prints the progress while pushing bits and bytes"""
    stat = Stat()
    with open(file, "rb", buffering=block_size) as advp:
        callback = partial(progress_callback,
                           file=advp, nums=nums, stat=stat)
        callback(0, file.size)
        room.upload_file(advp,
                         upload_as=file.name,
                         blocksize=block_size,
                         callback=callback)

    print("\n{} done in {:.2f}secs\n".
          format(file, (datetime.now() - stat.start).total_seconds()))


def parse_args():
    """Parse command line arguments into something sane!"""
    sorts = tuple(SORTING.keys()) + ("none", "rnd")

    config = ConfigParser()
    try:
        config.read(path("~/.vola.conf").expand())
        config = config["vola"]
    except Exception:
        config = dict()

    parser = argparse.ArgumentParser(
        description="Uploads one or more file to vola",
        epilog=("To set a default user name and optionally password, create "
                "~/.vola.conf with a [vola] section and set user= and passwd= "
                " block_size accordingly")
        )
    parser.add_argument('--room', '-r', dest='room', type=str, required=True,
                        help='room to upload to')
    parser.add_argument('--user', '-u', dest='user', type=str,
                        default=config.get("user", None),
                        help='user name to use')
    parser.add_argument('--passwd', '-p', dest='passwd', type=str,
                        default=config.get("passwd", None),
                        help='password if you wanna greenfag')
    parser.add_argument('--sort', '-s', dest='sort', type=str, default="name",
                        help=('upload files in some order ({})'.
                              format(','.join(sorts))))
    parser.add_argument("--delete-after", dest="delete", action="store_true",
                        help="Delete files after successful upload")
    parser.add_argument("--bs", "-b", dest="block_size", type=int,
                        default=int(config.get("block_size", BLOCK_SIZE)),
                        help="Use this block size")
    parser.add_argument("--attempts", "-t", dest="attempts", type=int,
                        default=int(config.get("attempts", 25)),
                        help="Retry failed uploads this many times")
    parser.set_defaults(delete=False)
    parser.add_argument('files', metavar='FILE', type=str, nargs='+',
                        help='files to upload')
    args = parser.parse_args()

    if not args.user or not re.match(r"[\w\d]{3,12}$", args.user):
        parser.error("No valid user name provided")

    if args.passwd and args.passwd == "":
        parser.error("No valid user password provided")

    if not args.room:
        parser.error("No valid room provided")

    args.files = [path(a) for a in args.files if path(a).isfile()]
    if not len(args.files):
        parser.error("No valid files selected")

    return args


def main():
    """Program, kok"""
    args = parse_args()

    stat = Stat()
    total = 0
    try:
        print("Starting DoS... ", end="", flush=True)
        with Room(args.room, args.user) as room:
            print("done")
            if args.passwd:
                print("Greenfagging in as {}... ".format(args.user),
                      end="", flush=True)
                room.user.login(args.passwd)
                print("done")

            files = args.files
            if args.sort == "none":
                pass
            elif args.sort == "rnd":
                random.shuffle(files)
            elif args.sort:
                files = sorted(files, key=SORTING[args.sort])

            print("Pushing attack bytes to mainframe...")
            for i, file in enumerate(files):
                for attempt in range(args.attempts):
                    try:
                        upload(room, file, nums=(i + 1, len(files)),
                               block_size=args.block_size)
                        total += file.size
                        stat.record(total)
                        if args.delete:
                            try:
                                file.unlink()
                            except Exception as ex:
                                print("Failed to delete file after upload: "
                                      "{}, {}".
                                      format(file, ex), file=sys.stderr)

                        break
                    except Exception as ex:
                        print("\nFailed to upload {}: {} (attempt: {})".
                              format(file, ex, attempt),
                              file=sys.stderr)
                        sleep(attempt * 0.1)
    except Exception as ex:
        print("Failure to fly: {}".format(ex), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("User canceled", file=sys.stderr)
        return 3

    print("All done in {:.2f}secs ({:.2f}MB/s)".
          format(stat.runtime, stat.rate))
    return 0

if __name__ == "__main__":
    sys.exit(main())
