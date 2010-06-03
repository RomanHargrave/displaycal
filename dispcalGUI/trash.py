#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

if sys.platform == "win32":
	from win32com.shell import shell, shellcon
	import win32api

	def recycle(path):
		path = os.path.join(win32api.GetShortPathName(os.path.split(path)[0]), 
			os.path.split(path)[1])
		retcode, aborted = shell.SHFileOperation((0, 
		   shellcon.FO_DELETE, path, "", shellcon.FOF_ALLOWUNDO | 
		   shellcon.FOF_NOCONFIRMATION | shellcon.FOF_RENAMEONCOLLISION | 
		   shellcon.FOF_SILENT, None, None))
		return retcode == 0
else:
	from time import strftime
	from urllib import quote
	import shutil

from util_os import getenvu, expanduseru

class TrashcanUnavailableError(Exception):

	def __str__(self):
		return self.args[0]


def trash(paths):
	"""
	Move files and folders to the trash.
	
	If a trashcan facility does not exist, do not touch the files. 
	Return a list of successfully processed paths.
	
	"""
	if isinstance(paths, (str, unicode)):
		paths = [paths]
	if not isinstance(paths, list):
		raise TypeError(str(type(paths)) + " is not list")
	deleted = []
	if sys.platform == "win32":
		for path in paths:
			path = os.path.abspath(path)
			if not os.path.exists(path):
				raise IOError("No such file or directory: " + path)
			if recycle(path):
				deleted += [path]
	else:
		# http://freedesktop.org/wiki/Specifications/trash-spec
		trashroot = os.path.join(getenvu("XDG_DATA_HOME",
		   os.path.join(expanduseru("~"), ".local", "share")), "Trash")
		trashinfo = os.path.join(trashroot, "info")
		if os.path.isdir(trashroot):
			# modern Linux distros
			trashcan = os.path.join(trashroot, "files")
		else:
			# older Linux distros and Mac OS X
			trashcan = os.path.join(expanduseru("~"), ".Trash")
		if not os.path.isdir(trashcan):
			raise TrashcanUnavailableError("Not a directory: '%s'" % trashcan)
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
					info.write("Path=%s\n" % 
							   quote(path.encode(sys.getfilesystemencoding())))
					info.write("DeletionDate=" + 
					           strftime("%Y-%m-%dT%H:%M:%S"))
					info.close()
				shutil.move(path, dst)
			else:
				# if trashcan does not exist, simply delete file/folder?
				pass
				# if os.path.isdir(path) and not os.path.islink(path):
					# shutil.rmtree(path)
				# else:
					# os.remove(path)
			deleted += [path]
	return deleted
