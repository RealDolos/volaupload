#!/usr/bin/env python3

from setuptools import setup
import re

def version():
    with open("volaupload/__init__.py") as fp:
        return re.search('__version__ = "(.+?)"', fp.read()).group(1)

setup(
    name="volaupload",
    version=version(),
    description="Upload files to volafile.io",
    long_description=open("README.rst").read(),
    url="https://github.com/RealDolos/volaupload",
    license="MIT",
    author="RealDolos",
    author_email="dolosthegreat@safe-mail.net",
    packages=['volaupload'],
    scripts=["scripts/volaupload.py"],
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
    install_requires=[l.strip() for l in open("requirements.txt").readlines()]
)
