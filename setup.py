#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.util import get_platform
from subprocess import call
from time import gmtime, strftime, timezone
import os
import sys

from dispcalGUI.setup import __doc__
from dispcalGUI.meta import name, domain, version, version_tuple

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)

def create_appdmg():
	retcode = call(["hdiutil", "create", os.path.join(pydir, "dist", "%s-%s.dmg" % (name, version)), "-volname", name, "-fs", "HFS+", "-srcfolder", os.path.join(pydir, "dist", "py2app", name + "-" + version)])
	if retcode != 0:
		sys.exit(retcode)

def setup():

	if sys.platform == "darwin":
		bdist_cmd = "py2app"
	elif sys.platform == "win32":
		bdist_cmd = "py2exe"
	else:
		bdist_cmd = "bdist_bbfreeze"
	if "bdist_standalone" in sys.argv[1:]:
		i = sys.argv.index("bdist_standalone")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
		if not bdist_cmd in sys.argv[1:i]:
			sys.argv.insert(i, bdist_cmd)
	elif "bdist_bbfreeze" in sys.argv[1:]:
		bdist_cmd = "bdist_bbfreeze"
	elif "py2app" in sys.argv[1:]:
		bdist_cmd = "py2app"
	elif "py2exe" in sys.argv[1:]:
		bdist_cmd = "py2exe"

	bdist_appdmg = "bdist_appdmg" in sys.argv[1:]
	bdist_pyi = "bdist_pyi" in sys.argv[1:]
	dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
	inno = "inno" in sys.argv[1:]
	onefile = "-F" in sys.argv[1:] or "--onefile" in sys.argv[1:]
	purge = "purge" in sys.argv[1:]
	purge_dist = "purge_dist" in sys.argv[1:]
	suffix = "onefile" if onefile else "onedir"

	if purge or purge_dist:

		# remove the "build", "dispcalGUI.egg-info" and 
		# "pyinstaller/bincache*" directories and their contents recursively

		import glob
		import shutil

		if dry_run:
			print "dry run - nothing will be removed"

		paths = []
		if purge:
			paths += glob.glob(os.path.join(pydir, "build")) + glob.glob(
			os.path.join(pydir, name + ".egg-info")) + glob.glob(os.path.join(
			pydir, "pyinstaller", "bincache*"))
			sys.argv.remove("purge")
		if purge_dist:
			paths += glob.glob(os.path.join(pydir, "dist"))
			sys.argv.remove("purge_dist")
		for path in paths:
			if os.path.exists(path):
				if dry_run:
					print path
					continue
				try:
					shutil.rmtree(path)
				except Exception, exception:
					print exception
				else:
					print "removed", path
		if len(sys.argv) == 1 or len(sys.argv) == 2 and dry_run:
			return

	if "readme" in sys.argv[1:]:
		readme_template_path = os.path.join(pydir, "misc", "README.template.html")
		readme_template = open(readme_template_path, "rb")
		readme_template_html = readme_template.read()
		readme_template.close()
		for key, val in [
			("DATE", 
				strftime("%Y-%m-%d", gmtime(os.stat(readme_template_path).st_mtime))),
			("TIMESTAMP", 
				strftime("%Y-%m-%dT%H:%M:%S", gmtime(os.stat(readme_template_path).st_mtime)) +
				("+" if timezone < 0 else "-") +
				strftime("%H:%M", gmtime(abs(timezone)))),
			("VERSION", version)
		]:
			readme_template_html = readme_template_html.replace("$" + key, val)
		readme = open(os.path.join(pydir, "README.html"), "rb")
		readme_html = readme.read()
		readme.close()
		if readme_html != readme_template_html:
			readme = open(os.path.join(pydir, "README.html"), "wb")
			readme.write(readme_template_html)
			readme.close()
		sys.argv.remove("readme")
		if len(sys.argv) == 1 or len(sys.argv) == 2 and dry_run:
			return

	if bdist_appdmg:
		i = sys.argv.index("bdist_appdmg")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
		if len(sys.argv) == 1 or len(sys.argv) == 2 and dry_run:
			create_appdmg()
			return

	if bdist_pyi:
		i = sys.argv.index("bdist_pyi")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
		if not "build_ext" in sys.argv[1:i]:
			sys.argv.insert(i, "build_ext")
		if len(sys.argv) < i + 2 or sys.argv[i + 1] not in ("--inplace", "-i"):
			sys.argv.insert(i + 1, "-i")
		if "-F" in sys.argv[1:]:
			sys.argv.remove("-F")
		if "--onefile" in sys.argv[1:]:
			sys.argv.remove("--onefile")

	if inno:
		inno_template_path = os.path.join(pydir, "misc", "%s-Setup-%s.iss" % (name, ("pyi-" + suffix if bdist_pyi else bdist_cmd)))
		inno_template = open(inno_template_path, "r")
		inno_script = inno_template.read().decode("MBCS", "replace") % {
			"AppVerName": version,
			"AppPublisherURL": "http://" + domain,
			"AppSupportURL": "http://" + domain,
			"AppUpdatesURL": "http://" + domain,
			"VersionInfoVersion": ".".join(map(str, version_tuple)),
			"VersionInfoTextVersion": version,
			"AppVersion": version,
			}
		inno_template.close()
		inno_path = os.path.join("dist", os.path.basename(inno_template_path))
		if not os.path.exists("dist"):
			os.makedirs("dist")
		inno_file = open(inno_path, "w")
		inno_file.write(inno_script.encode("MBCS", "replace"))
		inno_file.close()
		sys.argv.remove("inno")
		if len(sys.argv) == 1 or len(sys.argv) == 2 and dry_run:
			return

	from dispcalGUI.setup import setup
	setup()
	
	if bdist_appdmg:
		create_appdmg()

	if bdist_pyi:

		# create an executable using pyinstaller

		if sys.platform != "win32": # Linux/Mac OS X
			retcode = call([sys.executable, "Make.py"], 
				cwd = os.path.join(pydir, "pyinstaller", "source", "linux"))
			if retcode != 0:
				sys.exit(retcode)
			retcode = call(["make"], cwd = os.path.join(pydir, "pyinstaller", 
				"source", "linux"))
			if retcode != 0:
				sys.exit(retcode)
		retcode = call([sys.executable, "-O", os.path.join(pydir, "pyinstaller", 
			"Configure.py")])
		retcode = call([sys.executable, "-O", os.path.join(pydir, "pyinstaller", 
			"Build.py"), "-o", os.path.join(pydir, "build", "pyi.%s-%s" % 
			(get_platform(), suffix), name + "-" + version), os.path.join(pydir, 
			"misc", "%s-pyi-%s.spec" % (name, suffix))])
		if retcode != 0:
			sys.exit(retcode)

if __name__ == "__main__":
	setup()
