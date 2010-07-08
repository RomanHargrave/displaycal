#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	Meta information

"""

import sys

try:
	from __version__ import (BUILD_DATE as build, LASTMOD as lastmod, VERSION, 
							 VERSION_BASE, VERSION_STRING)
except ImportError:
	build = lastmod = "0000-00-00T00:00:00.0Z"
	VERSION = VERSION_BASE = (0, 0, 0, 0)
	VERSION_STRING = ".".join(str(n) for n in VERSION)

if sys.version_info[:2] < (3, ):
	author = "Florian Höch".decode("utf8")
else:
	author = "Florian Höch"
author_ascii = "Florian Hoech"
author_email = "dispcalGUI@hoech.net"
description = ("A graphical user interface for the Argyll CMS display "
				"calibration utilities")
domain = "dispcalGUI.hoech.net"
name = "dispcalGUI"

py_maxversion = (2, 7)
py_minversion = (2, 5)

version = VERSION_STRING
version_lin = VERSION_STRING # Linux
version_mac = VERSION_STRING # Mac OS X
version_win = VERSION_STRING # Windows
version_src = VERSION_STRING

version_tuple = VERSION # only ints allowed and must be exactly 4 values

wx_minversion = (2, 8, 6)
