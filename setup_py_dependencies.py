#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
name = 'dispcalGUI_py_dependencies'
version = '0.2.2b'
setup(name=name,
	  version=version,
	  py_modules=['argyllRGB2XYZ', 
				  'argyll_instruments', 
				  'CGATS', 
				  'colormath', 
				  'ICCProfile', 
				  'natsort', 
				  'pyi_md5pickuphelper', 
				  'safe_print', 
				  'subprocess26', 
				  'tempfile26', 
				  'trash'
				 ],
	  author='Florian Höch',
	  author_email='dispcalGUI@hoech.net',
	  url='http://dispcalGUI.hoech.net/',
	  download_url='http://dispcalGUI.hoech.net/dispcalGUI-%(version)-src.zip' % {'version': version},
	  description='Python modules needed by dispcalGUI.py',
	  long_description="""Python modules needed by dispcalGUI.py, a graphical
	   user interface for the Argyll CMS display calibration utilities""",
	  license='GNU GPL 3.0',
	  keywords=['dispcalGUI'],
	  platforms=[],
	  classifiers=['Development Status :: 4 - Beta',
				   'Intended Audience :: End Users/Advanced End Users',
				   'License :: OSI Approved :: GNU General Public License (GPL)',
				   'Operating System :: OS Independent',
				   'Programming Language :: Python',
				   'Topic :: Graphics'
				  ]
	  )