#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, shutil, subprocess as sp, sys, tempfile
from safe_print import safe_print

os.environ['PYTHONPATH'] = os.path.dirname(sys.executable)

pypath = os.path.abspath(sys.argv[0])
pydir = os.path.dirname(pypath)
pyver_str = sys.version.split()[0]
pyver = map(int, pyver_str.split("."))
pyi = "pyinstaller"

# build and install RealDisplaySizeMM if not yet installed
try:
	import RealDisplaySizeMM
except ImportError:
	retcode = sp.call([sys.executable, "setup.py", "install"], cwd = "RealDisplaySizeMM")
	if retcode != 0:
		sys.exit(retcode)

if sys.platform == "darwin": # mac os x

	# check for setuptools
	try:
		import setuptools
	except ImportError:
		# download...
		from ez_setup import use_setuptools
		use_setuptools()
		# ...and install setuptools
		# copy to /tmp to avoid problems with whitespace in the path
		egg = sys.path[0]
		tmp_egg = os.path.join(tempfile.gettempdir(), os.path.basename(egg))
		shutil.copyfile(egg, tmp_egg)
		retcode = sp.call(["sh", tmp_egg])
		os.remove(tmp_egg)
		if retcode != 0:
			sys.exit(retcode)
		try:
			import setuptools
		except ImportError:
			sys.stderr.write("setuptools installation error\n")
			sys.exit(2)

	# check for py2app
	try:
		import py2app
	except ImportError:
		# download and install py2app
		retcode = sp.call(["easy_install", "py2app"])
		if retcode != 0:
			sys.exit(retcode)
		# try:
			# import py2app
		# except ImportError:
			# sys.stderr.write("py2app installation error\n")
			# sys.exit(2)


	# fix missing Python version.plist (Python 2.6, maybe others too)
	version_plist = os.path.sep.join(sys.executable.split(os.path.sep)[:-4] + ["version.plist"])
	if not os.path.exists(version_plist):
		f = file(version_plist, "w")
		f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
		f.write('<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n')
		f.write('<plist version="1.0">\n')
		f.write('<dict>\n')
		f.write('	<key>BuildVersion</key>\n')
		f.write('	<string>1</string>\n')
		f.write('	<key>CFBundleShortVersionString</key>\n')
		f.write('	<string>%s</string>\n' % pyver_str)
		f.write('	<key>CFBundleVersion</key>\n')
		f.write('	<string>%s</string>\n' % pyver_str)
		f.write('	<key>ProjectName</key>\n')
		f.write('	<string>Python</string>\n')
		f.write('	<key>ReleaseStatus</key>\n')
		f.write('	<string>final</string>\n')
		f.write('	<key>SourceVersion</key>\n')
		f.write('	<string>%s</string>\n' % pyver_str)
		f.write('</dict>\n')
		f.write('</plist>')
		f.close()

	# run py2applet
	args = ["py2applet", "--make-setup", "dispcalGUI.py", "lang", "presets", "test.cal", "theme", "ti1", os.path.join("theme", "icons", "dispcalGUI.icns"), "Info.plist"]
	safe_print(*args)
	retcode = sp.call(args)
	if retcode != 0:
		sys.exit(retcode)

	# run py2app
	args = [sys.executable, "setup.py", "py2app", "-O2"]
	safe_print(*args)
	retcode = sp.call(args)
	if retcode != 0:
		sys.exit(retcode)

