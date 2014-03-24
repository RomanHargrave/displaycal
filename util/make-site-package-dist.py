#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Collect modules from site-packages used by dispcalGUI

"""

import os
import shutil
import sys
from distutils.sysconfig import get_python_lib

import wxversion

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dispcalGUI.meta import wx_minversion

# Search for a suitable wx version
wx_minversion_str = '.'.join(str(n) for n in wx_minversion[:2])
wxversions_all = wxversion.getInstalled()
wxversions_candidates = []
for wxv in wxversions_all:
	if wxv >= wx_minversion_str:
		wxversions_candidates.append(wxv)
if not wxversions_candidates:
	raise SystemExit('No wxPython versions >= %s found. Aborting.'
					 % wx_minversion_str)
choice = 1
if len(wxversions_candidates) > 1:
	print('Several wxPython versions >= %s found.' % wx_minversion_str)
	print('')
	for i, wxv in enumerate(wxversions_candidates):
		print('%2i: wx-%s' % (i + 1, wxv))
	print('')
	while choice:
		choice = raw_input('Please select (1..%i) and press <ENTER>,\n'
						   'or press just <ENTER> to abort: '
						   % len(wxversions_candidates))
		if not choice:
			sys.exit()
		try:
			choice = int(choice)
		except ValueError:
			print('Error: Only integers in range %i to %i allowed.'
				  % (1, len(wxversions_candidates)))
		else:
			break
wx_pth = os.path.join(os.path.dirname(wxversion.__file__),
					  'wx-%s' % wxversions_candidates[choice - 1])
print('Your choice: %s' % wx_pth)
if raw_input('Press <ENTER> to continue, X <ENTER> to abort: ').upper() == 'X':
	sys.exit()

# Packages to collect
pkgs = {'numpy': ['numpy'],
	    'wx': [wx_pth,
			   'wxversion']}
if sys.platform == 'win32':
	pkgs['wmi'] = ['wmi']

# Collect packages
python_lib = get_python_lib(True)
for pkg_name, data in pkgs.iteritems():
	pkg = __import__(pkg_name)
	dist_dir = os.path.join('dist', '%s-%s-%s-py%i.%i' % ((pkg_name,
														   pkg.__version__,
														   sys.platform) +
														  sys.version_info[:2]))
	print('Destination: %s' % dist_dir)
	if not os.path.isdir(dist_dir):
		os.makedirs(dist_dir)
	for entry in data:
		module = entry
		if not os.path.isabs(entry):
			entry = os.path.join(python_lib, entry)
		if entry.lower().endswith('.pth'):
			with open(entry) as pth:
				entry = os.path.join(os.path.dirname(pth), pth.read().strip())
		if os.path.isdir(entry):
			print('  Collecting package: %s' % entry)
			dirname = os.path.dirname(entry)
			for dirpath, dirnames, filenames in os.walk(entry):
				for filename in filenames:
					src = os.path.join(dirpath, filename)
					if filename in ('unins000.exe', 'unins000.dat'):
						print('  Skipping %s' % src)
						continue
					name, ext = os.path.splitext(filename)
					if ext in ('.pyc', '.pyo'):
						continue
					dst_dir = os.path.join(dist_dir,
										   os.path.relpath(dirpath, dirname))
					if not os.path.isdir(dst_dir):
						os.makedirs(dst_dir)
					dst = os.path.join(dst_dir, filename)
					if not os.path.isfile(dst):
						shutil.copy(src, dst)
		else:
			print('  Collecting module: %s' % entry)
			module = __import__(module)
			filename, ext = os.path.splitext(module.__file__)
			if ext in ('.pyc', '.pyo'):
				ext = '.py'
			pth = '%s%s' % (filename, ext)
			dst = os.path.join(dist_dir, os.path.basename(pth))
			if not os.path.isfile(dst):
				shutil.copy(pth, dst)
