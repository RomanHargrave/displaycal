#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import with_statement
from ConfigParser import RawConfigParser
from distutils.sysconfig import get_python_lib
from distutils.util import change_root, get_platform
from hashlib import md5, sha1
from subprocess import call, Popen
from time import gmtime, strftime, timezone
import codecs
import glob
import math
import os
import re
import shutil
import subprocess as sp
import sys
import time
if sys.platform == "win32":
	import msilib

sys.path.insert(0, "DisplayCAL")

from util_os import fs_enc, which
from util_str import strtr

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)

def create_appdmg(zeroinstall=False):
	if zeroinstall:
		dmgname = name + "-0install"
		srcdir = "0install"
	else:
		dmgname = name + "-" + version
		srcdir = "py2app.%s-py%s" % (get_platform(), sys.version[:3])
	retcode = call(["hdiutil", "create", os.path.join(pydir, "dist", 
													  dmgname + ".dmg"), 
					"-volname", dmgname, "-srcfolder", 
					os.path.join(pydir, "dist", srcdir, dmgname)])
	if retcode != 0:
		sys.exit(retcode)


def replace_placeholders(tmpl_path, out_path, lastmod_time=0, iterable=None):
	global longdesc
	with codecs.open(tmpl_path, "r", "UTF-8") as tmpl:
		tmpl_data = tmpl.read()
	if os.path.basename(tmpl_path).startswith("debian"):
		longdesc_backup = longdesc
		longdesc = "\n".join([" " + (line if line.strip() else ".") 
							  for line in longdesc.splitlines()])
	mapping = {
		"DATE":
			strftime("%a %b %d %Y",  # e.g. Tue Jul 06 2010
					 gmtime(lastmod_time or 
							os.stat(tmpl_path).st_mtime)),
		"DATETIME": strftime("%a %b %d %H:%M:%S UTC %Y",  # e.g. Wed Jul 07 15:25:00 UTC 2010
							  gmtime(lastmod_time or 
									 os.stat(tmpl_path).st_mtime)),
		"DEBPACKAGE": name.lower(),
		"DEBDATETIME": strftime("%a, %d %b %Y %H:%M:%S ",  # e.g. Wed, 07 Jul 2010 15:25:00 +0100
								 gmtime(lastmod_time or 
										os.stat(tmpl_path).st_mtime)) +
								 ("+" if timezone < 0 else "-") +
								 strftime("%H%M", gmtime(abs(timezone))),
		"DOMAIN": domain.lower(),
		"ISODATE": 
			strftime("%Y-%m-%d", 
					 gmtime(lastmod_time or 
							os.stat(tmpl_path).st_mtime)),
		"ISODATETIME": 
			strftime("%Y-%m-%dT%H:%M:%S", 
					 gmtime(lastmod_time or 
							os.stat(tmpl_path).st_mtime)) +
					 ("+" if timezone < 0 else "-") +
					 strftime("%H:%M", gmtime(abs(timezone))),
		"ISOTIME": 
			strftime("%H:%M", 
					 gmtime(lastmod_time or 
							os.stat(tmpl_path).st_mtime)),
		"TIMESTAMP": str(int(lastmod_time)),
		"SUMMARY": description,
		"DESC": longdesc,
		"APPDATADESC": "<p>\n\t\t\t" + longdesc.replace("\n", "\n\t\t\t").replace(".\n", ".\n\t\t</p>\n\t\t<p>\n") + "\n\t\t</p>",
		"APPNAME": name,
		"APPNAME_HTML": name_html,
		"APPNAME_LOWER": name.lower(),
		"AUTHOR": author,
		"AUTHOR_EMAIL": author_email,
		"MAINTAINER": author,
		"MAINTAINER_EMAIL": author_email,
		"MAINTAINER_EMAIL_SHA1": sha1(author_email).hexdigest(),
		"PACKAGE": name,
		"PY_MAXVERSION": ".".join(str(n) for n in py_maxversion),
		"PY_MINVERSION": ".".join(str(n) for n in py_minversion),
		"VERSION": version,
		"VERSION_SHORT": re.sub("(?:\.0){1,2}$", "", version),
		"URL": "http://%s/" % domain.lower(),
		"WX_MINVERSION": ".".join(str(n) for n in wx_minversion),
		"YEAR": strftime("%Y", gmtime())}
	mapping.update(iterable or {})
	for key, val in mapping.iteritems():
		tmpl_data = tmpl_data.replace("${%s}" % key, val)
	if os.path.basename(tmpl_path).startswith("debian"):
		longdesc = longdesc_backup
	if os.path.isfile(out_path):
		with codecs.open(out_path, "r", "UTF-8") as out:
			data = out.read()
		if data == tmpl_data:
			return
	elif not os.path.isdir(os.path.dirname(out_path)):
		os.makedirs(os.path.dirname(out_path))
	with codecs.open(out_path, "w", "UTF-8") as out:
		out.write(tmpl_data)


def svnversion_bump(svnversion):
	print "Bumping version number %s ->" % \
		  ".".join(svnversion),
	svnversion = svnversion_parse(
		str(int("".join(svnversion)) + 1))
	print ".".join(svnversion)
	return svnversion


