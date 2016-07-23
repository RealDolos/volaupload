#!/usr/bin/env python3
"""
Set it up!!!!
volaupload welcomes all cucks
"""

from setuptools import setup

import os
import re

def version():
    """Thanks python!"""
    with open("volaupload/_version.py") as filep:
        return re.search('__version__ = "(.+?)"', filep.read()).group(1)

requirements = [l.strip() for l in open("requirements.txt").readlines()]
if os.name == "nt":
    requirements += "win-unicode-console", "colorama"

setup(
    name="volaupload",
    version=version(),
    description="Upload files to volafile.io",
    long_description=open("README.rst").read(),
    url="https://github.com/RealDolos/volaupload",
    license="MIT",
    author="RealDolos",
    author_email="dolos@cock.li",
    packages=['volaupload'],
    entry_points={"console_scripts": ["volaupload = volaupload.__main__:run"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: System :: Archiving",
        "Topic :: Utilities",
    ],
    install_requires=requirements
    )
