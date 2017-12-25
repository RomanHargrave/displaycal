# -*- coding: utf-8 -*-

"""
	Meta information

"""

import re
import sys

try:
	from __version__ import (BUILD_DATE as build, LASTMOD as lastmod, VERSION, 
							 VERSION_BASE, VERSION_STRING)
except ImportError:
	build = lastmod = "0000-00-00T00:00:00.0Z"
	VERSION = None

if not VERSION or "--test-update" in sys.argv[1:]:
	VERSION = VERSION_BASE = (0, 0, 0, 0)
	VERSION_STRING = ".".join(str(n) for n in VERSION)

if sys.version_info[:2] < (3, ):
	author = "Florian Höch".decode("utf8")
else:
	author = "Florian Höch"
author_ascii = "Florian Hoech"
description = ("Display calibration and profiling with a focus on accuracy and "
			   "versatility")
longdesc = ("Calibrate and characterize your display devices using "
					  "one of many supported measurement instruments, with "
					  "support for multi-display setups and a variety of "
					  "available options for advanced users, such as "
					  "verification and reporting functionality to evaluate "
					  "ICC profiles and display devices, creating video 3D "
					  "LUTs, as well as optional CIECAM02 gamut mapping to "
					  "take into account varying viewing conditions.")
domain = "displaycal.net"
author_email = "florian" + chr(0100) + domain
name = "DisplayCAL"
name_html = '<span class="appname">Display<span>CAL</span></span>'

py_maxversion = (2, 7)
py_minversion = (2, 6)

version = VERSION_STRING
version_lin = VERSION_STRING # Linux
version_mac = VERSION_STRING # Mac OS X
version_win = VERSION_STRING # Windows
version_src = VERSION_STRING
version_short = re.sub("(?:\.0){1,2}$", "", version)

version_tuple = VERSION # only ints allowed and must be exactly 4 values

wx_minversion = (2, 8, 8)


def script2pywname(script):
	""" Convert all-lowercase script name to mixed-case pyw name """
	a2b = {name + "-3dlut-maker": name + "-3DLUT-maker",
		   name + "-vrml-to-x3d-converter": name + "-VRML-to-X3D-converter"}
	if script.lower().startswith(name.lower()):
		pyw = name + script[len(name):]
		return a2b.get(pyw, pyw)
	return script
