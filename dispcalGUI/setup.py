# -*- coding: utf-8 -*-

"""
dispcalGUI setup.py script

Can be used with setuptools or pure distutils (the latter can be forced 
with the --use-distutils option, otherwise it will try to use setuptools 
by default).

Also supported in addition to standard distutils/setuptools commands, 
are the bdist_bbfreeze, py2app and py2exe commands (if the appropriate 
packages are installed), which makes this file your all-around building/
bundling powerhouse for dispcalGUI. In the case of py2exe, special care 
is taken of Python 2.6+ and the Microsoft.VC90.CRT assembly dependency, 
so if building an executable on Windows with Python 2.6+ you should 
preferably use py2exe. Please note that bdist_bbfreeze and py2app 
*require* setuptools.

IMPORTANT NOTE:
If called from within the installed package, should only be used to 
uninstall (setup.py uninstall --record=INSTALLED_FILES), otherwise use 
the wrapper script in the root directory of the source tar.gz/zip

"""

from distutils.command.install import install
from distutils.util import change_root, get_platform
import distutils.core
import glob
import os
import platform
import shutil
import subprocess as sp
import sys
from time import strftime
from types import StringType

from defaultpaths import autostart, autostart_home
from meta import (author, author_ascii, description, longdesc, domain, name, 
				  py_maxversion, py_minversion, version, version_tuple, 
				  wx_minversion)
from util_os import relpath

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)
basedir = os.path.dirname(pydir)

msiversion = ".".join((str(version_tuple[0]), 
					   str(version_tuple[1]), 
					   str(version_tuple[2]) + 
					   str(version_tuple[3])))


class Target:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)