else: # linux / windows

	dist_dir = os.path.join("dist", "dispcalGUI")

	if not "--copy-only" in sys.argv:

		import platform

		build_loaders = False
		if sys.platform != "win32": # linux
			retcode = sp.call([sys.executable, "Make.py"], cwd = os.path.join(os.path.dirname(sys.argv[0]), pyi, "source", "linux"))
			if retcode != 0:
				sys.exit(retcode)
			retcode = sp.call(["make"], cwd = os.path.join(os.path.dirname(sys.argv[0]), pyi, "source", "linux"))
			if retcode != 0:
				sys.exit(retcode)
		else:
			bootloaders = [
				"inprocsrvr_6dc.dll",
				"inprocsrvr_6dw.dll",
				"inprocsrvr_6rc.dll",
				"inprocsrvr_6rw.dll",
				"inprocsrvr_7dc.dll",
				"inprocsrvr_7dw.dll",
				"inprocsrvr_7rc.dll",
				"inprocsrvr_7rw.dll",
				"run_6dc.exe",
				"run_6dw.exe",
				"run_6rc.exe",
				"run_6rw.exe",
				"run_7dc.exe",
				"run_7dw.exe",
				"run_7rc.exe",
				"run_7rw.exe"
			]
			for bootloader in bootloaders:
				if not os.path.exists(os.path.join(os.path.dirname(sys.argv[0]), pyi, "support", "loader", bootloader)):
					build_loaders = True
					break

		if build_loaders:
			# run SCons to create the bootloaders then configure PyInstaller
			retcode = sp.call([os.path.join(os.path.dirname(sys.argv[0]), pyi, "make-win.cmd"), sys.executable, "x64" if platform.architecture()[0] == "64bit" else "x86"], cwd = os.path.join(os.path.dirname(sys.argv[0]), pyi))
			if retcode != 0:
				sys.exit(retcode)
		else:
			# configure PyInstaller
			retcode = sp.call([sys.executable, "Configure.py"], cwd = os.path.join(os.path.dirname(sys.argv[0]), pyi))
			if retcode != 0:
				sys.exit(retcode)

		if "--makespec" in sys.argv:
			# make spec file. ONLY USE AS TEMPLATE!
			if sys.platform == "win32":
				retcode = sp.call([sys.executable, os.path.join(os.path.dirname(sys.argv[0]), pyi, "Makespec.py"), "-F", "-X", "-o", ".\\", "--icon=" + os.path.join("theme", "icons", "dispcalGUI.ico"), "-v", "winversion.txt", "-n", dist_dir, "dispcalGUI.py"])
			else:
				retcode = sp.call([sys.executable, os.path.join(os.path.dirname(sys.argv[0]), pyi, "Makespec.py"), "-F", "-s", "-X", "-o", "./", "-n", dist_dir, "./dispcalGUI.py"])
			if retcode != 0:
				sys.exit(retcode)

		# build executable
		if sys.platform == "win32":
			retcode = sp.call([sys.executable, os.path.join(os.path.dirname(sys.argv[0]), pyi, "Build.py"), "dispcalGUI-pyi--onefile.spec"])
		else:
			retcode = sp.call([sys.executable, os.path.join(os.path.dirname(sys.argv[0]), pyi, "Build.py"), "./dispcalGUI-pyi--onefile.spec"])
		if retcode != 0:
			sys.exit(retcode)
	
	for basename in ("lang", "screenshots", "theme"):
		if not os.path.exists(os.path.join(dist_dir, basename)):
			shutil.copytree(basename, os.path.join(dist_dir, basename), ignore = shutil.ignore_patterns(*[".svn", "Thumbs.db"] + (["16x16", "22x22", "24x24", "32x32", "48x48", "256x256", "dispcalGUI.icns", "dispcalGUI.ico", "dispcalGUI-install.ico", "header.png", "header-about.png", "*.txt"] + ([] if sys.platform == "win32" else ["dispcalGUI-uninstall.ico"]) if basename == "theme" else [])))
	for basename in ["README.html", "LICENSE.txt"] + (["dispcalGUI.desktop", "install.sh", "uninstall.sh"] if sys.platform != "win32" else []):
		if not os.path.exists(os.path.join(dist_dir, basename)):
			if basename.endswith(".txt"):
				# convert newlines
				src = open(basename, "r")
				tgt = open(os.path.join(dist_dir, basename), "w")
				tgt.write(src.read())
				tgt.close()
				src.close()
			else:
				shutil.copy2(basename, dist_dir)
	if sys.platform != "win32":
		for size in ("16x16", "22x22", "24x24", "32x32", "48x48", "256x256"):
			src = os.path.join("theme", "icons", size)
			dst = os.path.join(dist_dir, src)
			if not os.path.exists(dst):
				os.makedirs(dst)
			if not os.path.exists(os.path.join(dst, "dispcalGUI.png")):
				shutil.copy2(os.path.join(src, "dispcalGUI.png"), os.path.join(dst, "dispcalGUI.png"))
			# if not os.path.exists(os.path.join(dst, "dispcalGUI-uninstall.png")):
				# shutil.copy2(os.path.join(src, "dispcalGUI-uninstall.png"), os.path.join(dst, "dispcalGUI-uninstall.png"))
		# if not os.path.exists(os.path.join(dist_dir, "calibrationloader.sh")):
			# shutil.copy2("calibrationloader.sh", dist_dir)
			# os.chmod(os.path.join(dist_dir, "calibrationloader.sh"), 0755)
	else:
		if hasattr(sys, "version_info") and sys.version_info[:3] == (2,6,1):
			from vc90crt import vc90crt
			for filename in vc90crt.find_files():
				dst = os.path.join(dist_dir, vc90crt.name + ".manifest" if filename.endswith(".manifest") else os.path.basename(filename))
				if not os.path.exists(dst):
					shutil.copy2(filename, dst)
