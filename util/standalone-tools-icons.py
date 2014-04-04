#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import with_statement
from glob import glob
from subprocess import call
from tempfile import mkdtemp
import os
import re
import sys


appname = "dispcalGUI"
feeduri = "http://dispcalgui.hoech.net/0install/%s.xml" % appname


def installer(action="install"):
	if action not in ("install", "uninstall"):
		raise ValueError("Invalid action %r" % action)
	root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	if action == "install":
		tmpdir = mkdtemp()
	for desktopfilename in glob(os.path.join(root, "misc", "%s-*.desktop" %
														   appname)):
		desktopbasename = os.path.basename(desktopfilename)
		scriptname = re.sub("\.desktop$", "", desktopbasename)
		if action == "install":
			with open(desktopfilename) as desktopfile:
				contents = desktopfile.read()
			cmd = re.sub("^%s-" % appname, "run-", scriptname)
			for pattern, repl in [("Exec=.+",
								   "Exec=0launch --command=%s -- %s %%f" %
								   (cmd, feeduri))]:
				contents = re.sub(pattern, repl, contents)
			tmpfilename = os.path.join(tmpdir, desktopbasename)
			with open(tmpfilename, "w") as tmpfile:
				tmpfile.write(contents)
			try:
				for size in [16, 22, 24, 32, 48, 256]:
					call(["xdg-icon-resource", action, "--noupdate",
						  "--novendor", "--size", str(size),
						  os.path.join([root, appname, "theme", "icons",
										"%sx%s" % (size, size),
										scriptname + ".png"])])
				call(["xdg-desktop-menu", action, "--noupdate", "--novendor",
						 tmpfilename])
			except EnvironmentError, exception:
				exception.filename = "xdg-desktop-menu"
				raise exception
			finally:
				os.unlink(tmpfilename)
		else:
			for size in [16, 22, 24, 32, 48, 256]:
				call(["xdg-icon-resource", action, "--noupdate",
					  "--size", str(size), scriptname])])
			call(["xdg-desktop-menu", action, "--noupdate", desktopfilename])
	if action == "install":
		try:
			os.rmdir(tmpdir)
		except Exception, exception:
			import warnings
			warnings.warn(exception, Warning)
	call(["xdg-icon-resource", "forceupdate"])
	call(["xdg-desktop-menu", "forceupdate"])


if __name__ == "__main__":
	if len(sys.argv) == 2:
		try:
			installer(sys.argv[1])
		except Exception, exception:
			print exception
	else:
		print "Usage: %s install | uninstall" % os.path.basename(__file__)