def svnversion_parse(svnversion):
	svnversion = [n for n in svnversion]
	if len(svnversion) > 4:
		svnversion = ["".join(svnversion[:len(svnversion) - 3])] + \
					 svnversion[len(svnversion) - 3:]
		# e.g. ["1", "1", "2", "5", "0"] -> ["11", "2", "5", "0"]
	elif len(svnversion) < 4:
		svnversion.insert(0, "0")
		# e.g. ["2", "8", "3"] -> ["0", "2", "8", "3"]
	return svnversion


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
	elif "bdist_pyi" in sys.argv[1:]:
		bdist_cmd = "pyi"
	elif "py2app" in sys.argv[1:]:
		bdist_cmd = "py2app"
	elif "py2exe" in sys.argv[1:]:
		bdist_cmd = "py2exe"

	appdata = "appdata" in sys.argv[1:]
	arch = None
	bdist_appdmg = "bdist_appdmg" in sys.argv[1:]
	bdist_deb = "bdist_deb" in sys.argv[1:]
	bdist_lipa = "bdist_lipa" in sys.argv[1:]
	bdist_pyi = "bdist_pyi" in sys.argv[1:]
	buildservice = "buildservice" in sys.argv[1:]
	setup_cfg = None
	dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
	help = False
	inno = "inno" in sys.argv[1:]
	onefile = "-F" in sys.argv[1:] or "--onefile" in sys.argv[1:]
	purge = "purge" in sys.argv[1:]
	purge_dist = "purge_dist" in sys.argv[1:]
	use_setuptools = "--use-setuptools" in sys.argv[1:]
	zeroinstall = "0install" in sys.argv[1:]
	stability = "testing"
	
	argv = list(sys.argv[1:])
	for i, arg in enumerate(reversed(argv)):
		n = len(sys.argv) - i - 1
		arg = arg.split("=")
		if len(arg) == 2:
			if arg[0] == "--force-arch":
				arch = arg[1]
			elif arg[0] in ("--cfg", "--stability"):
				if arg[0] == "--cfg":
					setup_cfg = arg[1]
				else:
					stability = arg[1]
				sys.argv = sys.argv[:n] + sys.argv[n + 1:]
		elif arg[0] == "-h" or arg[0].startswith("--help"):
			help = True
	
	lastmod_time = 0
	
	non_build_args = filter(lambda arg: arg in sys.argv[1:], 
							["bdist_appdmg", "clean", "purge", "purge_dist", 
							 "uninstall", "-h", "--help", "--help-commands", 
							 "--all", "--name", "--fullname", "--author", 
							 "--author-email", "--maintainer", 
							 "--maintainer-email", "--contact", 
							 "--contact-email", "--url", "--license", 
							 "--licence", "--description", 
							 "--long-description", "--platforms", 
							 "--classifiers", "--keywords", "--provides", 
							 "--requires", "--obsoletes", "--quiet", "-q", 
							 "register", "--list-classifiers", "upload",
							 "--use-distutils", "--use-setuptools",
							 "--verbose", "-v", "finalize_msi"])

	if os.path.isdir(os.path.join(pydir, ".svn")) and (which("svn") or
													   which("svn.exe")) and (
	   not sys.argv[1:] or (len(non_build_args) < len(sys.argv[1:]) and 
							not help)):
		print "Trying to get SVN version information..."
		svnversion = None
		try:
			p = Popen(["svnversion"], stdout=sp.PIPE, cwd=pydir)
		except Exception, exception:
			print "...failed:", exception
		else:
			svnversion = p.communicate()[0]
			svnversion = strtr(svnversion.strip().split(":")[-1], "MPS")
			svnbasefilename = os.path.join(pydir, "VERSION_BASE")
			if os.path.isfile(svnbasefilename):
				with open(svnbasefilename) as svnbasefile:
					svnbase = int("".join(svnbasefile.read().strip().split(".")),
								  10)
				svnversion = int(svnversion)
				svnversion += svnbase
			svnversion = svnversion_parse(str(svnversion))
			svnbase = svnversion
		
		print "Trying to get SVN information..."
		mod = False
		lastmod = ""
		entries = []
		args = ["svn", "status", "--xml"]
		while not entries:
			try:
				p = Popen(args, stdout=sp.PIPE, cwd=pydir)
			except Exception, exception:
				print "...failed:", exception
				break
			else:
				from xml.dom import minidom
				xml = p.communicate()[0]
				xml = minidom.parseString(xml)
				entries = xml.getElementsByTagName("entry")
				if not entries:
					if "info" in args:
						break
					args = ["svn", "info", "-R", "--xml"]
		timestamp = None
		for entry in iter(entries):
			pth = entry.getAttribute("path")
			mtime = 0
			if "status" in args:
				status = entry.getElementsByTagName("wc-status")
				item = status[0].getAttribute("item")
				if item.lower() in ("none", "normal"):
					item = " "
				props = status[0].getAttribute("props")
				if props.lower() in ("none", "normal"):
					props = " "
				print item.upper()[0] + props.upper()[0] + " " * 5, pth
				mod = True
				if item.upper()[0] != "D" and os.path.exists(pth):
					mtime = os.stat(pth).st_mtime
					if mtime > lastmod_time:
						lastmod_time = mtime
						timestamp = time.gmtime(mtime)
			schedule = entry.getElementsByTagName("schedule")
			if schedule:
				schedule = schedule[0].firstChild.wholeText.strip()
				if schedule != "normal":
					print schedule.upper()[0] + " " * 6, pth
					mod = True
					mtime = os.stat(pth).st_mtime
					if mtime > lastmod_time:
						lastmod_time = mtime
						timestamp = time.gmtime(mtime)
			lmdate = entry.getElementsByTagName("date")
			if lmdate:
				lmdate = lmdate[0].firstChild.wholeText.strip()
				dateparts = lmdate.split(".")  # split off milliseconds
				mtime = time.mktime(time.strptime(dateparts[0], 
													  "%Y-%m-%dT%H:%M:%S"))
				mtime += float("." + strtr(dateparts[1], "Z"))
				if mtime > lastmod_time:
					lastmod_time = mtime
					timestamp = time.localtime(mtime)
		if timestamp:
			lastmod = strftime("%Y-%m-%dT%H:%M:%S", timestamp) + \
					  str(round(mtime - int(mtime), 6))[1:] + \
					  "Z"
			## print lmdate, lastmod, pth
		
		if not dry_run:
			print "Generating __version__.py"
			versionpy = open(os.path.join(pydir, "DisplayCAL", "__version__.py"), "w")
			versionpy.write("# generated by setup.py\n\n")
			buildtime = time.time()
			versionpy.write("BUILD_DATE = %r\n" % 
							(strftime("%Y-%m-%dT%H:%M:%S", 
									 gmtime(buildtime)) + 
							 str(round(buildtime - int(buildtime), 6))[1:] + 
							 "Z"))
			if lastmod:
				versionpy.write("LASTMOD = %r\n" % lastmod)
			if svnversion:
				if mod:
					svnversion = svnversion_bump(svnversion)
				else:
					print "Version", ".".join(svnversion)
				versionpy.write("VERSION = (%s)\n" % ", ".join(svnversion))
				versionpy.write("VERSION_BASE = (%s)\n" % ", ".join(svnbase))
				versionpy.write("VERSION_STRING = %r\n" % ".".join(svnversion))
				versiontxt = open(os.path.join(pydir, "VERSION"), "w")
				versiontxt.write(".".join(svnversion))
				versiontxt.close()
			versionpy.close()

	if not help and not dry_run:
		# Restore setup.cfg.backup if it exists
		if os.path.isfile(os.path.join(pydir, "setup.cfg.backup")) and \
		   not os.path.isfile(os.path.join(pydir, "setup.cfg")):
			shutil.copy2(os.path.join(pydir, "setup.cfg.backup"), 
						 os.path.join(pydir, "setup.cfg"))
	
	if not sys.argv[1:]:
		return
	
	global name, name_html, author, author_email, description, longdesc
	global domain, py_maxversion, py_minversion
	global version, version_lin, version_mac
	global version_src, version_tuple, version_win
	global wx_minversion
	from meta import (name, name_html, author, author_email, description,
					  lastmod, longdesc, domain, py_maxversion, py_minversion,
					  version, version_lin, version_mac, 
					  version_src, version_tuple, version_win,
					  wx_minversion, script2pywname)

	if not lastmod_time:
		lastmod_time = time.mktime(time.strptime(lastmod,
												 "%Y-%m-%dT%H:%M:%S.%fZ"))

	msiversion = ".".join((str(version_tuple[0]), 
						   str(version_tuple[1]), 
						   str(version_tuple[2]) + 
						   str(version_tuple[3])))

	if not dry_run and not help:
		if setup_cfg or ("bdist_msi" in sys.argv[1:] and use_setuptools):
			if not os.path.exists(os.path.join(pydir, "setup.cfg.backup")):
				shutil.copy2(os.path.join(pydir, "setup.cfg"), 
							 os.path.join(pydir, "setup.cfg.backup"))
		if "bdist_msi" in sys.argv[1:] and use_setuptools:
			# setuptools parses options globally even if they're not under the
			# section of the currently run command
			os.remove(os.path.join(pydir, "setup.cfg"))
		if setup_cfg:
			shutil.copy2(os.path.join(pydir, "misc", "setup.%s.cfg" % setup_cfg), 
						 os.path.join(pydir, "setup.cfg"))

	if purge or purge_dist:

		# remove the "build", "DisplayCAL.egg-info" and 
		# "pyinstaller/bincache*" directories and their contents recursively

		if dry_run:
			print "dry run - nothing will be removed"

		paths = []
		if purge:
			paths += glob.glob(os.path.join(pydir, "build")) + glob.glob(
						os.path.join(pydir, name + ".egg-info")) + glob.glob(
						os.path.join(pydir, "pyinstaller", "bincache*"))
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
		if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
			return

	if "readme" in sys.argv[1:]:
		if not dry_run:
			for suffix in ("", "-fr"):
				replace_placeholders(os.path.join(pydir, "misc", 
												  "README%s.template.html" %
												  suffix),
									 os.path.join(pydir, "README%s.html" %
												  suffix),
									 lastmod_time,
									 {"STABILITY": "Beta" if stability != "stable"
												   else ""})
			replace_placeholders(os.path.join(pydir, "misc", 
											  "history.template.html"),
								 os.path.join(pydir, "history.html"),
								 lastmod_time)
		sys.argv.remove("readme")
		if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
			return

	if ((appdata or 
		 "install" in sys.argv[1:]) and 
		not help and not dry_run):
		from setup import get_scripts
		import localization as lang
		scripts = get_scripts()
		provides = ["<python2>%s</python2>" % name]
		for script, desc in scripts:
			provides.append("<binary>%s</binary>" % script)
		provides = "\n\t\t".join(provides)
		lang.init()
		languages = []
		for code, tdict in lang.ldict.iteritems():
			if code == "en":
				continue
			untranslated = 0
			for key in tdict:
				if key.startswith("*") and key != "*":
					untranslated += 1
			languages.append('<lang percentage="%i">%s</lang>' %
							 (round((1 - untranslated / (len(tdict) - 1.0)) * 100),
							 code))
		languages = "\n\t\t".join(languages)
		tmpl_name = name + ".appdata.xml"
		replace_placeholders(os.path.join(pydir, "misc", tmpl_name),
							 os.path.join(pydir, "dist", tmpl_name),
							 lastmod_time, {"APPDATAPROVIDES": provides,
											"LANGUAGES": languages})
	if appdata:
		sys.argv.remove("appdata")

	if (("sdist" in sys.argv[1:] or 
		 "install" in sys.argv[1:] or 
		 "bdist_deb" in sys.argv[1:]) and 
		not help):
		buildservice = True
	if buildservice and not dry_run:
		replace_placeholders(os.path.join(pydir, "misc", "debian.copyright"),
							 os.path.join(pydir, "dist", "copyright"),
							 lastmod_time)
	if "buildservice" in sys.argv[1:]:
		sys.argv.remove("buildservice")

	if bdist_deb:
		bdist_args = ["bdist_rpm"]
		if not arch:
			arch = get_platform().split("-")[1]
			bdist_args += ["--force-arch=" + arch]
		i = sys.argv.index("bdist_deb")
		sys.argv = sys.argv[:i] + bdist_args + sys.argv[i + 1:]
	
	if bdist_lipa:
		i = sys.argv.index("bdist_lipa")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]

	if bdist_pyi:
		i = sys.argv.index("bdist_pyi")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
		if not "build_ext" in sys.argv[1:i]:
			sys.argv.insert(i, "build_ext")
		if "-F" in sys.argv[1:]:
			sys.argv.remove("-F")
		if "--onefile" in sys.argv[1:]:
			sys.argv.remove("--onefile")

	if inno and sys.platform == "win32":
		for tmpl_type in ("pyi" if bdist_pyi else bdist_cmd, "0install",
						  "0install-per-user"):
			inno_template_path = os.path.join(pydir, "misc", "%s-Setup-%s.iss" % 
											  (name, tmpl_type))
			inno_template = open(inno_template_path, "r")
			inno_script = inno_template.read().decode("UTF-8", "replace") % {
				"AppCopyright": u"© %s %s" % (strftime("%Y"), author),
				"AppName": name,
				"AppVerName": version,
				"AppPublisher": author,
				"AppPublisherURL": "http://" + domain,
				"AppSupportURL": "http://" + domain,
				"AppUpdatesURL": "http://" + domain,
				"VersionInfoVersion": ".".join(map(str, version_tuple)),
				"VersionInfoTextVersion": version,
				"AppVersion": version,
				"Platform": get_platform(),
				"PythonVersion": sys.version[:3],
				"URL": "http://%s/" % domain.lower(),
				}
			inno_template.close()
			inno_path = os.path.join("dist", 
									 os.path.basename(inno_template_path).replace(
										bdist_cmd, "%s.%s-py%s" % 
										(bdist_cmd, get_platform(), 
										 sys.version[:3])))
			if not dry_run:
				if not os.path.exists("dist"):
					os.makedirs("dist")
				inno_file = open(inno_path, "w")
				inno_file.write(inno_script.encode("MBCS", "replace"))
				inno_file.close()
		sys.argv.remove("inno")
		if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
			return
	
	if "finalize_msi" in sys.argv[1:]:
		db = msilib.OpenDatabase(r"dist\%s-%s.win32-py%s.msi" %
								 (name, msiversion, sys.version[:3]), 
								 msilib.MSIDBOPEN_TRANSACT)
		view = db.OpenView("SELECT Value FROM Property WHERE Property = 'ProductCode'")
		view.Execute(None)
		record = view.Fetch()
		productcode = record.GetString(1)
		view.Close()
		msilib.add_data(db, "Directory", [("ProgramMenuFolder",  # Directory
										   "TARGETDIR",  # Parent
										   ".")])  # DefaultDir
		msilib.add_data(db, "Directory", [("MenuDir",  # Directory
										   "ProgramMenuFolder",  # Parent
										   name.upper()[:6] + "~1|" + name)])  # DefaultDir
		msilib.add_data(db, "Icon", [(name + ".ico",  # Name
									  msilib.Binary(os.path.join(pydir, name, 
														"theme", "icons", 
														name + ".ico")))])  # Data
		msilib.add_data(db, "Icon", [("uninstall.ico",  # Name
									  msilib.Binary(os.path.join(pydir, name, 
														"theme", "icons", 
														name + "-uninstall.ico")))])  # Data
		msilib.add_data(db, "RemoveFile", [("MenuDir",  # FileKey
											name,  # Component
											None,  # FileName
											"MenuDir",  # DirProperty
											2)])  # InstallMode
		msilib.add_data(db, "Registry", [("DisplayIcon",  # Registry
										  -1,  # Root
										  r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" % 
										  productcode,  # Key
										  "DisplayIcon",  # Name
										  r"[icons]%s.ico" % name,  # Value
										  name)])  # Component
		msilib.add_data(db, "Shortcut", [(name,  # Shortcut
										  "MenuDir",  # Directory
										  name.upper()[:6] + "~1|" + name,  # Name
										  name,  # Component
										  r"[TARGETDIR]pythonw.exe",  # Target
										  r'"[TARGETDIR]Scripts\%s"' % name,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  name + ".ico",  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  name)])  # WkDir
		msilib.add_data(db, "Shortcut", [("LICENSE",  # Shortcut
										  "MenuDir",  # Directory
										  "LICENSE|LICENSE",  # Name
										  name,  # Component
										  r"[%s]LICENSE.txt" % name,  # Target
										  None,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  None,  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  name)])  # WkDir
		msilib.add_data(db, "Shortcut", [("README",  # Shortcut
										  "MenuDir",  # Directory
										  "README|README",  # Name
										  name,  # Component
										  r"[%s]README.html" % name,  # Target
										  None,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  None,  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  name)])  # WkDir
		msilib.add_data(db, "Shortcut", [("Uninstall",  # Shortcut
										  "MenuDir",  # Directory
										  "UNINST|Uninstall",  # Name
										  name,  # Component
										  r"[SystemFolder]msiexec",  # Target
										  r"/x" + productcode,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  "uninstall.ico",  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  "SystemFolder")])  # WkDir
		if not dry_run:
			db.Commit()
		sys.argv.remove("finalize_msi")
		if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
			return

	if zeroinstall:
		sys.argv.remove("0install")

	if bdist_appdmg:
		sys.argv.remove("bdist_appdmg")

	if (not bdist_lipa and not zeroinstall and not buildservice and
		not appdata and not bdist_appdmg) or sys.argv[1:]:
		print sys.argv[1:]
		from setup import setup
		setup()
	
	if dry_run or help:
		return

	if buildservice:
		# Create control files
		mapping = {"POST": open(os.path.join(pydir, "util",
											 "rpm_postinstall.sh"),
								"r").read().strip(),
				   "POSTUN": open(os.path.join(pydir, "util",
											   "rpm_postuninstall.sh"),
								  "r").read().strip()}
		tgz = os.path.join(pydir, "dist", "%s-%s.tar.gz" % (name, version))
		if os.path.isfile(tgz):
			with open(tgz, "rb") as tgzfile:
				mapping["MD5"] = md5(tgzfile.read()).hexdigest()
		for tmpl_name in ("PKGBUILD", "debian.changelog", "debian.control",
						  "debian.copyright",
						  "debian.rules", name + ".changes",
						  name + ".dsc", name + ".spec", 
						  os.path.join("0install", "PKGBUILD"),
						  os.path.join("0install", "debian.changelog"),
						  os.path.join("0install", "debian.control"),
						  os.path.join("0install", "debian.rules"),
						  os.path.join("0install", name + ".dsc"),
						  os.path.join("0install", name + ".spec"),
						  os.path.join("obs-autopackage-deploy",
									   name + ".spec")):
			tmpl_path = os.path.join(pydir, "misc", tmpl_name)
			replace_placeholders(tmpl_path,
								 os.path.join(pydir, "dist", tmpl_name),
								 lastmod_time, mapping)

	if bdist_deb:
		# Read setup.cfg
		cfg = RawConfigParser()
		cfg.read(os.path.join(pydir, "setup.cfg"))
		# Get dependencies
		dependencies = [val.strip().split(None, 1) for val in 
						cfg.get("bdist_rpm", "Requires").split(",")]
		# Get group
		if cfg.has_option("bdist_rpm", "group"):
			group = cfg.get("bdist_rpm", "group")
		else:
			group = None
		# Get maintainer
		if cfg.has_option("bdist_rpm", "maintainer"):
			maintainer = cfg.get("bdist_rpm", "maintainer")
		else:
			maintainer = None
		# Get packager
		if cfg.has_option("bdist_rpm", "packager"):
			packager = cfg.get("bdist_rpm", "packager")
		else:
			packager = None
		# Convert dependency format:
		# 'package >= version' to 'package (>= version)'
		for i in range(len(dependencies)):
			if len(dependencies[i]) > 1:
				dependencies[i][1] = "(%s)" % dependencies[i][1]
			dependencies[i] = " ".join(dependencies[i])
		release = 1 # TODO: parse setup.cfg
		rpm_filename = os.path.join(pydir, "dist", "%s-%s-%s.%s.rpm" % 
									(name, version, release, arch))
		if not dry_run:
			# remove target directory (and contents) if it already exists
			target_dir = os.path.join(pydir, "dist", "%s-%s" % (name, version))
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir)
			if os.path.exists(target_dir + ".orig"):
				shutil.rmtree(target_dir + ".orig")
			# use alien to create deb dir from rpm package
			retcode = call(["alien", "-c", "-g", "-k", 
							os.path.basename(rpm_filename)], 
							cwd=os.path.join(pydir, "dist"))
			if retcode != 0:
				sys.exit(retcode)
			# update changelog
			shutil.copy2(os.path.join(pydir, "dist", "debian.changelog"), 
						 os.path.join(pydir, "dist", "%s-%s" % (name, version), 
									  "debian", "changelog"))
			# update rules
			shutil.copy2(os.path.join(pydir, "misc", "alien.rules"), 
						 os.path.join(pydir, "dist", "%s-%s" % (name, version), 
									  "debian", "rules"))
			# update control
			control_filename = os.path.join(pydir, "dist", "%s-%s" % (name, 
																	  version), 
											"debian", "control")
			shutil.copy2(os.path.join(pydir, "dist", "debian.control"), 
						 control_filename)
			### read control file from deb dir
			##control = open(control_filename, "r")
			##lines = [line.rstrip("\n") for line in control.readlines()]
			##control.close()
			### update control with info from setup.cfg
			##for i in range(len(lines)):
				##if lines[i].startswith("Depends:"):
					### add dependencies
					##lines[i] += ", python"
					##lines[i] += ", python" + sys.version[:3]
					##lines[i] += ", " + ", ".join(dependencies)
				##elif lines[i].startswith("Maintainer:") and (maintainer or 
															 ##packager):
					### set maintainer
					##lines[i] = "Maintainer: " + (maintainer or packager)
				##elif lines[i].startswith("Section:") and group:
					### set section
					##lines[i] = "Section: " + group
				##elif lines[i].startswith("Description:"):
					##lines.pop()
					##lines.pop()
					##break
			### write updated control file
			##control = open(control_filename, "w")
			##control.write("\n".join(lines))
			##control.close()
			### run strip on shared libraries
			##sos = os.path.join(change_root(target_dir, get_python_lib(True)),
							   ##name, "*.so")
			##for so in glob.glob(sos):
				##retcode = call(["strip", "--strip-unneeded", so])
			# create deb package
			retcode = call(["chmod", "+x", "./debian/rules"], cwd=target_dir)
			retcode = call(["./debian/rules", "binary"], cwd=target_dir)
			if retcode != 0:
				sys.exit(retcode)

	if setup_cfg or ("bdist_msi" in sys.argv[1:] and use_setuptools):
		shutil.copy2(os.path.join(pydir, "setup.cfg.backup"), 
					 os.path.join(pydir, "setup.cfg"))
	
	if bdist_lipa:
		# Create a Listaller package using lipkgen
		from setup import get_data, get_scripts
		scripts = get_scripts()
		ipkinstall = os.path.join(pydir, "ipkinstall")
		# Generate doap file
		replace_placeholders(os.path.join(pydir, "misc", name + ".doap"),
							 os.path.join(ipkinstall, name + ".doap"),
							 lastmod_time)
		# Adjust .desktop files
		for script, desc in scripts:
			filename = os.path.join(pydir, "misc", script + ".desktop")
			if os.path.exists(filename):
				with open(filename) as file1:
					filename = os.path.join(ipkinstall, script + ".desktop")
					with open(filename, "w") as file2:
						file2.write(file1.read().replace("Exec=" + script,
														 "Exec=%s.pyw" %
														 script2pywname(script)))
		# Collect data
		collect = ([("%APP%", ["ipkinstall/%s.desktop" % script
							   for script, desc in
							   filter(lambda (script, desc):
									  not script.endswith("-apply-profiles"),
									  scripts)])] +
				   [("%%ICON-%s%%" % size,
					 ["%s/theme/icons/%sx%s/%s.png" %
					  (name, size, size, script)
					  for script, desc in scripts])
					for size in (16, 24, 32, 48, 64, 128, 256)] +
				   [("%INST%", ["%s.pyw" % script2pywname(script)
								for script, desc in scripts])] +
				   get_data("%INST%", "data") +
				   get_data("%INST%", "doc") +
				   [("%INST%/" + name,
					 glob.glob(os.path.join(name, "*.py")))] +
				   [("%%INST%%/%s/lib" % name,
					 glob.glob(os.path.join(name, "lib/*.py")))] +
				   [("%%INST%%/%s/lib/agw" % name,
					 glob.glob(os.path.join(name, "lib/agw/*.py")))] +
				   get_data("%INST%/" + name, "package_data", name) +
				   [("%INST%/scripts", ["scripts/%s" % script
										for script, desc in scripts])])
		for bits in (32, 64):
			collect += [("%%INST%%/%s/lib%s" % (name, bits),
						 glob.glob(os.path.join(name, "lib%s/*.py" % bits)))]
			for pycompat in (26, 27):
				collect += [("%%INST%%/%s/lib%s/python%s"
							 % (name, bits, pycompat),
							 glob.glob(os.path.join(name, "lib%s/python%s/*.py"
														  % (bits, pycompat))) +
							 glob.glob(os.path.join(name, "lib%s/python%s/*.so"
														  % (bits, pycompat))))]
		data = {}
		for tgt_dir, files in collect:
			tgt_dir = tgt_dir.replace(os.sep, "/")
			if not tgt_dir in data:
				data[tgt_dir] = []
			data[tgt_dir] += files
		tgt_dirs = sorted(data.keys())
		# Generate files list
		with open(os.path.join(ipkinstall, "files-all.list"), "w") as fileslist:
			fileslist.write("# IPK file list for %s\n" % name)
			fileslist.write("# Generated by setup.py, do not edit\n")
			fileslist.write("\n")
			cur_tgt_dir = None
			for tgt_dir in tgt_dirs:
				if tgt_dir != cur_tgt_dir:
					cur_tgt_dir = tgt_dir
					fileslist.write(":: %s\n" % tgt_dir)
				for filename in sorted(data[tgt_dir]):
					fileslist.write(os.path.relpath(filename,
													pydir).replace(os.sep,
																   "/") + "\n")
		# Create actual Listaller package
		if not which("lipkgen"):
			raise SystemExit("Error: No lipkgen in %s" % os.getenv("PATH"))
		out_dir = os.path.join(pydir, "dist")
		if not os.path.isdir(out_dir):
			os.makedirs(out_dir)
		retcode = call(["lipkgen", "-b", "-o", out_dir, "--sign"])
		if retcode != 0:
			sys.exit(retcode)

	if bdist_pyi:

		# create an executable using pyinstaller

		retcode = call([sys.executable, os.path.join(pydir, "pyinstaller", 
													 "pyinstaller.py"), 
						"--workpath", os.path.join(pydir, "build",
												   "pyi.%s-%s" %
												   (get_platform(),
												    sys.version[:3])),
						"--distpath", os.path.join(pydir, "dist",
												   "pyi.%s-py%s" %
													(get_platform(),
													 sys.version[:3])),
						os.path.join(pydir, "misc", "%s.pyi.spec" % name)])
		if retcode != 0:
			sys.exit(retcode)

	if zeroinstall:
		from xml.dom import minidom
		# Create/update 0install feeds
		from setup import get_data, get_scripts
		scripts = sorted((script2pywname(script), desc)
						 for script, desc in get_scripts())
		cmds = []
		for script, desc in scripts:
			cmdname = "run"
			if script != name:
				cmdname += "-" + script.replace(name + "-", "")
			cmds.append((cmdname, script, desc))
			##if script.endswith("-apply-profiles"):
				### Add forced calibration loading entry
				##cmds.append((cmdname + "-force", script, desc))
		# Get archive digest
		extract = "%s-%s" % (name, version)
		archive_name = extract + ".tar.gz"
		archive_path = os.path.join(pydir, "dist", archive_name)
		p = Popen(["0install", "digest", archive_path.encode(fs_enc), extract],
				  stdout=sp.PIPE, cwd=pydir)
		stdout, stderr = p.communicate()
		print stdout
		hash = re.search("(sha\d+\w+[=_][0-9a-f]+)", stdout.strip())
		if not hash:
			raise SystemExit(p.wait())
		hash = hash.groups()[0]
		for tmpl_name in ("7z.xml", "argyllcms.xml", name + ".xml",
						  name + "-linux.xml", name + "-mac.xml",
						  name + "-win32.xml", "numpy.xml", "pygame.xml",
						  "pywin32.xml", "wmi.xml", "wxpython.xml"):
			dist_path = os.path.join(pydir, "dist", "0install", tmpl_name)
			create = not os.path.isfile(dist_path)
			if create:
				tmpl_path = os.path.join(pydir, "misc", "0install",
										 tmpl_name)
				replace_placeholders(tmpl_path, dist_path, lastmod_time)
			if tmpl_name.startswith(name):
				with open(dist_path) as dist_file:
					xml = dist_file.read()
					domtree = minidom.parseString(xml)
				# Get interface
				interface = domtree.getElementsByTagName("interface")[0]
				# Get languages
				langs = [os.path.splitext(os.path.basename(lang))[0] for lang in
						 glob.glob(os.path.join(name, "lang", "*.json"))]
				# Get architecture groups
				groups = domtree.getElementsByTagName("group")
				if groups:
					# Get main group
					group0 = groups[0]
					# Add languages
					group0.setAttribute("langs", " ".join(langs))
				# Update groups
				for i, group in enumerate(groups[-1:]):
					if create:
						# Remove dummy implementations
						for implementation in group.getElementsByTagName("implementation"):
							if implementation.getAttribute("released") == "0000-00-00":
								implementation.parentNode.removeChild(implementation)
						# Add commands
						runner = domtree.createElement("runner")
						if group.getAttribute("arch").startswith("Windows-"):
							runner.setAttribute("command", "run-win")
						if group.getAttribute("arch").startswith("Linux"):
							python = "http://repo.roscidus.com/python/python"
						else:
							python = "http://%s/0install/python.xml" % domain.lower()
						runner.setAttribute("interface", python)
						runner.setAttribute("version",
											"%i.%i..!3.0" % py_minversion)
						for cmdname, script, desc in cmds:
							# Add command to group
							cmd = domtree.createElement("command")
							cmd.setAttribute("name", cmdname)
							cmd.setAttribute("path", script + ".pyw")
							##if cmdname.endswith("-apply-profiles"):
								### Autostart
								##arg = domtree.createElement("suggest-auto-start")
								##cmd.appendChild(arg)
							if cmdname.endswith("-apply-profiles-force"):
								# Forced calibration loading
								arg = domtree.createElement("arg")
								arg.appendChild(domtree.createTextNode("--force"))
								cmd.appendChild(arg)
							cmd.appendChild(runner.cloneNode(True))
							group.appendChild(cmd)
					# Add implementation if it does not exist yet, update otherwise
					match = None
					for implementation in group.getElementsByTagName("implementation"):
						match = (implementation.getAttribute("version") == version and
								 implementation.getAttribute("stability") == stability)
						if match:
							break
					if not match:
						implementation = domtree.createElement("implementation")
						implementation.setAttribute("version", version)
						implementation.setAttribute("released",
													strftime("%Y-%m-%d", 
															 gmtime(lastmod_time)))
						implementation.setAttribute("stability", stability)
						digest = domtree.createElement("manifest-digest")
						implementation.appendChild(digest)
						archive = domtree.createElement("archive")
						implementation.appendChild(archive)
					else:
						digest = implementation.getElementsByTagName("manifest-digest")[0]
						for attrname, value in digest.attributes.items():
							# Remove existing hashes
							digest.removeAttribute(attrname)
						archive = implementation.getElementsByTagName("archive")[0]
					implementation.setAttribute("id", hash)
					digest.setAttribute(*hash.split("="))
					# Update archive
					if stability == "stable":
						folder = ""
					else:
						folder = "&folder=snapshot"
					archive.setAttribute("extract", extract)
					archive.setAttribute("href",
										 "http://%s/download.php?version=%s&suffix=.tar.gz%s" %
										 (domain.lower(), version, folder))
					archive.setAttribute("size", "%s" % os.stat(archive_path).st_size)
					archive.setAttribute("type", "application/x-compressed-tar")
					group.appendChild(implementation)
				if create:
					for cmdname, script, desc in cmds:
						# Add entry-points to interface
						entry_point = domtree.createElement("entry-point")
						entry_point.setAttribute("command", cmdname)
						binname = script
						if cmdname.endswith("-force"):
							binname += "-force"
						entry_point.setAttribute("binary-name", binname)
						cfg = RawConfigParser()
						desktopbasename = "%s.desktop" % script
						if cmdname.endswith("-apply-profiles"):
							desktopbasename = "z-" + desktopbasename
						cfg.read(os.path.join(pydir, "misc",
											  desktopbasename))
						for option, tagname in (("Name", "name"),
												("GenericName", "summary"),
												("Comment", "description")):
							for lang in [None] + langs:
								if lang:
									suffix = "[%s]" % lang
								else:
									suffix = ""
								option = "%s%s" % (option, suffix)
								if cfg.has_option("Desktop Entry", option):
									value = cfg.get("Desktop Entry",
													option).decode("UTF-8")
									if value:
										tag = domtree.createElement(tagname)
										if not lang:
											lang = "en"
										tag.setAttribute("xml:lang", lang)
										tag.appendChild(domtree.createTextNode(value))
										entry_point.appendChild(tag)
						for ext, mime_type in (("ico", "image/vnd.microsoft.icon"),
											   ("png", "image/png")):
							icon = domtree.createElement("icon")
							if ext == "ico":
								subdir = ""
								filename = script
							else:
								subdir = "256x256/"
								filename = script.lower()
							icon.setAttribute("href",
											  "http://%s/theme/icons/%s%s.%s" %
											  (domain.lower(), subdir,
											   filename, ext))
							icon.setAttribute("type", mime_type)
							entry_point.appendChild(icon)
						interface.appendChild(entry_point)
				# Update feed
				print "Updating 0install feed", dist_path
				with open(dist_path, "wb") as dist_file:
					xml = domtree.toprettyxml(encoding="utf-8")
					xml = re.sub(r"\n\s+\n", "\n", xml)
					xml = re.sub(r"\n\s*([^<]+)\n\s*", r"\1", xml)
					dist_file.write(xml)
				# Sign feed
				zeropublish = which("0publish") or which("0publish.exe")
				args = []
				if not zeropublish:
					zeropublish = which("0install") or which("0install.exe")
					if zeropublish:
						args = ["run", "--command", "0publish", "--",
								"http://0install.de/feeds/ZeroInstall_Tools.xml"]
				if zeropublish:
					passphrase_path = os.path.join(pydir, "gpg", "passphrase.txt")
					print "Signing", dist_path
					if os.path.isfile(passphrase_path):
						import wexpect
						with open(passphrase_path) as passphrase_file:
							passphrase = passphrase_file.read().strip()
						p = wexpect.spawn(zeropublish.encode(fs_enc), args +
										  ["-x", dist_path.encode(fs_enc)])
						p.expect(":")
						p.send(passphrase)
						p.send("\n")
						try:
							p.expect(wexpect.EOF, timeout=3)
						except:
							p.terminate()
					else:
						call([zeropublish] + args + ["-x", dist_path.encode(fs_enc)])
				else:
					print "WARNING: 0publish not found, please sign the feed!"
		# Create 0install app bundles
		bundletemplate = os.path.join("0install", "template.app", "Contents")
		bundletemplatepath = os.path.join(pydir, bundletemplate)
		if os.path.isdir(bundletemplatepath):
			p = Popen(["0install", "-V"], stdout=sp.PIPE)
			stdout, stderr = p.communicate()
			zeroinstall_version = re.search(r" (\d(?:\.\d+)+)", stdout)
			if zeroinstall_version:
				zeroinstall_version = zeroinstall_version.groups()[0]
			if zeroinstall_version < "2.8":
				zeroinstall_version = "2.8"
			feeduri = "http://%s/0install/%s.xml" % (domain.lower(), name)
			dist_dir = os.path.join(pydir, "dist", "0install",
									name + "-0install")
			for script, desc in scripts + [("0install-launcher",
											"0install Launcher"),
										   ("0install-cache-manager",
											"0install Cache Manager")]:
				if script.endswith("-apply-profiles"):
					continue
				desc = re.sub("^%s " % name, "", desc).strip()
				if script == "0install-launcher":
					bundlename = name
				else:
					bundlename = desc
				bundledistpath = os.path.join(dist_dir, desc + ".app",
											  "Contents")
				replace_placeholders(os.path.join(bundletemplatepath,
												  "Info.plist"),
									 os.path.join(bundledistpath,
												  "Info.plist"), lastmod_time,
									 {"NAME": bundlename,
									  "EXECUTABLE": script,
									  "ID": ".".join(reversed(domain.split("."))).replace(name,
																						  script)})
				if script.startswith(name):
					run = "0launch%s -- %s" % (re.sub("^%s" % name,
													  " --command=run", script),
											   feeduri)
				else:
					run = {"0install-launcher": "0launch --gui " + feeduri,
						   "0install-cache-manager": "0store manage"}.get(script)
				replace_placeholders(os.path.join(bundletemplatepath, "MacOS",
												  "template"),
									 os.path.join(bundledistpath,
												  "MacOS", script),
									 lastmod_time,
									 {"EXEC": run,
									  "ZEROINSTALL_VERSION": zeroinstall_version})
				os.chmod(os.path.join(bundledistpath, "MacOS", script), 0755)
				for binary in os.listdir(os.path.join(bundletemplatepath,
													  "MacOS")):
					if binary == "template":
						continue
					src = os.path.join(bundletemplatepath, "MacOS", binary)
					dst = os.path.join(bundledistpath, "MacOS", binary)
					if os.path.islink(src):
						linkto = os.readlink(src)
						if os.path.islink(dst) and os.readlink(dst) != linkto:
							os.remove(dst)
						if not os.path.islink(dst):
							os.symlink(linkto, dst)
					else:
						shutil.copy2(src, dst)
				resdir = os.path.join(bundledistpath, "Resources")
				if not os.path.isdir(resdir):
					os.mkdir(resdir)
				if script.startswith(name):
					iconsrc = os.path.join(pydir, name, "theme", "icons",
										   script + ".icns")
				else:
					iconsrc = os.path.join(pydir, "0install",
										   "ZeroInstall.icns")
				icondst = os.path.join(resdir, script + ".icns")
				if os.path.isfile(iconsrc) and not os.path.isfile(icondst):
					shutil.copy2(iconsrc, icondst)
			# README as .webloc file (link to homepage)
			with codecs.open(os.path.join(dist_dir, "README.webloc"), "w",
							 "UTF-8") as readme:
				readme.write("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>URL</key>
	<string>http://%s/</string>
</dict>
</plist>
""" % domain.lower())
			# Copy LICENSE.txt
			shutil.copy2(os.path.join(pydir, "LICENSE.txt"),
						 os.path.join(dist_dir, "LICENSE.txt"))
	
	if bdist_appdmg:
		create_appdmg(zeroinstall)


if __name__ == "__main__":
	setup()
