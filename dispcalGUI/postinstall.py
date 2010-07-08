#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import call
from os.path import splitext
import os
import shutil
import sys
import traceback

from meta import name
from util_os import relpath, which

recordfile_name = "INSTALLED_FILES"

if sys.platform == "win32":
	try:
		create_shortcut
		# this function is only available within bdist_wininst installers
	except NameError:
		try:
			from pythoncom import (CoCreateInstance, CLSCTX_INPROC_SERVER, 
								   IID_IPersistFile)
			from win32com.shell import shell
			import win32con
		except ImportError:
			def create_shortcut(*args):
				pass
		else:
			def create_shortcut(*args):
				shortcut = CoCreateInstance(
					shell.CLSID_ShellLink, None,
					CLSCTX_INPROC_SERVER, shell.IID_IShellLink
				)
				shortcut.SetPath(args[0])
				shortcut.SetDescription(args[1])
				if len(args) > 3:
					shortcut.SetArguments(args[3])
				if len(args) > 4:
					shortcut.SetWorkingDirectory(args[4])
				if len(args) > 5:
					shortcut.SetIconLocation(args[5], 
											 args[6] if len(args) > 6 else 0)
				shortcut.SetShowCmd(win32con.SW_SHOWNORMAL)
				shortcut.QueryInterface(IID_IPersistFile).Save(args[2], 0)
	try:
		directory_created
		# this function is only available within bdist_wininst installers
	except NameError:
		def directory_created(path):
			pass
	try:
		file_created
		# this function is only available within bdist_wininst installers
	except NameError:
		try:
			import win32api
		except ImportError:
			def file_created(path):
				pass
		else:
			def file_created(path):
				if os.path.exists(recordfile_name):
					installed_files = []
					if os.path.exists(recordfile_name):
						recordfile = open(recordfile_name, "r")
						installed_files += [line.rstrip("\n") for line in 
											recordfile]
						recordfile.close()
					try:
						path.decode("ASCII")
					except (UnicodeDecodeError, UnicodeEncodeError):
						# the contents of the record file used by distutils 
						# must be ASCII GetShortPathName allows us to avoid 
						# any issues with encoding because it returns the 
						# short path as 7-bit string (while still being a 
						# valid path)
						path = win32api.GetShortPathName(path)
					installed_files += [path]
					recordfile = open(recordfile_name, "w")
					recordfile.write("\n".join(installed_files))
					recordfile.close()
	try:
		get_special_folder_path
		# this function is only available within bdist_wininst installers
	except NameError:
		try:
			from win32com.shell import shell, shellcon
		except ImportError:
			def get_special_folder_path(csidl_string):
				pass
		else:
			def get_special_folder_path(csidl_string):
				return shell.SHGetSpecialFolderPath(0, getattr(shellcon, 
															   csidl_string))

