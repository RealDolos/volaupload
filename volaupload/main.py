""" RealDolos' funky volafile upload tool"""

# pylint: disable=broad-except

import argparse
import os
import random
import re
import shutil
import sys
import time

from configparser import ConfigParser
from functools import partial

from ._version import __version__
from .stat import FAC
from .stat import Statistics
from .utils import progressbar
from .utils import shorten
from .utils import SORTING
from .utils import try_advise
from .utils import try_unlink

# False-positive
# pylint: disable=no-name-in-module
from path import path
# pylint: enable=no-name-in-module

BUFFER_SIZE = 1 << 26
BLOCK_SIZE = 1 << 20
CONFIG = path("~/.vola.conf").expand()
UPDATE_INFO = "https://api.github.com/repos/RealDolos/volaupload/tags"


def progress_callback(cur, tot, file, nums, stat):
    """Print progress (and fadvise)"""
    # pylint: disable=anomalous-backslash-in-string
    stat.record(cur)

    cols = shutil.get_terminal_size((25, 72)).columns

    def colorstripped(line):
        """Return regularly colored and stripped versions of a print message"""
        return line, re.sub("\033\[.*?m", "", line)

    def baseinfo():
        """Compose basic information"""
        ccur, ctot, per = cur / FAC, tot / FAC, float(cur) / tot
        ptot = ""
        lnum = len(str(nums["files"]))
        if nums["files"] > 1:
            ptot = progressbar(nums["cur"] + cur, nums["total"], 10) + " "
        times = ("{:.1f}s/{:.0f}s".
                 format(stat.runtime, stat.eta(tot)))
        fmt = ("\033[1m{}\033[0m"
               "\033[31;1m{:{}}/{:{}}\033[0m - "
               "\033[33;1m{}\033[0m "
               "\033[1m{:6.1%}\033[0m "
               "{{}} {:.1f}/{:.1f} - "
               "\033[1m{:5.2f}MB/s\033[0m ({:5.2f}MB/s), "
               "\033[34;1m{:>12.12}\033[0m")
        return fmt.format(ptot,
                          nums["item"], lnum, nums["files"], lnum,
                          progressbar(cur, tot, 30 if cols > 80 else 20),
                          per,
                          ccur, ctot,
                          stat.rate, stat.rate_last,
                          times)

    line, stripped = colorstripped(baseinfo())
    short_file = shorten(file.name, max(10, cols - len(stripped) - 2))
    line, stripped = colorstripped(line.format(short_file))

    cols = max(0, cols - len(stripped) - 4)
    tty = sys.stdout.isatty()
    if not tty or os.name == "nt":
        line = stripped

    if tty:
        clear = " " * cols if os.name == "nt" else "\033[K"
        print("\r{}{}".format(line, clear),
              end="", flush=True)
    else:
        print(line, flush=True)

    # Tell OS to buffer some moar!
    if cur + BUFFER_SIZE < tot:
        try_advise(file, cur + BUFFER_SIZE, BUFFER_SIZE * 2)


def upload(room, file, nums, block_size=BLOCK_SIZE):
    """Uploads a file and prints the progress while pushing bits and bytes"""
    stat = Statistics()
    with open(file, "rb", buffering=block_size) as advp:
        callback = partial(progress_callback,
                           file=advp, nums=nums, stat=stat)
        callback(0, file.size)
        room.upload_file(advp,
                         upload_as=file.name,
                         blocksize=block_size,
                         callback=callback)
        print("", flush=True)


