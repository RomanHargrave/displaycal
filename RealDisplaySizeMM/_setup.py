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
	setup(name = 'RealDisplaySizeMM', version='1.0',
		description = 'Return the size (in mm) of a given display.',
		ext_modules = [RealDisplaySizeMM])

if __name__ == '__main__':
	_setup()