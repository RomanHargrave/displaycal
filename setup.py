#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import shutil26 as shutil
import sys
import tempfile

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
prefix_root = sys.prefix.split(os.path.sep)[0] + os.path.sep
root = prefix_root
exec_prefix = None
scripts = None
python_lib = None
site_pkgs = None
data = None

for arg in sys.argv[1:]:
	if arg in ("-n", "--dry-run"):
		dry_run = True
	elif arg.startswith("--exec-prefix") or arg.startswith("--home"):
		opt, arg = arg.split("=")
		exec_prefix = arg
	elif arg.startswith("--root"):
		opt, arg = arg.split("=")
		root = arg
	elif arg.startswith("--install-lib") or arg.startswith("--install-platlib"):
		opt, arg = arg.split("=")
		site_pkgs = arg
	elif arg.startswith("--install-scripts"):
		opt, arg = arg.split("=")
		scripts = arg
	elif arg.startswith("--install-data"):
		opt, arg = arg.split("=")
		data = arg

if not exec_prefix:
	if sys.platform == "win32":
		if root != prefix_root:
			exec_prefix = os.path.join(root, 
			"Python" + sys.version[0] + sys.version[2])
			# using sys.version in this way is consistent with setuptools
		elif "--user" in sys.argv[1:]:
			exec_prefix = os.path.join(os.getenv("APPDATA"), "Python")
		else:
			exec_prefix = sys.exec_prefix
	elif sys.platform == "darwin" and root == prefix_root and not "--user" in sys.argv[1:]:
		exec_prefix = sys.exec_prefix
	else:
		# Linux/Unix (and Mac OS X when using --root or --user)
		if root != prefix_root:
			exec_prefix = os.path.join(root, "usr", "local")
		elif "--user" in sys.argv[1:]:
			exec_prefix = os.path.join(os.path.expanduser("~"), ".local")
		else:
			exec_prefix = sys.exec_prefix

if not scripts:
	if sys.platform == "win32":
		scripts = os.path.join(exec_prefix, "Scripts")
	else:
		# Linux/Unix and Mac OS X
		scripts = os.path.join(exec_prefix, "bin")

if sys.platform == "win32":
	if root == prefix_root and "--user" in sys.argv[1:]:
		python_lib = os.path.join(exec_prefix, 
			"Python" + sys.version[0] + sys.version[2])
			# using sys.version in this way is consistent with setuptools
	else:
		python_lib = os.path.join(exec_prefix, "Lib")
else:
	# Linux/Unix and Mac OS X
	python_lib = os.path.join(exec_prefix, "lib", "python" + sys.version[:3])
	# using sys.version in this way is consistent with setuptools

if not site_pkgs:
	site_pkgs = os.path.join(python_lib, "site-packages")

pkg = os.path.join(site_pkgs, name)

if sys.platform == "win32":
	if root == prefix_root and ("--user" in sys.argv[1:] or exec_prefix != sys.exec_prefix or (site_pkgs and 
		site_pkgs != os.path.join(exec_prefix, "Lib", "site-packages"))):
		if not data:
			data = os.path.join(os.getenv("APPDATA"), name)
	else:
		if not data:
			if root != prefix_root:
				data = os.path.join("Lib", "site-packages", name)
			else:
				data = os.path.join(site_pkgs, name)
	doc = data # install doc files to data dir
elif sys.platform == "darwin" and root == prefix_root and not "--user" in sys.argv[1:]:
	if not data:
		data = os.path.join(site_pkgs, name)
	doc = data # install doc files to data dir
else:
	if "--user" in sys.argv[1:]: # also Mac OS X
		XDG_DATA_HOME = os.getenv("XDG_DATA_HOME",
			os.path.join(os.path.expanduser("~"), ".local", "share"))
		if not data:
			data = os.path.join(XDG_DATA_HOME, name)
		doc = os.path.join(XDG_DATA_HOME, "doc", name)
	else:
		XDG_DATA_DIRS = os.getenv(
			"XDG_DATA_DIRS", 
			os.pathsep.join(
				(
					os.path.join(os.path.sep, "usr", "local", "share"), 
					os.path.join(os.path.sep, "usr", "share")
				)
			)
		).split(os.pathsep)
		if not data:
			data = os.path.join(XDG_DATA_DIRS[0], name)
		doc = os.path.join(XDG_DATA_DIRS[0], "doc", name)

