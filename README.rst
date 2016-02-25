VolaUpload
==========
The `volafile.io <https://volafile.io/>`_ upload tool of your choice!

Installation
------------
Use pip already

::

    pip install https://github.com/RealDolos/volaupload/archive/master.zip


Windows user might wanna try, after installing python3 that is:

::

    py -3 -m pip install https://github.com/RealDolos/volaupload/archive/master.zip

Usage
-----
::

    volaupload -r ROOM FILE ...
    volaupload --help


Windows user might wanna try:

::

    py -3 -m volaupload ...

Configuration
-------------

Create :code:`~/.vola.conf` with a :code:`[vola]` section.
Currently the following configuration parameters are recognized:

- :code:`user` - User name to use with vola
- :code:`passwd` - Password to greenfag the user with
- :code:`attempts` - Number of attempts to perform
- :code:`bind` - to a specific address
- :code:`force_server` - Because not all servers are equal

Additionally, you may create an :code:`[aliases]` section, where you can specify
case insensitive names for rooms, e.g.

- :code:`beepi = BEEPi`
- :code:`cucks = BEEPi`
