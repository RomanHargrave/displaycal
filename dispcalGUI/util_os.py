#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import os
import re
import sys

if sys.platform == "darwin":
    enc = "UTF-8"
else:
    enc = sys.stdout.encoding or locale.getpreferredencoding() or "ASCII"
fs_enc = sys.getfilesystemencoding() or enc

def quote_args(args):
	""" Quote commandline arguments where needed """
	args_out = []
	for arg in args:
		if re.search("[\^!$%&()[\]\s]", arg):
			arg = '"' + arg + '"'
		args_out += [arg]
	return args_out


def expanduseru(path):
	""" Unicode version of os.path.expanduser """
	return unicode(os.path.expanduser(path), fs_enc)


def expandvarsu(path):
	""" Unicode version of os.path.expandvars """
	return unicode(os.path.expandvars(path), fs_enc)


def getenvu(key, default = None):
	""" Unicode version of os.getenv """
	var = os.getenv(key, default)
	return var if isinstance(var, unicode) else unicode(var, fs_enc)


def get_sudo():
	""" Return the full path of the 'sudo' executable """
	# for executable in ["gnomesu", "kdesu", "gksu", "sudo"]:
		# if which(executable):
			# return executable
	return which("sudo")


def listdir_re(path, rex = None):
	""" Filter directory contents through a regular expression """
	files = os.listdir(path)
	if rex:
		rex = re.compile(rex, re.IGNORECASE)
		files = filter(rex.search, files)
	return files


def putenvu(key, value):
	""" Unicode version of os.putenv (also correctly updates os.environ) """
	os.environ[key] = value.encode(fs_enc)


def relpath(path, start):
	""" Return a relative version of a path """
	path = os.path.abspath(path).split(os.path.sep)
	start = os.path.abspath(start).split(os.path.sep)
	if path == start:
		return "."
	elif path[:len(start)] == start:
		return os.path.sep.join(path[len(start):])
	elif start[:len(path)] == path:
		return os.path.sep.join([".."] * (len(start) - len(path)))


def which(executable, paths = None):
	""" Return the full path of executable """
	if not paths:
		paths = getenvu("PATH", os.defpath).split(os.pathsep)
	for cur_dir in paths:
		filename = os.path.join(cur_dir, executable)
		if os.path.isfile(filename):
			try:
				if os.access(filename, os.X_OK):
					return filename
			except Exception, exception:
				pass
	return None
