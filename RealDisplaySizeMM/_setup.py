#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from distutils.core import setup, Extension

def _setup():
	if sys.platform == 'win32':
		RealDisplaySizeMM = Extension('RealDisplaySizeMM', 
			sources = ['RealDisplaySizeMM.c'], 
			libraries = ['user32', 'gdi32'], 
			define_macros=[('NT', None)])
	elif sys.platform == 'darwin':
		RealDisplaySizeMM = Extension('RealDisplaySizeMM', 
			sources = ['RealDisplaySizeMM.c'],
			extra_link_args = ['-framework Carbon', '-framework Python', '-framework IOKit'], 
			define_macros=[('__APPLE__', None), ('UNIX', None)])
	else:
		RealDisplaySizeMM = Extension('RealDisplaySizeMM', 
			sources = ['RealDisplaySizeMM.c'], 
			libraries = ['Xinerama', 'Xrandr', 'Xxf86vm'], 
			define_macros=[('UNIX', None)])
	setup(
		author = 'Florian Höch (adapted from C code of the open-source color management system Argyll CMS by Graeme W. Gill)',
		author_email = 'fh@hoech.net',
		license = 'GPL v3',
		platforms = ['Linux/Unix with X11', 'Mac OS X', 'Windows 2000 and newer'],
		url = 'http://hoech.net/',
		name = 'RealDisplaySizeMM', 
		version='1.0',
		description = 'Return the size (in mm) of a given display.',
		long_description = 'Return the size (in mm) of a given display.',
		ext_modules = [RealDisplaySizeMM])

if __name__ == '__main__':
	_setup()