def postinstall(prefix=None):
	if sys.platform == "darwin":
		# TODO: implement
		pass
	elif sys.platform == "win32":
		if prefix is None:
			# assume we are running from bdist_wininst installer
			import dispcalGUI
			modpath = os.path.dirname(os.path.abspath(dispcalGUI.__file__))
		else:
			# assume we are running from source dir,
			# or from install dir
			modpath = prefix
		if os.path.exists(modpath):
			icon = os.path.join(modpath, "theme", "icons", name + ".ico")
			if os.path.exists(icon):
				try:
					startmenu_programs_common = get_special_folder_path(
						"CSIDL_COMMON_PROGRAMS")
					startmenu_programs = get_special_folder_path(
						"CSIDL_PROGRAMS")
					startmenu_common = get_special_folder_path(
						"CSIDL_COMMON_STARTMENU")
					startmenu = get_special_folder_path("CSIDL_STARTMENU")
				except OSError, exception:
					traceback.print_exc()
					return
				else:
					for path in (startmenu_programs_common, 
								 startmenu_programs):
						if path:
							grppath = os.path.join(path, name)
							if not os.path.exists(grppath):
								try:
									os.makedirs(grppath)
								except Exception, exception:
									# maybe insufficient privileges?
									traceback.print_exc()
									continue
							directory_created(grppath)
							for filename in (name + ".py", "LICENSE.txt", 
											 "README.html", "Uninstall"):
								lnkpath = os.path.join(
									grppath, splitext(filename)[0] + ".lnk")
								if os.path.exists(lnkpath):
									try:
										os.remove(lnkpath)
									except Exception, exception:
										# maybe insufficient privileges?
										traceback.print_exc()
										continue
								if not os.path.exists(lnkpath):
									if filename != "Uninstall":
										tgtpath = os.path.join(modpath, 
															   filename)
									try:
										if filename == "Uninstall":
											uninstaller = os.path.join(
												sys.prefix, "Remove%s.exe" % 
												name)
											if os.path.exists(uninstaller):
												create_shortcut(
													uninstaller, 
													splitext(filename)[0], 
													lnkpath, 
													'-u "%s-wininst.log"' % 
													os.path.join(sys.prefix, 
																 name), 
													sys.prefix, 
													os.path.join(
														modpath, "theme", 
														"icons", name + 
														"-uninstall.ico"))
											else:
												create_shortcut(
													sys.executable, 
													splitext(filename)[0], 
													lnkpath, 
													'"%s" uninstall '
													'--record="%s"' % (
														os.path.join(
															modpath, 
															"setup.py"), 
														os.path.join(
															modpath, 
															"INSTALLED_FILES")
													), 
													sys.prefix, 
													os.path.join(
														modpath, "theme", 
														"icons", name + 
														"-uninstall.ico"))
										elif filename.endswith(".py"):
											create_shortcut(
												sys.executable, 
												splitext(filename)[0], 
												lnkpath, '"%s"' % tgtpath, 
												modpath, icon)
										else:
											create_shortcut(
												tgtpath, 
												splitext(filename)[0], 
												lnkpath, "", modpath)
									except Exception, exception:
										# maybe insufficient privileges?
										traceback.print_exc()
										continue
									if path == startmenu_programs:
										group = relpath(grppath, startmenu)
									else:
										group = relpath(grppath, 
														startmenu_common)
									print ("Installed start menu entry '%s' to "
										  "%s") % (splitext(filename)[0], 
												  (unicode(group, "MBCS", 
														   "replace") if 
												   type(group) != unicode else 
												   group).encode("MBCS", 
																 "replace"))
								file_created(lnkpath)
							break
			else:
				print "warning - '%s' not found" % icon.encode("MBCS", 
															   "replace")
			if os.path.exists(recordfile_name):
				irecordfile_name = os.path.join(modpath, "INSTALLED_FILES")
				irecordfile = open(irecordfile_name, "w")
				irecordfile.close()
				file_created(irecordfile_name)
				shutil.copy2(recordfile_name, irecordfile_name)
		else:
			print "warning - '%s' not found" % modpath.encode("MBCS", 
															  "replace")
	else:
		# Linux/Unix
		if prefix is None:
			prefix = sys.prefix
		if which("xdg-icon-resource"):
			##print "installing icon resources..."
			##for size in [16, 22, 24, 32, 48, 256]:
				##call(["xdg-icon-resource", "install", "--noupdate", "--novendor", 
					  ##"--size", str(size), prefix + 
					  ##("/share/%s/theme/icons/%sx%s/%s.png" % (name, size, size, 
					   ##name))])
			call(["xdg-icon-resource", "forceupdate"])
		if which("xdg-desktop-menu"):
			##print "installing desktop menu entry..."
			##call(["xdg-desktop-menu", "install", "--novendor", (prefix + 
				  ##"/share/%s/%s.desktop" % (name, name))])
			call(["xdg-desktop-menu", "forceupdate"])


def postuninstall(prefix=None):
	if sys.platform == "darwin":
		# TODO: implement
		pass
	elif sys.platform == "win32":
		# nothing to do
		pass
	else:
		# Linux/Unix
		if prefix is None:
			prefix = sys.prefix
		if which("xdg-desktop-menu"):
			##print "uninstalling desktop menu entry..."
			##call(["xdg-desktop-menu", "uninstall", prefix + 
				  ##("/share/applications/%s.desktop" % name)])
			call(["xdg-desktop-menu", "forceupdate"])
		if which("xdg-icon-resource"):
			##print "uninstalling icon resources..."
			##for size in [16, 22, 24, 32, 48, 256]:
				##call(["xdg-icon-resource", "uninstall", "--noupdate", "--size", 
					  ##str(size), name])
			call(["xdg-icon-resource", "forceupdate"])


def main():
	prefix = None
	for arg in sys.argv[1:]:
		arg = arg.split("=")
		if len(arg) == 2:
			if arg[0] == "--prefix":
				prefix = arg[1]
	try:
		if "-remove" in sys.argv[1:]:
			postuninstall(prefix)
		else:
			postinstall(prefix)
	except Exception, exception:
		traceback.print_exc()

if __name__ == "__main__":
	main()
