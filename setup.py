#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import re
import shutil
from subprocess import call
import sys
import tempfile

from distutils.sysconfig import get_python_lib

from ez_setup import use_setuptools
use_setuptools()

try:
	import setuptools
	from setuptools import setup, Extension
	print "using setuptools"
except ImportError:
	setuptools = None
	from distutils.core import setup, Extension
	print "using distutils"

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)

name = "dispcalGUI"
version = "0.2.2b"
desc = "A graphical user interface for the Argyll CMS display calibration utilities"

dry_run = False
prefix = None
scripts = None
share_prefix = None

for arg in sys.argv[1:]:
	if arg in ("-n", "--dry-run"):
		dry_run = True
	elif arg.startswith("--prefix"):
		opt, arg = arg.split("=")
		prefix = arg
	elif arg.startswith("--install-scripts"):
		opt, arg = arg.split("=")
		scripts = arg
	elif arg.startswith("--install-data"):
		opt, arg = arg.split("=")
		share_prefix = arg

if not prefix:
	if sys.platform == "win32":
		if "--user" in sys.argv[1:]:
			prefix = os.path.join(os.getenv("APPDATA"), "Python", 
				"Python" + sys.version[0] + sys.version[2]) # using sys.version in this way is consistent with setuptools
		else:
			prefix = sys.prefix
	elif sys.platform == "darwin" and not "--user" in sys.argv[1:]:
		# if "--user" in sys.argv[1:]:
			# # normal user
			# prefix = os.path.join(os.path.expanduser("~"), "Library", "Python",
				# sys.version[:3]) # using sys.version in this way is consistent with setuptools
		# else:
			# # root
		prefix = sys.prefix
	else:
		# Linux/Unix
		if "--user" in sys.argv[1:]:
			# normal user
			prefix = os.path.join(os.path.expanduser("~"), ".local")
		else:
			# root
			prefix = os.path.join(os.path.sep, "usr", "local")

if not scripts:
	if sys.platform == "win32": #in ("darwin", "win32"):
		if "--user" in sys.argv[1:]:
			script_prefix = os.path.join(os.getenv("APPDATA"), "Python")
		else:
			script_prefix = prefix
	else:
		# Linux/Unix
		script_prefix = prefix
		# if "--user" in sys.argv[1:]:
			# # normal user
			# script_prefix = os.path.expanduser("~")
		# else:
			# # root
			# script_prefix = prefix
	if sys.platform == "win32":
		scripts = os.path.join(script_prefix, "Scripts")
	else:
		# Linux/Unix and Mac OS X
		scripts = os.path.join(script_prefix, "bin")

if sys.platform == "win32" or (sys.platform == "darwin" and not "--user" in sys.argv[1:]): # in ("darwin", "win32"):
	if "--user" in sys.argv[1:] or prefix != sys.prefix:
		pkg_prefix = os.path.join(prefix, "site-packages")
		if sys.platform == "win32" and not share_prefix:
			share_prefix = os.getenv("APPDATA")
			# if setuptools:
				# share_prefix = os.path.join(pkg_prefix, "%(name)s-%(version)s-py%(pyver)s-win32.egg" % {
					# "name": name, 
					# "version": version, 
					# "pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
				# })
			# else:
				# share_prefix = pkg_prefix
	else:
		pkg_prefix = get_python_lib()
		if not share_prefix:
			share_prefix = pkg_prefix
	share = os.path.join(share_prefix, name)
	doc = share # install doc files to package dir
else:
	pkg_prefix = get_python_lib(prefix=prefix)
	if "--user" in sys.argv[1:]:
		# normal user
		if not share_prefix:
			share_prefix = os.getenv("XDG_DATA_HOME",
				os.path.join(os.path.expanduser("~"), ".local", "share"))
		share = os.path.join(share_prefix, name)
		doc = os.path.join(share_prefix, "doc", name)
	else:
		# root
		if not share_prefix:
			share_prefix = os.getenv(
				"XDG_DATA_DIRS", 
				os.pathsep.join(
					(
						os.path.join(os.path.sep, "usr", "local", "share"), 
						os.path.join(os.path.sep, "usr", "share")
					)
				)
			).split(os.pathsep)[0]
		share = os.path.join(share_prefix, name)
		doc = os.path.join(share_prefix, "doc", name)

pkg = os.path.join(pkg_prefix, name)

