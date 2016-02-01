# -*- coding: utf-8 -*-

import platform
import sys

if sys.platform == "darwin":
	# Mac OS X has universal binaries in two flavors:
	# - i386 & PPC
	# - i386 & x86_64
	if platform.architecture()[0].startswith('64'):
		from lib64.RealDisplaySizeMM import *
	else:
		from lib32.RealDisplaySizeMM import *
else:
	# Linux and Windows have separate files
	if platform.architecture()[0].startswith('64'):
		if sys.version_info[:2] == (2, 6):
			from lib64.python26.RealDisplaySizeMM import *
		elif sys.version_info[:2] == (2, 7):
			from lib64.python27.RealDisplaySizeMM import *
	else:
		if sys.version_info[:2] == (2, 6):
			from lib32.python26.RealDisplaySizeMM import *
		elif sys.version_info[:2] == (2, 7):
			from lib32.python27.RealDisplaySizeMM import *
