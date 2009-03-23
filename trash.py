#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

if sys.platform == "win32":
	from win32com.shell import shell, shellcon

	def recycle(path):
		retcode, aborted = shell.SHFileOperation((0, 
		   shellcon.FO_DELETE, path, "", shellcon.FOF_ALLOWUNDO | 
		   shellcon.FOF_NOCONFIRMATION | shellcon.FOF_RENAMEONCOLLISION | 
		   shellcon.FOF_SILENT, None, None))
elif sys.platform != "darwin":
	from time import strftime
	from urllib import quote
	import shutil

def trash(paths):
	""" Move files and folders to the trash. If a trashcan facility does not
	exist, simply delete the files/folders. """
	if isinstance(paths, (str, unicode)):
		paths = [paths]
	if not isinstance(paths, list):
		raise TypeError(str(type(paths)) + " is not list")
	if sys.platform == "win32":
		for path in paths:
			path = os.path.abspath(path)
			if not os.path.exists(path):
				raise IOError("No such file or directory: " + path)
			recycle(path)
	else:
		# http://freedesktop.org/wiki/Specifications/trash-spec
		trashroot = os.path.join(os.getenv("XDG_DATA_HOME",
		   os.path.join(os.path.expanduser("~"), ".local", "share")), "Trash")
		trashinfo = os.path.join(trashroot, "info")
		if os.path.isdir(trashroot):
			# modern Linux distros
			trashcan = os.path.join(trashroot, "files")
		else:
			# older Linux distros and Mac OS X
			trashcan = os.path.join(os.path.expanduser("~"), ".Trash")
		for path in paths:
			if os.path.isdir(trashcan):
				n = 1
				dst = os.path.join(trashcan, os.path.basename(path))
				while os.path.exists(dst):
					# avoid name clashes
					n += 1
					dst = os.path.join(trashcan, 
					                   os.path.basename(path) + "." + str(n))
				if os.path.isdir(trashinfo):
					info = open(os.path.join(trashinfo, 
					                         os.path.basename(dst) + 
											 ".trashinfo"), "w")
					info.write("[Trash Info]\n")
					info.write("Path=%s\n" % quote(path.encode(sys.getfilesystemencoding())))
					info.write("DeletionDate=" + 
					           strftime("%Y-%m-%dT%H:%M:%S"))
					info.close()
				shutil.move(path, dst)
			else:
				# if trashcan does not exist, simply delete file/folder
				if os.path.isdir(path) and not os.path.islink(path):
					shutil.rmtree(path)
				else:
					os.remove(path)
