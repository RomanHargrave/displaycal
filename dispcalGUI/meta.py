#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	Meta information.

	When specifying version information, play nice with distutils.

	The following are valid version numbers (shown in the order that
	would be obtained by sorting according to the supplied cmp function):

		0.4       0.4.0  (these two are equivalent)
		0.4.1
		0.5a1
		0.5b3
		0.5
		0.9.6
		1.0
		1.0.4a3
		1.0.4b1
		1.0.4

	The following are examples of invalid version numbers:

		1
		2.7.2.2
		1.3.a4
		1.3pl1
		1.3c4

	(from distutils.version's StrictVersion)

"""

try:
	from __version__ import (BUILD_DATE as build, LASTMOD as lastmod, VERSION, 
							 VERSION_STRING)
except ImportError:
	lastmod = "0000-00-00T00:00:00.0Z"
	VERSION = (0, 0, 0, 0)
	VERSION_STRING = ".".join(str(n) for n in VERSION)

author = u"Florian Höch"
author_ascii = "Florian Hoech"
description = (u"A graphical user interface for the Argyll CMS display "
				"calibration utilities")
domain = "dispcalGUI.hoech.net"
name = "dispcalGUI"

version = VERSION_STRING
version_lin = VERSION_STRING # Linux
version_mac = VERSION_STRING # Mac OS X
version_win = VERSION_STRING # Windows
version_src = VERSION_STRING

version_tuple = VERSION # only ints allowed and must be exactly 4 values