def parse_args():
    """Parse command line arguments into something sane!"""
    sorts = tuple(SORTING.keys()) + ("none", "rnd")

    config = ConfigParser()
    try:
        config.read(CONFIG)
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
    parser.add_argument("--bind", "-i", dest="bind", type=str,
                        default=config.get("bind", None),
                        help="Bind to specific source address")
    parser.add_argument("--retarddir", "-R", dest="rdir", action="store_true",
                        help="Upload all files within directories passed to "
                        "volaupload (this is mainly here for people too stupid to find and xargs!)")
    parser.set_defaults(delete=False, rdir=False)
    parser.add_argument('files', metavar='FILE', type=str, nargs='+',
                        help='files to upload')
    args = parser.parse_args()

    if not args.user or not re.match(r"[\w\d]{3,12}$", args.user):
        parser.error("No valid user name provided")

    if args.passwd and args.passwd == "":
        parser.error("No valid user password provided")

    if not args.room:
        parser.error("No valid room provided")

    def files_because_windows_is_stupid(files):
        """Windows is too stupid to glob"""
        for i in files:
            i = path(i)
            if "*" in i or "?" in i and os.name == "nt":
                parent = i.parent or path(".")
                yield from parent.files(str(i.name))
                continue
            if i.isfile():
                yield i
            elif args.rdir and i.isdir():
                yield from i.walkfiles()

    args.files = list(files_because_windows_is_stupid(args.files))

    if not len(args.files):
        parser.error("No valid files selected")

    if args.sort == "none":
        pass
    elif args.sort == "rnd":
        random.shuffle(args.files)
    elif args.sort:
        args.files = sorted(args.files, key=SORTING[args.sort])

    return args


def check_update():
    """Check if there is a new version"""
    import requests

    config = ConfigParser()
    try:
        config.read(CONFIG)
        try:
            section = config["update"]
        except Exception:
            config.add_section("update")
            section = config["update"]
    except Exception:
        section = dict()

    check = float(section.get("check", 0))
    ver = section.get("version", __version__)
    url = section.get("url", None)
    now = time.time()

    if check + 86400 < now:
        ver = requests.get(UPDATE_INFO).json()[0]
        url = ver["zipball_url"]
        ver = ver["name"]
        section["check"] = str(now)
        section["version"] = ver
        section["url"] = url
        with open(CONFIG, "w") as configfile:
            config.write(configfile)

    if ([int(i) for i in ver.replace("v", "").split(".")] >
            [int(i) for i in __version__.split(".")] and url):
        print("New version {} available:\nInstall: pip3 install -U {}".
              format(ver, url),
              flush=True)

def override_socket(bind):
    """ Bind all sockets to specific address """
    import socket

    class BoundSocket(socket.socket):
        """
        requests is kinda an asshole when it comes to using source_address.
        Also volapi is also an asshole.
        """

        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)

        def connect(self, address):
            try:
                self.bind((bind, 0))
            except Exception:
                pass
            return super().connect(address)

        def connect_ex(self, address):
            try:
                self.bind((bind, 0))
            except Exception:
                pass
            return super().connect_ex(address)

        def bind(self, address):
            super().bind(address)

    socket.socket = BoundSocket

def main():
    """Program, kok"""

    args = parse_args()

    if args.bind:
        override_socket(args.bind)

    try:
        check_update()
    except Exception as ex:
        print("Failed to check for new version:", ex,
              file=sys.stderr, flush=True)

    from volapi import Room

    stat = Statistics()
    total_current = 0
    try:
        print("Starting DoS... ", end="", flush=True)
        with Room(args.room, args.user, subscribe=False) as room:
            print("done")
            if args.passwd:
                print("Greenfagging in as {}... ".format(args.user),
                      end="", flush=True)
                room.user.login(args.passwd)
                print("done")

            files = args.files
            total_length = sum(f.size for f in files)

            print("Pushing attack bytes to mainframe... {:.2f}MB in total".
                  format(total_length / FAC),
                  flush=True)
            upload_file = partial(upload,
                                  room=room,
                                  block_size=args.block_size)
            for i, file in enumerate(files):
                for attempt in range(args.attempts):
                    try:
                        nums = dict(item=i + 1, files=len(files),
                                    cur=total_current, total=total_length)
                        upload_file(file=file, nums=nums)
                        total_current += file.size
                        stat.record(total_current)
                        if args.delete:
                            try_unlink(file)

                        # Exit attempt loop
                        break
                    except Exception as ex:
                        print("\nFailed to upload {}: {} (attempt: {})".
                              format(file, ex, attempt),
                              file=sys.stderr, flush=True)
                        time.sleep(attempt * 0.1)
    except Exception as ex:
        print("\nFailure to fly: {}".format(ex), file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nUser canceled", file=sys.stderr, flush=True)
        return 3
    finally:
        print("All done in {:.2f}secs ({:.2f}MB/s)".
              format(stat.runtime, stat.rate))
    return 0
