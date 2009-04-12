#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup, Extension
from distutils.sysconfig import get_python_lib
import os
import re
from subprocess import call
import sys

def listdir(path, rex = None):
	files = os.listdir(path)
	if rex:
		rex = re.compile(rex, re.IGNORECASE)
		files = filter(rex.search, files)
	return files

name = "dispcalGUI"
version = "0.2.2b"
desc = "A graphical user interface for the Argyll CMS display calibration utilities"
requires = ["demjson (>= 0.3)", "wxPython (>= 2.8.7)"]
pkg_prefix = os.path.join(get_python_lib(), name)

if "uninstall" in sys.argv[1:]:
	# quick and dirty uninstall
	import shutil
	shutil.rmtree(pkg_prefix, True)
	files_to_remove = [
		os.path.join(get_python_lib(), "%(name)s-%(version)s-py%(pyver)s.egg-info" % 
			{"name": name, "version": version, "pyver": ".".join(map(str, sys.version_info[:2]))})
	]
	if sys.platform == "win32":
		files_to_remove += [
			os.path.join(sys.prefix, "Scripts", name),
			os.path.join(sys.prefix, "Scripts", name + ".cmd")
		]
	else:
		# Linux/Unix and Mac OS X
		files_to_remove += [os.path.join(sys.prefix, "bin", name)]
	for path in files_to_remove:
		if os.path.exists(path):
			try:
				os.remove(path)
			except Exception, exception:
				print exception
else:
	if sys.platform == "win32":
		requires += ["SendKeys (>= 0.3)", "pywin32 (>= 213.0)"]
	elif sys.platform == "darwin":
		requires += ["appscript (>= 0.19)"]
	else:
		pass

	if not '--help' in sys.argv[1:] and not '--help-commands' in sys.argv[1:]:
		call([sys.executable, "setup.py"] + sys.argv[1:] + 
			(["--install-platlib=%s" % pkg_prefix] if "install" in sys.argv[1:] or 
			"install_lib" in sys.argv[1:] else []), 
			cwd = os.path.join(os.path.dirname(__file__), "RealDisplaySizeMM"))
		try:
			import demjson
		except ImportError:
			call([sys.executable, "setup.py"] + sys.argv[1:], 
				cwd = os.path.join(os.path.dirname(__file__), "demjson"))

	data_files = [
		(os.path.join(pkg_prefix, "lang"), 
			[os.path.join("lang", fname) for fname in 
			listdir("lang", ".+\.json")]), 
		(os.path.join(pkg_prefix, "presets"), 
			[os.path.join("presets", fname) for fname in 
			listdir("presets", ".+\.icc")]), 
		(os.path.join(pkg_prefix, "screenshots"), 
			[os.path.join("screenshots", fname) for fname in 
			listdir("screenshots", ".+\.png")]),
		(os.path.join(pkg_prefix, "theme"), 
			[os.path.join("theme", fname) for fname in 
			listdir("theme", ".+\.png")]), 
		(os.path.join(pkg_prefix, "theme", "icons"), 
			[os.path.join("theme", "icons", fname) for fname in 
			listdir(os.path.join("theme", "icons"), ".+\.(icns|ico)")]), 
		(os.path.join(pkg_prefix, "ti1"), 
			[os.path.join("ti1", fname) for fname in listdir("ti1", ".+\.ti1")]),
		(pkg_prefix, ["LICENSE.txt"]),
		(pkg_prefix, ["README.html"]),
		(pkg_prefix, ["test.cal"])
	]
	for dname in ("16x16", "22x22", "24x24", "32x32", "48x48", "256x256"):
		data_files += [(os.path.join(pkg_prefix, "theme", "icons", dname), 
			[os.path.join("theme", "icons", dname, fname) for fname in 
			listdir(os.path.join("theme", "icons", dname), ".+\.png")])]

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
		# extra_path=name,
		license="GPL v3",
		long_description=desc,
		name=name,
		# package_data={name: [
			# "lang/*.json",
			# "presets/*.icc",
			# # "screenshots/*",
			# "theme/*",
			# "ti1/*.ti1",
			# "test.cal"
		# ]},
		package_dir={name: ""},
		#packages=[name],
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
		version=version
	)