def setup():
	bits = platform.architecture()[0][:2]

	print "***", os.path.abspath(sys.argv[0]), " ".join(sys.argv[1:])

	bdist_bbfreeze = "bdist_bbfreeze" in sys.argv[1:]
	bdist_dumb = "bdist_dumb" in sys.argv[1:]
	bdist_win = "bdist_msi" in sys.argv[1:] or "bdist_wininst" in sys.argv[1:]
	debug = 0
	do_full_install = False
	do_install = False
	do_py2app = "py2app" in sys.argv[1:]
	do_py2exe = "py2exe" in sys.argv[1:]
	do_uninstall = "uninstall" in sys.argv[1:]
	doc_layout = "deb" if os.path.exists("/etc/debian_version") else ""
	dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
	help = False
	install_data = None # data files install path (only if given)
	is_rpm_build = "bdist_rpm" in sys.argv[1:] or os.path.abspath(sys.argv[0]).endswith(
		os.path.join(os.path.sep, "rpm", "BUILD", name + "-" + version, 
		os.path.basename(os.path.abspath(sys.argv[0]))))
	prefix = ""
	recordfile_name = None # record installed files to this file
	sdist = "sdist" in sys.argv[1:]
	setuptools = None
	skip_instrument_conf_files = "--skip-instrument-configuration-files" in \
		sys.argv[1:]
	skip_postinstall = "--skip-postinstall" in sys.argv[1:]
	use_distutils = not bdist_bbfreeze and not do_py2app
	use_setuptools = not use_distutils or "--use-setuptools" in \
		sys.argv[1:] or (os.path.exists("use-setuptools") and 
						 not "--use-distutils" in sys.argv[1:])

	sys.path.insert(1, os.path.join(os.path.dirname(pydir), "util"))

	if use_setuptools:
		if "--use-setuptools" in sys.argv[1:] and not \
		   os.path.exists("use-setuptools"):
			open("use-setuptools", "w").close()
		try:
			from ez_setup import use_setuptools as ez_use_setuptools
			ez_use_setuptools()
		except ImportError:
			pass
		try:
			from setuptools import setup, Extension
			setuptools = True
			print "using setuptools"
		except ImportError:
			pass
	else:
		if os.path.exists("use-setuptools"):
			os.remove("use-setuptools")

	if not setuptools:
		from distutils.core import setup, Extension
		print "using distutils"
	
	if do_py2exe:
		import py2exe
		# ModuleFinder can't handle runtime changes to __path__, but win32com 
		# uses them
		try:
			# if this doesn't work, try import modulefinder
			import py2exe.mf as modulefinder
			import win32com
			for p in win32com.__path__[1:]:
				modulefinder.AddPackagePath("win32com", p)
			for extra in ["win32com.shell"]:
				__import__(extra)
				m = sys.modules[extra]
				for p in m.__path__[1:]:
					modulefinder.AddPackagePath(extra, p)
		except ImportError:
			# no build path setup, no worries.
			pass
	
	if do_py2exe:
		origIsSystemDLL = py2exe.build_exe.isSystemDLL
		def isSystemDLL(pathname):
			if os.path.basename(pathname).lower() in ("gdiplus.dll", 
													  "mfc90.dll"):
				return 0
			if os.path.basename(pathname).lower() in ("powrprof.dll", ) or \
			   os.path.basename(pathname).lower().startswith("api-ms-win-"):
				return 1
			return origIsSystemDLL(pathname)
		py2exe.build_exe.isSystemDLL = isSystemDLL

	if do_uninstall:
		i = sys.argv.index("uninstall")
		sys.argv = sys.argv[:i] + ["install"] + sys.argv[i + 1:]
		install.create_home_path = lambda self: None

	if skip_instrument_conf_files:
		i = sys.argv.index("--skip-instrument-configuration-files")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
	
	if skip_postinstall:
		i = sys.argv.index("--skip-postinstall")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]

	if "--use-distutils" in sys.argv[1:]:
		i = sys.argv.index("--use-distutils")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]

	if "--use-setuptools" in sys.argv[1:]:
		i = sys.argv.index("--use-setuptools")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]

	argv = list(sys.argv[1:])
	for i, arg in enumerate(reversed(argv)):
		n = len(sys.argv) - i - 1
		if arg in ("install", "install_lib", "install_headers", 
				   "install_scripts", "install_data"):
			if arg == "install":
				do_full_install = True
			do_install = True
		elif arg == "-d" and len(sys.argv[1:]) > i:
			dist_dir = sys.argv[i + 2]
		else:
			arg = arg.split("=")
			if arg[0] == "--debug":
				debug = 1 if len(arg) == 1 else int(arg[1])
				sys.argv = sys.argv[:n] + sys.argv[n + 1:]
			elif len(arg) == 2:
				if arg[0] == "--dist-dir":
					dist_dir = arg[1]
				elif arg[0] == "--doc-layout":
					doc_layout = arg[1]
					sys.argv = sys.argv[:n] + sys.argv[n + 1:]
				elif arg[0] == "--install-data":
					install_data = arg[1]
				elif arg[0] == "--prefix":
					prefix = arg[1]
				elif arg[0] == "--record":
					recordfile_name = arg[1]
			elif arg[0] == "-h" or arg[0].startswith("--help"):
				help = True

	if not recordfile_name and (do_full_install or do_uninstall):
		recordfile_name = "INSTALLED_FILES"
		# if not do_uninstall:
			# sys.argv.append("--record=" + "INSTALLED_FILES")

	if sys.platform in ("darwin", "win32") or "bdist_egg" in sys.argv[1:]:
		doc = data = "." if do_py2app or do_py2exe or bdist_bbfreeze else name
	else:
		# Linux/Unix
		data = name
		if doc_layout.startswith("deb"):
			doc = os.path.join("doc", name.lower())
		elif "suse" in doc_layout:
			doc = os.path.join("doc", "packages", name)
		else:
			doc = os.path.join("doc", name + "-" + version)
		if not install_data:
			data = os.path.join("share", data)
			doc = os.path.join("share", doc)
			if is_rpm_build:
				doc = os.path.join(os.path.sep, "usr", doc)

	# on Mac OS X and Windows, we want data files in the package dir
	# (package_data will be ignored when using py2exe)
	package_data = {
		name: [
			"argyll_instruments.json",
			"beep.wav",
			"camera_shutter.wav",
			"pnp.ids",
			"lang/*.json",
			"presets/*.icc",
			"quirk.json",
			"ref/*.cie",
			"ref/*.gam",
			"ref/*.icm",
			"ref/*.ti1",
			"report/*.css",
			"report/*.html",
			"report/*.js",
			"theme/*.png",
			"theme/icons/10x10/*.png",
			"theme/icons/16x16/*.png",
			"theme/icons/32x32/*.png",
			"theme/icons/72x72/*.png",
			"ti1/*.ti1",
			"xrc/*.xrc",
			"linear.cal",
			"test.cal"
		] if sys.platform in ("darwin", "win32") and not do_py2app and not 
		do_py2exe else []
	}
	if sdist and sys.platform in ("darwin", "win32"):
		package_data[name] += ["theme/icons/22x22/*.png",
							   "theme/icons/24x24/*.png",
							   "theme/icons/48x48/*.png",
							   "theme/icons/256x256/*.png"]
	if sys.platform == "win32" and not do_py2exe:
		package_data[name] += ["theme/icons/*.ico"]
	# Doc files
	data_files = [
		(os.path.join(doc, "screenshots"), 
			glob.glob(os.path.join(pydir, "..", "screenshots", "*.png"))),
		(os.path.join(doc, "theme"), 
			glob.glob(os.path.join(pydir, "..", "theme", "*.png"))), 
		(os.path.join(doc, "theme"), 
			glob.glob(os.path.join(pydir, "..", "theme", "*.css"))), 
		(os.path.join(doc, "theme"), 
			glob.glob(os.path.join(pydir, "..", "theme", "*.js"))), 
		(os.path.join(doc, "theme", "slimbox2"), 
			glob.glob(os.path.join(pydir, "..", "theme", "slimbox2", "*.css"))), 
		(os.path.join(doc, "theme", "slimbox2"), 
			glob.glob(os.path.join(pydir, "..", "theme", "slimbox2", "*.js"))), 
		(os.path.join(doc, "theme", "icons"), 
			[os.path.join(pydir, "..", "theme", "icons", "favicon.ico")]), 
		(doc, [os.path.join(pydir, "..", "README.html")])
	] if not is_rpm_build or doc_layout.startswith("deb") else []
	if data_files:
		if doc_layout.startswith("deb"):
			data_files.append((doc, [os.path.join(pydir, "..", "dist", 
												  "copyright")]))
			data_files.append((os.path.join(os.path.dirname(data), "doc-base"), 
							   [os.path.join(pydir, "..", "misc", 
											 "dispcalgui-readme")]))
		else:
			data_files.append((doc, [os.path.join(pydir, "..", "LICENSE.txt")]))
	if sys.platform not in ("darwin", "win32") or do_py2app or do_py2exe:
		# Linux/Unix or py2app/py2exe
		data_files += [
			(data, [os.path.join(pydir, "argyll_instruments.json")]),
			(data, [os.path.join(pydir, "beep.wav")]), 
			(data, [os.path.join(pydir, "camera_shutter.wav")]), 
			(data, [os.path.join(pydir, "pnp.ids")]), 
			(data, [os.path.join(pydir, "quirk.json")]), 
			(os.path.join(data, "lang"), 
				glob.glob(os.path.join(pydir, "lang", "*.json"))), 
			(os.path.join(data, "presets"), 
				glob.glob(os.path.join(pydir, "presets", "*.icc"))),
			(os.path.join(data, "ref"), 
				glob.glob(os.path.join(pydir, "ref", "*.cie"))), 
			(os.path.join(data, "ref"), 
				glob.glob(os.path.join(pydir, "ref", "*.gam"))), 
			(os.path.join(data, "ref"), 
				glob.glob(os.path.join(pydir, "ref", "*.icm"))), 
			(os.path.join(data, "ref"), 
				glob.glob(os.path.join(pydir, "ref", "*.ti1"))), 
			(os.path.join(data, "report"), 
				glob.glob(os.path.join(pydir, "report", "*.css"))),
			(os.path.join(data, "report"), 
				glob.glob(os.path.join(pydir, "report", "*.html"))),
			(os.path.join(data, "report"), 
				glob.glob(os.path.join(pydir, "report", "*.js"))),
			(os.path.join(data, "tests"), 
				glob.glob(os.path.join(pydir, "..", "tests", "*.icc"))),
			(os.path.join(data, "theme"), 
				glob.glob(os.path.join(pydir, "theme", "*.png"))), 
			(os.path.join(data, "ti1"), 
				glob.glob(os.path.join(pydir, "ti1", "*.ti1"))), 
			(os.path.join(data, "xrc"), 
				glob.glob(os.path.join(pydir, "xrc", "*.xrc"))),
			(data, [os.path.join(pydir, "linear.cal")]),
			(data, [os.path.join(pydir, "test.cal")])
		]
		if sys.platform == "win32":
			if do_py2exe:
				data_files += [
					(os.path.join(data, "theme", "icons"), 
					 [os.path.join(pydir, "theme", "icons", name + 
					  "-uninstall.ico")]), 
					(os.path.join(data, "lib"), 
					 [sys.executable, sys.executable.replace(".exe", "w.exe")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-3DLUT-maker")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-apply-profiles")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-curve-viewer")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-profile-info")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-synthprofile")]),
					(os.path.join(data, "scripts"), 
					 [os.path.join("scripts", name + "-testchart-editor")])]
			else:
				data_files += [(os.path.join(data, "theme", "icons"), 
					glob.glob(os.path.join(pydir, "theme", 
										   "icons", "*.icns|*.ico")))]
		elif sys.platform != "darwin":
			# Linux
			data_files += [(os.path.join(os.path.dirname(data), 
										 "applications"), 
							[os.path.join(pydir, "..", "misc", name + 
												".desktop")])]
			data_files += [(autostart if os.geteuid() == 0 or prefix.startswith("/")
							else autostart_home, 
							[os.path.join(pydir, "..", "misc", 
										  "z-%s-apply-profiles.desktop" % name)])]
			data_files += [(os.path.join(os.path.dirname(data), "man", "man1"), 
							glob.glob(os.path.join(pydir, "..", "man", "*.1")))]
			if not skip_instrument_conf_files:
				# device configuration / permission stuff
				if is_rpm_build:
					# RPM postinstall script will install these to the correct
					# locations. This allows us compatibility with Argyll
					# packages which may also contain same udev rules / hotplug
					# scripts, thus avoiding file conflicts
					data_files += [(os.path.join(data, "usb"), [os.path.join(
									pydir, "..", "misc", "45-Argyll.rules")])]
					data_files += [(os.path.join(data, "usb"), [os.path.join(
									pydir, "..", "misc", "55-Argyll.rules")])]
					data_files += [(os.path.join(data, "usb"), [os.path.join(
									pydir, "..", "misc", "Argyll")])]
					data_files += [(os.path.join(data, "usb"), [os.path.join(
									pydir, "..", "misc", "Argyll.usermap")])]
				else:
					devconf_files = []
					if os.path.isdir("/etc/udev/rules.d"):
						if glob.glob("/dev/bus/usb/*/*"):
							# USB and serial instruments using udev, where udev 
							# already creates /dev/bus/usb/00X/00X devices
							devconf_files += [
								("/etc/udev/rules.d", [os.path.join(
									pydir, "..", "misc", "55-Argyll.rules")])
							]
						else:
							# USB using udev, where there are NOT /dev/bus/usb/00X/00X 
							# devices
							devconf_files += [
								("/etc/udev/rules.d", [os.path.join(
									pydir, "..", "misc", "45-Argyll.rules")])
							]
					else:
						if os.path.isdir("/etc/hotplug"):
							# USB using hotplug and Serial using udev
							# (older versions of Linux)
							devconf_files += [
								("/etc/hotplug/usb", [os.path.join(pydir, "..", "misc", 
																   fname) for fname in 
													  ["Argyll", "Argyll.usermap"]])
							]
					for entry in devconf_files:
						for fname in entry[1]:
							if os.path.isfile(fname):
								data_files += [(entry[0], [fname])]
		for dname in ("10x10", "16x16", "22x22", "24x24", "32x32", "48x48",
					  "72x72", "256x256"):
			# Only the 10x10, 16x16, 32x32 and 72x72 icons are used exclusively
			# by the app, the other sizes of the app icon are used for the 
			# desktop entry under Linux
			icons = []
			desktopicons = []
			for iconpath in glob.glob(os.path.join(pydir, "theme", "icons", 
												   dname, "*.png")):
				if os.path.basename(iconpath) != name + ".png" or (
					sys.platform in ("darwin", "win32") and 
					dname in ("10x10", "16x16", "32x32", "72x72")):
					icons.append(iconpath)
				elif sys.platform not in ("darwin", "win32"):
					desktopicons.append(iconpath)
			if icons:
				data_files += [(os.path.join(data, "theme", "icons", dname), 
							   icons)]
			if desktopicons:
				data_files += [(os.path.join(os.path.dirname(data), "icons", 
											 "hicolor", dname, "apps"), 
							   desktopicons)]

	sources = [os.path.join(name, "RealDisplaySizeMM.c")]
	if sys.platform == "win32":
		macros = [("NT", None)]
		libraries = ["user32", "gdi32"]
		link_args = None
	elif sys.platform == "darwin":
		macros = [("__APPLE__", None), ("UNIX", None)]
		libraries = None
		link_args = ["-framework Carbon", "-framework CoreFoundation", 
						   "-framework Python", "-framework IOKit"]
		if not help and ("build" in sys.argv[1:] or 
						 "build_ext" in sys.argv[1:] or 
						 (("install" in sys.argv[1:] or 
						   "install_lib" in sys.argv[1:]) and 
						  not "--skip-build" in sys.argv[1:])):
			p = sp.Popen([sys.executable, '-c', '''import os
from distutils.core import setup, Extension

setup(ext_modules=[Extension("%s.RealDisplaySizeMM", sources=%r, 
							 define_macros=%r, extra_link_args=%r)])''' % 
						  (name, sources, macros, link_args)] + sys.argv[1:], 
						 stdout = sp.PIPE, stderr = sp.STDOUT)
			lines = []
			while True:
				o = p.stdout.readline()
				if o == '' and p.poll() != None:
					break
				if o[0:4] == 'gcc ':
					lines += [o]
				print o.rstrip()
			if len(lines):
				os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.3'
				sp.call(lines[-1], shell = True)  # fix the library
	else:
		macros = [("UNIX", None)]
		libraries = ["X11", "Xinerama", "Xrandr", "Xxf86vm"]
		link_args = None
	if sys.platform == "darwin":
		extname = "%s.lib.RealDisplaySizeMM" % name
	else:
		extname = "%s.lib%s.python%s%s.RealDisplaySizeMM" % ((name, bits) + 
															 sys.version_info[:2])
	RealDisplaySizeMM = Extension(extname, 
								  sources=sources, 
								  define_macros=macros, 
								  libraries=libraries,
								  extra_link_args=link_args)
	ext_modules = [RealDisplaySizeMM]

	requires = []
	if not setuptools or sys.platform != "win32":
		# wxPython windows installer doesn't add egg-info entry, so
		# a dependency check from pkg_resources would always fail
		requires += [
			"wxPython (>= %s)" % ".".join(str(n) for n in wx_minversion)
		]
	if sys.platform == "win32":
		requires += [
			"pywin32 (>= 213.0)"
		]

	packages = [name, "%s.lib" % name, "%s.lib.agw" % name]
	if sdist:
		# For source desributions we want all libraries
		for tmpbits in ("32", "64"):
			for pycompat in ("25", "26", "27"):
				packages += ["%s.lib%s" % (name, tmpbits),
							 "%s.lib%s.python%s" % (name, tmpbits, pycompat)]
	elif sys.platform == "darwin":
		# On Mac OS X we only want the universal binary in lib
		pass
	else:
		# On Linux/Windows we want separate libraries
		packages += ["%s.lib%s" % (name, bits),
					 "%s.lib%s.python%s%s" % ((name, bits) + sys.version_info[:2])]
		

	attrs = {
		"author": author_ascii,
		"author_email": "%s@hoech.net" % name,
		"classifiers": [
			"Development Status :: 5 - Production/Stable",
			"Environment :: MacOS X",
			"Environment :: Win32 (MS Windows)",
			"Environment :: X11 Applications",
			"Intended Audience :: End Users/Desktop",
			"License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
			"Operating System :: OS Independent",
			"Programming Language :: Python :: 2.5",
			"Programming Language :: Python :: 2.6",
			"Programming Language :: Python :: 2.7",
			"Topic :: Multimedia :: Graphics",
		],
		"data_files": data_files,
		"description": description,
		"download_url": "http://%(domain)s/"
						"%(name)s-%(version)s.tar.gz" % 
						{"domain": domain, "name": name, "version": version},
		"ext_modules": ext_modules,
		"license": "GPL v3",
		"long_description": longdesc,
		"name": name,
		"packages": packages,
		"package_data": package_data,
		"package_dir": {
			name: name
		},
		"platforms": [
			"Python >= %s <= %s" % (".".join(str(n) for n in py_minversion),
									".".join(str(n) for n in py_maxversion)), 
			"Linux/Unix with X11", 
			"Mac OS X >= 10.4", 
			"Windows 2000 and newer"
		],
		"requires": requires,
		"provides": [name],
		"scripts": [],
		"url": "http://%s/" % domain,
		"version": msiversion if "bdist_msi" in sys.argv[1:] else version
	}

	if setuptools:
		attrs["entry_points"] = {
			"gui_scripts": [
				"%s = %s.%s:main" % (name, name, name),
			]
		}
		attrs["exclude_package_data"] = {
			name: ["RealDisplaySizeMM.c"]
		}
		attrs["include_package_data"] = sys.platform in ("darwin", "win32")
		install_requires = [req.replace("(", "").replace(")", "") for req in 
							requires]
		attrs["install_requires"] = install_requires
		attrs["zip_safe"] = False
	else:
		attrs["scripts"] += [os.path.join("scripts", name)]
		attrs["scripts"] += [os.path.join("scripts", name + "-3DLUT-maker")]
		attrs["scripts"] += [os.path.join("scripts", name + "-curve-viewer")]
		attrs["scripts"] += [os.path.join("scripts", name + "-profile-info")]
		attrs["scripts"] += [os.path.join("scripts", name + "-synthprofile")]
		attrs["scripts"] += [os.path.join("scripts", name + "-testchart-editor")]
	
	if sys.platform != "darwin" and (sys.platform != "win32" or not do_py2exe):
		attrs["scripts"] += [os.path.join("scripts", name + "-apply-profiles")]
	
	if bdist_bbfreeze:
		attrs["setup_requires"] = ["bbfreeze"]

	if "bdist_wininst" in sys.argv[1:]:
		attrs["scripts"] += [os.path.join("util", name + "_postinstall.py")]
		
	if do_py2app:
		reversedomain = domain.split(".")
		reversedomain.reverse()
		reversedomain = ".".join(reversedomain)
		attrs["app"] = [os.path.join(pydir, "main.py")]
		dist_dir = os.path.join(pydir, "..", "dist", 
								"py2app.%s-py%s" % (get_platform(), 
													sys.version[:3]), 
								name + "-" + version)
		excludes = ["test", "Tkconstants", "Tkinter", "tcl"]
		for excludebits in ("32", "64"):
			excludes += ["dispcalGUI.lib%s" % excludebits]
			for pycompat in ("25", "26", "27"):
				excludes += ["lib%s.python%s" % (excludebits, pycompat),
							 "lib%s.python%s.RealDisplaySizeMM" % (excludebits, pycompat)]
		attrs["options"] = {
			"py2app": {
				"argv_emulation": True,
				"dist_dir": dist_dir,
				# numpy.lib.utils imports pydoc, which imports Tkinter, but 
				# numpy.lib.utils is not even used by dispcalGUI, so omit all 
				# Tk stuff
				"excludes": excludes,
				"iconfile": os.path.join(pydir, "theme", "icons", 
										 "dispcalGUI.icns"),
				"optimize": 0,
				"plist": {
					"CFBundleDevelopmentRegion": "English",
					"CFBundleExecutable": name,
					"CFBundleGetInfoString": version,
					"CFBundleIdentifier": reversedomain,
					"CFBundleInfoDictionaryVersion": "6.0",
					"CFBundleLongVersionString": version,
					"CFBundleName": name,
					"CFBundlePackageType": "APPL",
					"CFBundleShortVersionString": version,
					"CFBundleSignature": "????",
					"CFBundleVersion": ".".join(map(str, version_tuple)),
					"NSHumanReadableCopyright": u"© %s %s" % (strftime("%Y"),
															  author)
				}
			}
		}
		attrs["setup_requires"] = ["py2app"]

	if do_py2exe:
		import wx
		from winmanifest_util import getmanifestxml
		manifest_xml = getmanifestxml(os.path.join(pydir, "..", "misc", 
			name + (".exe.VC90.manifest" if hasattr(sys, "version_info") and 
			sys.version_info[:2] >= (2,6) else ".exe.manifest")))
		attrs["windows"] = [Target(**{
			"script": os.path.join(pydir, "..", script),
			"icon_resources": [(1, os.path.join(pydir, "theme", "icons", 
												name + ".ico"))],
			"other_resources": [(24, 1, manifest_xml)],
			"copyright": u"© %s %s" % (strftime("%Y"), author),
			"description": desc
		}) for desc, script in [(name, name + ".pyw"),
								("Profile Loader",
								 os.path.join("scripts",
											  name + "-apply-profiles")),
								("3DLUT Maker",
								 os.path.join("scripts",
											  name + "-3DLUT-maker")),
								("Curve Viewer",
								 os.path.join("scripts",
											  name + "-curve-viewer")),
								("Profile Info",
								 os.path.join("scripts",
											  name + "-profile-info")),
								("Synthetic Profile Creator",
								 os.path.join("scripts",
											  name + "-synthprofile")),
								("Testchart Editor",
								 os.path.join("scripts",
											  name + "-testchart-editor"))]]
		dist_dir = os.path.join(pydir, "..", "dist", "py2exe.%s-py%s" % 
								(get_platform(), sys.version[:3]), name + 
								"-" + version)
		excludes = ["Tkconstants", "Tkinter", "tcl", "dispcalGUI.lib",
					"lib.RealDisplaySizeMM"]
		if bits == "32":
			excludebits = "64"
		else:
			excludebits = "32"
		excludes += ["dispcalGUI.lib%s" % excludebits,
					 "lib%s.RealDisplaySizeMM" % excludebits]
		for pycompat in ("25", "26", "27"):
			excludes += ["lib%s.python%s" % (excludebits, pycompat),
						 "lib%s.python%s.RealDisplaySizeMM" % (excludebits, pycompat)]
		attrs["options"] = {
			"py2exe": {
				"dist_dir": dist_dir,
				"dll_excludes": [
					"iertutil.dll", 
					"msvcm90.dll", 
					"msvcp90.dll", 
					"msvcr90.dll", 
					"mswsock.dll",
					"urlmon.dll",
					"w9xpopen.exe"
				],
				# numpy.lib.utils imports pydoc, which imports Tkinter, but 
				# numpy.lib.utils is not even used by dispcalGUI, so omit all 
				# Tk stuff
				"excludes": excludes, 
				"bundle_files": 3 if wx.VERSION >= (2, 8, 10, 1) else 1,
				"compressed": 1,
				"optimize": 0  # 0 = don’t optimize (generate .pyc)
							   # 1 = normal optimization (like python -O) 
							   # 2 = extra optimization (like python -OO)
			}
		}
		if debug:
			attrs["options"]["py2exe"].update({
				"bundle_files": 3,
				"compressed": 0,
				"optimize": 0,
				"skip_archive": 1
			})
		if setuptools:
			attrs["setup_requires"] = ["py2exe"]
		attrs["zipfile"] = os.path.join("lib", "library.zip")

	if (do_uninstall or do_install or bdist_win or bdist_dumb) and not help:
		distutils.core._setup_stop_after = "commandline"
		dist = setup(**attrs)
		distutils.core._setup_stop_after = None
		cmd = install(dist).get_finalized_command("install")
		if debug > 0:
			for attrname in [
				"base", 
				"data", 
				"headers", 
				"lib", 
				"libbase", 
				"platbase", 
				"platlib", 
				"prefix", 
				"purelib", 
				"root", 
				"scripts", 
				"userbase"
			]:
				if attrname not in ["prefix", "root"]:
					attrname = "install_" + attrname
				if hasattr(cmd, attrname):
					print attrname, getattr(cmd, attrname)
		if debug > 1:
			try:
				from ppdir import ppdir
			except ImportError:
				pass
			else:
				ppdir(cmd, types=[dict, list, str, tuple, type, unicode])
		if not install_data and sys.platform in ("darwin", "win32"):
			# on Mac OS X and Windows, we want data files in the package dir
			data_basedir = cmd.install_lib
		else:
			data_basedir = cmd.install_data
		data = change_root(data_basedir, data)
		doc = change_root(data_basedir, doc)
		# determine in which cases we want to make data file paths relative to 
		# site-packages (on Mac and Windows) and when we want to make them 
		# absolute (Linux)
		linux = sys.platform not in ("darwin", "win32") and (not cmd.root and 
															 setuptools)
		dar_win = (sys.platform in ("darwin", "win32") and 
				   (cmd.root or not setuptools)) or bdist_win
		if not do_uninstall and not install_data and (linux or dar_win) and \
		   attrs["data_files"]:
			if data_basedir.startswith(cmd.install_data + os.path.sep):
				data_basedir = relpath(data_basedir, cmd.install_data)
			print "*** changing basedir for data_files:", data_basedir
			for i, f in enumerate(attrs["data_files"]):
				if type(f) is StringType:
					attrs["data_files"][i] = change_root(data_basedir, f)
				else:
					attrs["data_files"][i] = (change_root(data_basedir, f[0]), 
											  f[1])

	if do_uninstall and not help:

		# Quick and dirty uninstall

		if dry_run:
			print "dry run - nothing will be removed"
		else:
			from postinstall import postuninstall
			# Yeah, yeah - its actually pre-uninstall
			if cmd.root:
				postuninstall(prefix=change_root(cmd.root, cmd.prefix))
			else:
				postuninstall(prefix=cmd.prefix)

		removed = []
		visited = []

		if os.path.exists(recordfile_name):
			paths = [(change_root(cmd.root, line.rstrip("\n")) if cmd.root else 
				line.rstrip("\n")) for line in open(recordfile_name, "r")]
		else:
			paths = []
		if not paths:
			# If the installed files have not been recorded, use some fallback 
			# logic to find them
			paths = glob.glob(os.path.join(cmd.install_scripts, name))
			if sys.platform == "win32":
				if setuptools:
					paths += glob.glob(os.path.join(cmd.install_scripts, 
													name + ".exe"))
					paths += glob.glob(os.path.join(cmd.install_scripts, 
													name + "-script.py"))
				else:
					paths += glob.glob(os.path.join(cmd.install_scripts, 
													name + ".cmd"))
			paths += glob.glob(os.path.join(cmd.install_scripts, name + 
											"_postinstall.py"))
			for attrname in [
				"data", 
				"headers", 
				"lib", 
				"libbase", 
				"platlib", 
				"purelib"
			]:
				path = os.path.join(getattr(cmd, "install_" + attrname), name)
				if not path in paths:
					# Using sys.version in this way is consistent with 
					# setuptools
					paths += glob.glob(path) + glob.glob(path + 
						("-%(version)s-py%(pyversion)s*.egg" % {
							"version": version, 
							"pyversion": sys.version[:3]
						})
					) + glob.glob(path + 
						("-%(version)s-py%(pyversion)s*.egg-info" % {
							"version": version, 
							"pyversion": sys.version[:3]
						})
					)
			if os.path.isabs(data) and not data in paths:
				for fname in [
					"lang",
					"presets",
					"ref",
					"report",
					"screenshots",
					"tests",
					"theme",
					"ti1",
					"LICENSE.txt",
					"README.html",
					"argyll_instruments.json",
					"beep.wav",
					"camera_shutter.wav",
					name + ".desktop",
					"pnp.ids",
					"quirk.json",
					"linear.cal",
					"test.cal"
				]:
					path = os.path.join(data, fname)
					if not path in paths:
						paths += glob.glob(path)
			if os.path.isabs(doc) and not doc in paths:
				for fname in [
					"screenshots",
					"theme",
					"LICENSE.txt",
					"README.html"
				]:
					path = os.path.join(doc, fname)
					if not path in paths:
						paths += glob.glob(path)
			if sys.platform == "win32":
				from postinstall import get_special_folder_path
				startmenu_programs_common = get_special_folder_path(
					"CSIDL_COMMON_PROGRAMS")
				startmenu_programs = get_special_folder_path("CSIDL_PROGRAMS")
				for path in (startmenu_programs_common, startmenu_programs):
					if path:
						for filename in (name, "LICENSE", "README", 
										 "Uninstall"):
							paths += glob.glob(os.path.join(path, name, 
															filename + ".lnk"))

		for path in paths:
			if os.path.exists(path):
				if path in visited:
					continue
				else:
					visited += [path]
				if dry_run:
					print path
					continue
				try:
					if os.path.isfile(path):
						os.remove(path)
					elif os.path.isdir(path):
						os.rmdir(path)
				except Exception, exception:
					print "could'nt remove", path
					print "   ", exception
				else:
					print "removed", path
					removed += [path]
			while path != os.path.dirname(path):
				# remove parent directories if empty
				# could also use os.removedirs(path) but we want some status 
				# info
				path = os.path.dirname(path)
				if os.path.isdir(path):
					if len(os.listdir(path)) == 0:
						if path in visited:
							continue
						else:
							visited += [path]
						if dry_run:
							print path
							continue
						try:
							os.rmdir(path)
						except Exception, exception:
							print "could'nt remove", path
							print "   ", exception
						else:
							print "removed", path
							removed += [path]
					else:
						break

		if not removed:
			print len(visited), "entries found"
		else:
			print len(removed), "entries removed"

	else:

		# To have a working sdist and bdist_rpm when using distutils,
		# we go to the length of generating MANIFEST.in from scratch everytime, 
		# using the information available from setup.
		manifest_in = ["# This file will be re-generated by setup.py - do not"
					   "edit"]
		manifest_in += ["include LICENSE.txt", "include MANIFEST", 
						"include MANIFEST.in", "include README.html", 
						"include %s.pyw" % name, "include use-distutils"]
		manifest_in += ["include " + os.path.basename(sys.argv[0])]
		manifest_in += ["include " + 
						os.path.splitext(os.path.basename(sys.argv[0]))[0] + 
						".cfg"]
		for datadir, datafiles in attrs.get("data_files", []):
			for datafile in datafiles:
				manifest_in += ["include " + (
								relpath(os.path.sep.join(datafile.split("/")), 
										basedir) or datafile)]
		for extmod in attrs.get("ext_modules", []):
			manifest_in += ["include " + os.path.sep.join(src.split("/")) 
							for src in extmod.sources]
		for pkg in attrs.get("packages", []):
			pkg = os.path.join(*pkg.split("."))
			pkgdir = os.path.sep.join(attrs.get("package_dir", 
												{}).get(pkg, pkg).split("/"))
			manifest_in += ["include " + os.path.join(pkgdir, "*.py")]
			manifest_in += ["include " + os.path.join(pkgdir, "*.so")]
			for obj in attrs.get("package_data", {}).get(pkg, []):
				manifest_in += ["include " + os.path.sep.join([pkgdir] + 
															  obj.split("/"))]
		for pymod in attrs.get("py_modules", []):
			manifest_in += ["include " + os.path.join(*pymod.split("."))]
		manifest_in += ["include " + 
						os.path.join(name, "theme", "theme-info.txt")]
		manifest_in += ["recursive-include %s %s %s" % 
						(os.path.join(name, "theme", "icons"), 
						"*.icns", "*.ico")]
		manifest_in += ["recursive-include %s %s" % ("autopackage", "*")]
		manifest_in += ["include " + os.path.join("man", "*.1")]
		manifest_in += ["recursive-include %s %s" % ("misc", "*")]
		if skip_instrument_conf_files:
			manifest_in += [
				"exclude misc/Argyll",
				"exclude misc/*.rules",
				"exclude misc/*.usermap",
			]
		manifest_in += ["include " + os.path.join("screenshots", "*.png")]
		manifest_in += ["include " + os.path.join("scripts", "*")]
		manifest_in += ["include " + os.path.join("tests", "*")]
		manifest_in += ["recursive-include %s %s" % ("theme", "*")]
		manifest_in += ["recursive-include %s %s" % ("util", 
													 "*.cmd *.py *.sh")]
		if sys.platform == "win32" and not setuptools:
			# Only needed under Windows
			manifest_in += ["global-exclude .svn/*"]
		manifest_in += ["global-exclude *~"]
		manifest_in += ["global-exclude *.backup"]
		manifest_in += ["global-exclude *.bak"]
		if not dry_run:
			manifest = open("MANIFEST.in", "w")
			manifest.write("\n".join(manifest_in))
			manifest.close()
			if os.path.exists("MANIFEST"):
				os.remove("MANIFEST")

		if bdist_bbfreeze:
			i = sys.argv.index("bdist_bbfreeze")
			if not "-d" in sys.argv[i + 1:] and \
			   not "--dist-dir" in sys.argv[i + 1:]:
				dist_dir = os.path.join(pydir, "..", "dist", 
										"bbfreeze.%s-py%s" % (get_platform(), 
															  sys.version[:3]))
				sys.argv.insert(i + 1, "--dist-dir=" + dist_dir)
			if not "egg_info" in sys.argv[1:i]:
				sys.argv.insert(i, "egg_info")

		if do_py2app or do_py2exe:
			sys.path.insert(1, pydir)
			i = sys.argv.index("py2app" if do_py2app else "py2exe")
			if not "build_ext" in sys.argv[1:i]:
				sys.argv.insert(i, "build_ext")
			if len(sys.argv) < i + 2 or sys.argv[i + 1] not in ("--inplace", 
																"-i"):
				sys.argv.insert(i + 1, "-i")

		setup(**attrs)
		
		if dry_run or help:
			return
		
		if do_py2app:
			# Create ref, tests, ReadMe and license symlinks in directory
			# containing the app bundle
			os.symlink(os.path.join("dispcalGUI.app", "Contents", "Resources",
									"ref"), os.path.join(dist_dir, "ref"))
			os.symlink(os.path.join("dispcalGUI.app", "Contents", "Resources",
									"tests"), os.path.join(dist_dir, "tests"))
			os.symlink(os.path.join("dispcalGUI.app", "Contents", "Resources",
									"README.html"), os.path.join(dist_dir,
																 "README.html"))
			os.symlink(os.path.join("dispcalGUI.app", "Contents", "Resources",
									"LICENSE.txt"), os.path.join(dist_dir,
																 "LICENSE.txt"))
		
		if do_py2exe:
			shutil.copy(os.path.join(dist_dir, "python26.dll"),
						os.path.join(dist_dir, "lib", "python26.dll"))

		if ((bdist_bbfreeze and sys.platform == "win32") or do_py2exe) and \
		   sys.version_info[:2] >= (2,6):
			from vc90crt import name as vc90crt_name, vc90crt_copy_files
			if do_py2exe:
				vc90crt_copy_files(dist_dir)
				vc90crt_copy_files(os.path.join(dist_dir, 
												"lib"))
			else:
				vc90crt_copy_files(os.path.join(dist_dir, 
												name + "-" + version))
		
		if do_full_install and not is_rpm_build and not skip_postinstall:
			from postinstall import postinstall
			if sys.platform == "win32":
				path = os.path.join(cmd.install_lib, name)
				# Using sys.version in this way is consistent with setuptools
				for path in glob.glob(path) + glob.glob(
					os.path.join(path + (
						"-%(version)s-py%(pyversion)s*.egg" % 
						{
							"version": version, 
							"pyversion": sys.version[:3]
						}
					), name)
				):
					if cmd.root:
						postinstall(prefix=change_root(cmd.root, path))
					else:
						postinstall(prefix=path)
						
			elif cmd.root:
				postinstall(prefix=change_root(cmd.root, cmd.prefix))
			else:
				postinstall(prefix=cmd.prefix)

if __name__ == "__main__":
	setup()