print "root:", root
print "exec_prefix:", exec_prefix
print "scripts:", scripts
print "pkg:", pkg
print "data:", data
print "doc:", doc

if "uninstall" in sys.argv[1:]:

	# quick and dirty uninstall

	if dry_run:
		print "dry run - nothing will be removed"
	
	removed = []
	
	paths = glob.glob(pkg) + glob.glob(pkg + "-%(version)s-py%(pyver)s*.egg" % 
		{
			"version": version, 
			"pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
		}
	) + glob.glob(pkg + "-%(version)s-py%(pyver)s*.egg-info" % 
		{
			"version": version, 
			"pyver": sys.version[:3] # using sys.version in this way is consistent with setuptools
		}
	) + [os.path.join(scripts, name)]
	if sys.platform == "win32":
		paths += [os.path.join(scripts, name + ".cmd")]
	if data != pkg:
		paths += [os.path.join(data, fname) for fname in [
				"lang",
				"presets",
				"screenshots",
				"theme",
				"ti1",
				"LICENSE.txt",
				"README.html",
				"test.cal"
			]
		]
	if doc != pkg and doc != data:
		paths += [os.path.join(doc, fname) for fname in [
				"theme",
				"LICENSE.txt",
				"README.html",
				"test.cal"
			]
		]
	for path in paths:
		if os.path.exists(path):
			if dry_run:
				print path
				continue
			print "removing", path
			if os.path.isfile(path):
				os.remove(path)
			elif os.path.isdir(path):
				shutil.rmtree(path, False)
			removed += [path]
		while path != os.path.dirname(path):
			# remove parent directories if empty
			# could also use os.removedirs(path) but we want some status info
			path = os.path.dirname(path)
			if os.path.isdir(path) and len(os.listdir(path)) == 0:
				if dry_run:
					print path
					continue
				print "removing", path
				os.rmdir(path)
				removed += [path]
	
	if not removed:
		print "nothing removed"
	else:
		print len(removed), "entries removed"

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
						shutil.copytree(srcpath, tmppath, 
							ignore=shutil.ignore_patterns(".svn", "Thumbs.db"))
		
		data_files = [
			(os.path.join(data, "lang"), 
				[os.path.join(tempdir, "lang", fname) for fname in 
				glob.glob(os.path.join(tempdir, "lang", "*.json"))]), 
			(os.path.join(data, "presets"), 
				[os.path.join(tempdir, "presets", fname) for fname in 
				glob.glob(os.path.join(tempdir, "presets", "*.icc"))]), 
			(os.path.join(data, "screenshots"), 
				[os.path.join(tempdir, "screenshots", fname) for fname in 
				glob.glob(os.path.join(tempdir, "screenshots", "*.png"))]),
			(os.path.join(data, "theme"), 
				[os.path.join(tempdir, "theme", fname) for fname in 
				glob.glob(os.path.join(tempdir, "theme", "*.png"))]), 
			(os.path.join(data, "theme", "icons"), 
				[os.path.join(tempdir, "theme", "icons", fname) for fname in 
				glob.glob(os.path.join(tempdir, "theme", "icons", "*.icns|*.ico"))]), 
			(os.path.join(data, "ti1"), 
				[os.path.join(tempdir, "ti1", fname) for fname in 
				glob.glob(os.path.join(tempdir, "ti1", "*.ti1"))]),
			(doc, [os.path.join(tempdir, "LICENSE.txt")]),
			(doc, [os.path.join(tempdir, "README.html")]),
			(doc, [os.path.join(tempdir, "test.cal")])
		]
		if doc != data:
			data_files += [
				(os.path.join(doc, "theme"), 
					[os.path.join(tempdir, "theme", "header-readme.png")]), 
				(os.path.join(doc, "theme", "icons"), 
					[os.path.join(tempdir, "theme", "icons", "favicon.ico")]), 
			]
		for dname in ("16x16", "22x22", "24x24", "32x32", "48x48", "256x256"):
			data_files += [(os.path.join(data, "theme", "icons", dname), 
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
