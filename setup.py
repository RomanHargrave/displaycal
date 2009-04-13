#!/usr/bin/env python
# -*- coding: utf-8 -*-

from getopt import getopt
import glob
import os
import re
import shutil
from subprocess import call
import sys
import tempfile

from distutils.sysconfig import get_python_lib

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)
pyver_str = sys.version.split()[0]
pyver = map(int, pyver_str.split("."))

name = "dispcalGUI"
version = "0.2.2b"
desc = "A graphical user interface for the Argyll CMS display calibration utilities"

if sys.platform == "win32":
	exec_prefix = sys.exec_prefix
	prefix = sys.prefix
	share_prefix = os.path.join(get_python_lib(), name)
elif sys.platform == "darwin":
	exec_prefix = sys.exec_prefix
	prefix = sys.prefix
	if os.geteuid() == 0:
		share_prefix = os.path.join(os.path.join(os.path.sep, 
			"Library", "Application Support"), name)
	else:
		share_prefix = os.path.join(os.path.join(os.path.expanduser("~"), 
			"Library", "Application Support"), name)
else:
	xdg_data_home = os.getenv("XDG_DATA_HOME",
		os.path.join(os.path.expanduser("~"), ".local", "share"))
	xdg_data_dirs = os.getenv(
		"XDG_DATA_DIRS", 
		os.pathsep.join(
			(
				os.path.join(os.path.sep, "usr", "local", "share"), 
				os.path.join(os.path.sep, "usr", "share")
			)
		)
	).split(os.pathsep)
	if os.geteuid() == 0:
		exec_prefix = os.path.join(os.path.sep, "usr", "local")
		prefix = os.path.join(os.path.sep, "usr", "local")
		share_prefix = os.path.join(xdg_data_dirs[0], name)
	else:
		exec_prefix = os.path.expanduser("~")
		prefix = os.path.join(os.path.expanduser("~"), ".local")
		share_prefix = os.path.join(xdg_data_home, name)

if "uninstall" in sys.argv[1:]:

	# quick and dirty uninstall

	dry_run = False
	opts, args = getopt(sys.argv[2:], "dp:", ["dry-run", "prefix="])
	for opt, arg in opts:
		if opt in ("-d", "--dry-run"):
			dry_run = True
		elif opt in ("-p", "--prefix"):
			exec_prefix = prefix = arg
			share_prefix = os.path.join(arg, "share", name)

	pkg_prefix = os.path.join(get_python_lib(prefix=prefix), name)
	if dry_run:
		print "dry run - nothing will be removed"
	removed = []
	for objname in glob.glob(pkg_prefix + "*") + glob.glob(share_prefix + "*"):
		if objname in removed:
			continue
		print "removing", objname
		if dry_run:
			continue
		if os.path.isdir(objname):
			shutil.rmtree(objname, True)
		else:
			os.remove(objname)
		removed += [objname]
	if sys.platform == "win32":
		files_to_remove = [
			os.path.join(exec_prefix, "Scripts", name),
			os.path.join(exec_prefix, "Scripts", name + ".cmd")
		]
	else:
		# Linux/Unix and Mac OS X
		files_to_remove = [os.path.join(exec_prefix, "bin", name)]
	for path in files_to_remove:
		if os.path.exists(path):
			print "removing", path
			if dry_run:
				continue
			os.remove(path)
			removed += [path]
	if not removed:
		print "nothing removed"

else:

	try:
		from setuptools import setup, Extension
		print "using setuptools"
	except ImportError:
		from ez_setup import use_setuptools
		use_setuptools()

	try:
		from setuptools import setup, Extension
		print "using setuptools"
	except ImportError:
		from distutils.core import setup, Extension
		print "using distutils"
	
	# copy files to temp dir so known absolute paths can be used (fixes bdist_rpm)
	tempdir = os.path.join(tempfile.gettempdir(), name + "-" + version)
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
	
	data_files = [
		(os.path.join(share_prefix, "lang"), 
			[os.path.join(tempdir, "lang", fname) for fname in 
			glob.glob(os.path.join(tempdir, "lang", "*.json"))]), 
		(os.path.join(share_prefix, "presets"), 
			[os.path.join(tempdir, "presets", fname) for fname in 
			glob.glob(os.path.join(tempdir, "presets", "*.icc"))]), 
		(os.path.join(share_prefix, "screenshots"), 
			[os.path.join(tempdir, "screenshots", fname) for fname in 
			glob.glob(os.path.join(tempdir, "screenshots", "*.png"))]),
		(os.path.join(share_prefix, "theme"), 
			[os.path.join(tempdir, "theme", fname) for fname in 
			glob.glob(os.path.join(tempdir, "theme", "*.png"))]), 
		(os.path.join(share_prefix, "theme", "icons"), 
			[os.path.join(tempdir, "theme", "icons", fname) for fname in 
			glob.glob(os.path.join(tempdir, "theme", "icons", "*.icns|*.ico"))]), 
		(os.path.join(share_prefix, "ti1"), 
			[os.path.join(tempdir, "ti1", fname) for fname in 
			glob.glob(os.path.join(tempdir, "ti1", "*.ti1"))]),
		(share_prefix, [os.path.join(tempdir, "LICENSE.txt")]),
		(share_prefix, [os.path.join(tempdir, "README.html")]),
		(share_prefix, [os.path.join(tempdir, "test.cal")])
	]
	for dname in ("16x16", "22x22", "24x24", "32x32", "48x48", "256x256"):
		data_files += [(os.path.join(share_prefix, "theme", "icons", dname), 
			[os.path.join(tempdir, "theme", "icons", dname, fname) for fname in 
			glob.glob(os.path.join(tempdir, "theme", "icons", dname, "*.png"))])]

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
		ext_modules=[RealDisplaySizeMM],
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