print "prefix:", prefix
print "pkg:", pkg
print "scripts:", scripts
print "share:", share
print "doc:", doc

if "uninstall" in sys.argv[1:]:

	# quick and dirty uninstall

	if dry_run:
		print "dry run - nothing will be removed"
	removed = []
	# remove package files
	paths = glob.glob(pkg + 
		"-%(version)s-py%(pyver)s*.egg" % {
			"version": version, 
			"pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
		}
	)
	paths += glob.glob(pkg + 
		"-%(version)s-py%(pyver)s*.egg-info" % {
			"version": version, 
			"pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
		}
	)
	paths += [os.path.join(scripts, name)]
	if sys.platform == "win32":
		paths += [os.path.join(scripts, name + ".cmd")]
	if share != pkg:
		paths += [os.path.join(share, fname) for fname in [
				"LICENSE.txt",
				"README.html",
				"test.cal"
			]
		]
	for path in paths:
		if os.path.isfile(path):
			if dry_run:
				print path
				continue
			print "removing", path
			os.remove(path)
			removed += [path]
	# remove package directories
	paths = glob.glob(pkg)
	paths += glob.glob(pkg + 
		"-%(version)s-py%(pyver)s*.egg" % {
			"version": version, 
			"pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
		}
	)
	if share != pkg:
		paths += [os.path.join(share, dir) for dir in [
				"lang",
				"presets",
				"screenshots",
				"theme",
				"ti1"
			]
		]
	if doc != pkg and doc != share:
		paths += glob.glob(doc)
	for path in paths:
		# are we in the right place?
		if not os.path.isfile(os.path.join(path, name + ".py")) and \
			not os.path.isdir(os.path.join(path, name)) and \
			not os.path.isdir(path):
			continue
		if dry_run:
			print path
			continue
		print "removing", path
		shutil.rmtree(path, True)
		removed += [path]
	if not removed:
		print "nothing removed"

