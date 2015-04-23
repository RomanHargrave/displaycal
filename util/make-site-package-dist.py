#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Collect modules from site-packages used by dispcalGUI

"""

import glob
import os
import shutil
import sys
from distutils.sysconfig import get_python_lib

try:
	import wxversion
except:
	class WxVersion(object):
		__file__ = ''
		def getInstalled(self):
			return []

	wxversion = WxVersion()

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
	print 'No wxPython versions >= %s found' % wx_minversion_str
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
else:
	wx_pth = 'wx'

# Packages to collect
pkgs = {'numpy': ['numpy'],
		'pygame': ['pygame'],
	    'wx': [wx_pth,
			   'wxversion']}
if sys.platform == 'win32':
	pkgs['wmi'] = ['wmi']
if sys.platform == 'darwin':
	pkgs['pyglet'] = ['pyglet']
	pkgs['pygame'].extend(['/Library/Frameworks/SDL_image.framework',
						   '/Library/Frameworks/SDL_mixer.framework',
						   '/Library/Frameworks/SDL_ttf.framework',
						   '/Library/Frameworks/SDL.framework'])
	pkgs['wx'].extend(glob.glob(os.path.normpath(os.path.join(
		os.path.dirname(wx_pth), '..', '..', 'libwx_*.dylib'))))


def copy(src, dst):
	if os.path.islink(src):
		os.symlink(os.readlink(src), dst)
	else:
		shutil.copy(src, dst)


# Collect packages
python_lib = get_python_lib(True)
for pkg_name, data in pkgs.iteritems():
	print('Checking for package: %s' % pkg_name)
	try:
		pkg = __import__(pkg_name)
	except ImportError, exception:
		print exception
		continue
	dist_dir = os.path.join('dist', '%s-%s-%s-py%i.%i' % ((pkg_name,
														   pkg.__version__,
														   sys.platform) +
														  sys.version_info[:2]))
	print('Destination: %s' % dist_dir)
	if not os.path.isdir(dist_dir):
		os.makedirs(dist_dir)
	for entry in data:
		pth = entry
		if not os.path.isabs(pth):
			pth = os.path.join(python_lib, pth)
		if pth.lower().endswith('.pth'):
			with open(pth) as pthfile:
				pth = os.path.join(os.path.dirname(pth), pthfile.read().strip())
		if not os.path.exists(pth):
			print('  Checking for module: %s' % pth)
			try:
				module = __import__(entry)
			except ImportError, exception:
				print exception
				continue
			filename, ext = os.path.splitext(module.__file__)
			if os.path.basename(filename) == '__init__':
				pth = os.path.dirname(filename)
				if not os.path.isdir(pth):
					while not os.path.isfile(pth):
						pth = os.path.dirname(pth)
						print '  Checking for %s' % pth
					if not os.path.isfile(pth):
						print('  Warning: Module not found: %s' % entry)
						continue
			else:
				if ext in ('.pyc', '.pyo'):
					ext = '.py'
				pth = '%s%s' % (filename, ext)
		if os.path.isdir(pth):
			print('  Collecting package: %s' % pth)
			dirname = os.path.dirname(pth)
			for dirpath, dirnames, filenames in os.walk(pth):
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
						print('  Collecting file: %s' % pth)
						copy(src, dst)
		else:
			dst = os.path.join(dist_dir, os.path.basename(pth))
			if not os.path.isfile(dst):
				print('  Collecting file: %s' % pth)
				copy(pth, dst)
