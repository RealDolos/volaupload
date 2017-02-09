""" RealDolos' funky volafile upload tool"""

# pylint: disable=broad-except,anomalous-backslash-in-string,too-few-public-methods

import argparse
import os
import random
import re
import shutil
import sys
import time

from configparser import ConfigParser
from functools import partial

from path import Path

from ._version import __version__

from .stat import FAC
from .stat import Statistics

from .utils import format_time
from .utils import POSIX_FADV_WILLNEED
from .utils import progressbar
from .utils import shorten
from .utils import SORTING
from .utils import try_advise
from .utils import try_unlink

try:
    import colorama
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


BUFFER_SIZE = 1 << 26
BLOCK_SIZE = 1 << 20
CONFIG = Path("~/.vola.conf").expand()
UPDATE_INFO = "https://api.github.com/repos/RealDolos/volaupload/tags"


def get_version():
    """Get a printable version string"""
    parts = [__version__]
    if POSIX_FADV_WILLNEED:
        parts += "(fadvise)",
    return " ".join(parts)


class Callback:
    """ Bundle and print process information """
    def __init__(self, file, name, nums, info):
        self.file = file
        self.name = name
        self.nums = nums
        self.info = info
        self.stat = Statistics()

    def __call__(self, cur, tot):
        """Print progress (and fadvise)"""
        self.stat.record(cur)

        cols = shutil.get_terminal_size((25, 72)).columns

        def colorstripped(line):
            """Return regularly colored and stripped versions of a print message"""
            return line, re.sub("\033\[.*?m", "", line)

        def baseinfo():
            """Compose basic information"""
            ccur, ctot, per = cur / FAC, tot / FAC, float(cur) / tot
            ptot = ""
            lnum = len(str(self.nums["files"]))
            if self.nums["files"] > 1:
                if cols > 100:
                    ptot = progressbar(self.nums["cur"] + cur, self.nums["total"], 10) + " "
                else:
                    ptot = "{:3.0%}".format(
                        min(0.999, float(self.nums["cur"] + cur) / self.nums["total"]))
            times = "{}/{}".format(format_time(self.stat.runtime), format_time(self.stat.eta(tot)))
            fmt = ("\033[1m{ptot}\033[0m"
                   "\033[31;1m{num:{lnum}}/{files:{lnum}}\033[0m - "
                   "\033[33;1m{progress}\033[0m "
                   "\033[1m{per:6.1%}\033[0m "
                   "{{}} {ccur:.1f}/{ctot:.1f} {server}{resumes} - "
                   "\033[1m{rate:5.2f}MB/s\033[0m ({lrate:5.2f}MB/s), "
                   "\033[34;1m{times:>11}\033[0m")
            server = (self.info.get("server", "") or "N/A").split(".", 1)[0]
            resumes = self.info.get("resumecount", 0)
            resumes = "" if not resumes else "/{}".format(resumes)
            return fmt.format(ptot=ptot,
                              num=self.nums["item"], lnum=lnum,
                              files=self.nums["files"],
                              progress=progressbar(cur, tot, 30 if cols > 100 else 5),
                              per=per,
                              ccur=ccur, ctot=ctot,
                              server=server, resumes=resumes,
                              rate=self.stat.rate, lrate=self.stat.rate_last,
                              times=times)

        line, stripped = colorstripped(baseinfo())
        short_file = shorten(self.name, max(5, cols - len(stripped) - 2))
        line, stripped = colorstripped(line.format(short_file))

        cols = max(0, cols - len(stripped) - 4)
        tty = sys.stdout.isatty()
        if not tty or (not HAS_COLORAMA and os.name == "nt"):
            line = stripped

        if tty:
            clear = " " * cols if os.name == "nt" else "\033[K"
            print("\r{}{}".format(line, clear),
                  end="", flush=True)
        else:
            print(line, flush=True)

        # Tell OS to buffer some moar!
        if cur + BUFFER_SIZE < tot:
            try_advise(self.file, cur + BUFFER_SIZE, BUFFER_SIZE * 2)


def upload(room, file, nums, block_size=BLOCK_SIZE, force_server=None, prefix=None):
    """Uploads a file and prints the progress while pushing bits and bytes"""
    info = dict(server="")

    def information(idict):
        """Information callback"""
        nonlocal info, force_server
        info.update(idict)
        if force_server:
            return info.get("server", "") == force_server
        return True

    with open(file, "rb", buffering=block_size) as advp:
        callback = Callback(advp, file.name, nums, info)
        callback(0, file.size)
        upload_as = file.name
        if prefix:
            upload_as = "{} - {}".format(prefix.strip(), upload_as)
        room.upload_file(advp,
                         upload_as=upload_as,
                         blocksize=block_size,
                         callback=callback,
                         information_callback=information)
        print("", flush=True)


def parse_args():
    """Parse command line arguments into something sane!"""
    sorts = tuple(SORTING.keys()) + ("none", "rnd")

    config = ConfigParser()
    aliases = dict()
    try:
        config.read(CONFIG)
        try:
            aliases = config["aliases"]
        except Exception:
            pass
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
                        help='room or alias to upload to')
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
    parser.add_argument("--prefix", dest="prefix", type=str, default=None,
                        help="Prefix file names")
    parser.add_argument("--bind", "-i", dest="bind", type=str,
                        default=config.get("bind", None),
                        help="Bind to specific source address")
    parser.add_argument("--retarddir", "-R", dest="rdir", action="store_true",
                        help="Upload all files within directories passed to "
                        "volaupload (this is mainly here for people too stupid to find and xargs!)")
    parser.add_argument("--force-server", dest="force_server", type=str,
                        default=config.get("force_server", None),
                        help="Force a particular server")
    parser.add_argument("--version", "-V", action="version", version=get_version(),
                        help=argparse.SUPPRESS)
    parser.set_defaults(delete=False, rdir=False)
    parser.add_argument('files', metavar='FILE', type=str, nargs='+',
                        help='files to upload')
    args = parser.parse_args()

    if not args.user or not re.match(r"[\w\d]{3,12}$", args.user):
        parser.error("No valid user name provided")

    if args.passwd and args.passwd == "":
        parser.error("No valid user password provided")

    args.room = aliases.get(args.room, args.room)
    if not args.room:
        parser.error("No valid room provided")

    def files_because_windows_is_stupid(files):
        """Windows is too stupid to glob"""
        for i in files:
            i = Path(i)
            if "*" in i or "?" in i and os.name == "nt":
                parent = i.parent or Path(".")
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
            if any(f.name == "Thumbs.db" for f in files):
                class NotGonnaDoIt(Exception):
                    """roboCop, pls"""
                    pass
                raise NotGonnaDoIt("No Thumbs.db for you!")
            total_length = sum(f.size for f in files)

            print("Pushing attack bytes to mainframe... {:.2f}MB in total".
                  format(total_length / FAC),
                  flush=True)
            upload_file = partial(upload,
                                  room=room,
                                  block_size=args.block_size,
                                  force_server=args.force_server,
                                  prefix=args.prefix)
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
        print("\nFailure to fly: {} ({})".format(ex, type(ex)), file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nUser canceled", file=sys.stderr, flush=True)
        return 3
    finally:
        print("All done in {:.2f}secs ({:.2f}MB/s)".
              format(stat.runtime, stat.rate))
    return 0