else:
	
	tempdir = os.path.join(tempfile.gettempdir(), name + "-" + version)
	
	if "-h" in sys.argv[1:] or "--help" in sys.argv[1:] or \
		"--help-commands" in sys.argv[1:] or "-n" in sys.argv[1:] or \
		"--dry-run" in sys.argv[1:]:
		data_files = []
		ext_modules = []
	else:
		# copy files to temp dir so known absolute paths can be used (fixes bdist_rpm)
		for source in [
			"RealDisplaySizeMM", 
			"lang", 
			"presets", 
			"screenshots", 
			"theme", 
			"ti1", 
			"LICENSE.txt", 
			"README.html", 
			"test.cal"
		]:
			srcpath = os.path.join(pydir, source)
			if os.path.exists(srcpath):
				tmppath = os.path.join(tempdir, source)
				if not os.path.exists(tmppath):
					if os.path.isfile(srcpath):
						shutil.copy2(srcpath, tmppath)
					else:
						shutil.copytree(srcpath, tmppath)
		
		data_files = [
			(os.path.join(share, "lang"), 
				[os.path.join(tempdir, "lang", fname) for fname in 
				glob.glob(os.path.join(tempdir, "lang", "*.json"))]), 
			(os.path.join(share, "presets"), 
				[os.path.join(tempdir, "presets", fname) for fname in 
				glob.glob(os.path.join(tempdir, "presets", "*.icc"))]), 
			(os.path.join(share, "screenshots"), 
				[os.path.join(tempdir, "screenshots", fname) for fname in 
				glob.glob(os.path.join(tempdir, "screenshots", "*.png"))]),
			(os.path.join(share, "theme"), 
				[os.path.join(tempdir, "theme", fname) for fname in 
				glob.glob(os.path.join(tempdir, "theme", "*.png"))]), 
			(os.path.join(share, "theme", "icons"), 
				[os.path.join(tempdir, "theme", "icons", fname) for fname in 
				glob.glob(os.path.join(tempdir, "theme", "icons", "*.icns|*.ico"))]), 
			(os.path.join(share, "ti1"), 
				[os.path.join(tempdir, "ti1", fname) for fname in 
				glob.glob(os.path.join(tempdir, "ti1", "*.ti1"))]),
			(doc, [os.path.join(tempdir, "LICENSE.txt")]),
			(doc, [os.path.join(tempdir, "README.html")]),
			(doc, [os.path.join(tempdir, "test.cal")])
		]
		if doc != share:
			data_files += [
				(os.path.join(doc, "theme"), 
					[os.path.join(tempdir, "theme", "header-readme.png")]), 
				(os.path.join(doc, "theme", "icons"), 
					[os.path.join(tempdir, "theme", "icons", "favicon.ico")]), 
			]
		for dname in ("16x16", "22x22", "24x24", "32x32", "48x48", "256x256"):
			data_files += [(os.path.join(share, "theme", "icons", dname), 
				[os.path.join(tempdir, "theme", "icons", dname, fname) for fname in 
				glob.glob(os.path.join(tempdir, "theme", "icons", dname, "*.png"))])]

		if sys.platform == "win32":
			RealDisplaySizeMM = Extension(name + "." + "RealDisplaySizeMM", 
				sources = [os.path.join(tempdir, "RealDisplaySizeMM", "RealDisplaySizeMM.c")], 
				libraries = ["user32", "gdi32"], 
				define_macros=[("NT", None)])
		elif sys.platform == "darwin":
			RealDisplaySizeMM = Extension(name + "." + "RealDisplaySizeMM", 
				sources = [os.path.join(tempdir, "RealDisplaySizeMM", "RealDisplaySizeMM.c")],
				extra_link_args = ["-framework Carbon", "-framework Python", "-framework IOKit"], 
				define_macros=[("__APPLE__", None), ("UNIX", None)])
		else:
			RealDisplaySizeMM = Extension(name + "." + "RealDisplaySizeMM", 
				sources = [os.path.join(tempdir, "RealDisplaySizeMM", "RealDisplaySizeMM.c")], 
				libraries = ["Xinerama", "Xrandr", "Xxf86vm"], 
				define_macros=[("UNIX", None)])
		ext_modules = [RealDisplaySizeMM]

	requires = [
		"wxPython (>= 2.8.7)"
	]
	if sys.platform == "win32":
		requires += [
			"SendKeys (>= 0.3)",
			"pywin32 (>= 213.0)"
		]
	elif sys.platform == "darwin":
		requires += [
			"appscript (>= 0.19)"
		]
	else:
		pass
	install_requires = [req.replace("(", "").replace(")", "") for req in requires]
	try:
		import wx
		if wx.__version__ >= "2.8.7":
			install_requires.remove("wxPython >= 2.8.7")
	except ImportError:
		pass

	scripts = [name]
	if sys.platform == "win32":
		scripts += [name + ".cmd"]

	setup(
		author="Florian Höch",
		author_email="%s@hoech.net" % name,
		classifiers=[
			"Development Status :: 4 - Beta",
			"Environment :: Console",
			"Intended Audience :: End Users/Desktop",
			"Intended Audience :: Advanced End Users",
			"License :: OSI Approved :: GNU General Public License (GPL)",
			"Operating System :: OS Independent (Written in an interpreted language)",
			"Programming Language :: Python",
			"Topic :: Graphics",
			"User Interface :: Project is a user interface (UI) system",
			"User Interface :: wxWidgets",
		],
		data_files=data_files,
		description=desc,
		download_url="http://%(name)s.hoech.net/%(name)s-%(version)s-src.zip" % 
			{"name": name, "version": version},
		ext_modules=ext_modules,
		install_requires=install_requires, # setuptools functionality
		license="GPL v3",
		long_description=desc,
		name=name,
		package_dir={name: ""},
		platforms=[
			"Python >= 2.5 < 3.0", 
			"Linux/Unix with X11", 
			"Mac OS X", 
			"Windows 2000 and newer"
		],
		py_modules=[name + "." + fname for fname in [
			"__init__", 
			"CGATS", 
			"ICCProfile", 
			"argyllRGB2XYZ", 
			"argyll_instruments", 
			"colormath", 
			"demjson", 
			name, 
			"natsort", 
			"pyi_md5pickuphelper", 
			"safe_print", 
			"subprocess26", 
			"tempfile26", 
			"trash"
		]],
		requires=requires,
		url="http://%s.hoech.net/" % name,
		scripts=scripts,
		version=version,
		zip_safe=False
	)
	
	if not "-h" in sys.argv[1:] and not "--help" in sys.argv[1:] and \
		not "--help-commands" in sys.argv[1:] and not "-n" in sys.argv[1:] and \
		not "--dry-run" in sys.argv[1:] and os.path.exists(tempdir):
		shutil.rmtree(tempdir, True)
