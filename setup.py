#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ConfigParser import RawConfigParser
from distutils.sysconfig import get_python_lib
from distutils.util import change_root, get_platform
from subprocess import call, Popen
from time import gmtime, strftime, timezone
import codecs
import glob
import math
import os
import shutil
import subprocess as sp
import sys
import time
if sys.platform == "win32":
	import msilib

sys.path.insert(0, "dispcalGUI")

from util_os import which
from util_str import strtr

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)

def create_appdmg():
	retcode = call(["hdiutil", "create", os.path.join(pydir, "dist", 
													  "%s-%s.dmg" % 
													  (name, version)), 
					"-volname", name, "-srcfolder", 
					os.path.join(pydir, "dist", "py2app.%s-py%s" % 
					(get_platform(), sys.version[:3]), name + "-" + version)])
	if retcode != 0:
		sys.exit(retcode)


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

	arch = None
	bdist_appdmg = "bdist_appdmg" in sys.argv[1:]
	bdist_deb = "bdist_deb" in sys.argv[1:]
	bdist_pyi = "bdist_pyi" in sys.argv[1:]
	setup_cfg = None
	dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
	help = False
	inno = "inno" in sys.argv[1:]
	onefile = "-F" in sys.argv[1:] or "--onefile" in sys.argv[1:]
	purge = "purge" in sys.argv[1:]
	purge_dist = "purge_dist" in sys.argv[1:]
	suffix = "onefile" if onefile else "onedir"
	use_setuptools = "--use-setuptools" in sys.argv[1:]
	
	argv = list(sys.argv[1:])
	for i, arg in enumerate(reversed(argv)):
		n = len(sys.argv) - i - 1
		arg = arg.split("=")
		if len(arg) == 2:
			if arg[0] == "--force-arch":
				arch = arg[1]
			elif arg[0] == "--cfg":
				setup_cfg = arg[1]
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
			svnversion = strtr(svnversion.strip().split(":")[-1], 
							   ["M", "P", "S"])
			svnversion = svnversion_parse(svnversion)
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
				if item.upper()[0] != "D":
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
			versionpy = open(os.path.join(pydir, "dispcalGUI", "__version__.py"), "w")
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
	
	global name, version
	from meta import (name, author, author_email, description, longdesc,
					  domain, py_maxversion, py_minversion,
					  version, version_lin, version_mac, 
					  version_src, version_tuple, version_win,
					  wx_minversion)

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

		# remove the "build", "dispcalGUI.egg-info" and 
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
		readme_template_path = os.path.join(pydir, "misc", 
											"README.template.html")
		readme_template = open(readme_template_path, "rb")
		readme_template_html = readme_template.read()
		readme_template.close()
		for key, val in [
			("DATE", 
				strftime("%Y-%m-%d", 
						 gmtime(lastmod_time or 
								os.stat(readme_template_path).st_mtime))),
			("TIME", 
				strftime("%H:%M", 
						 gmtime(lastmod_time or 
								os.stat(readme_template_path).st_mtime))),
			("TIMESTAMP", 
				strftime("%Y-%m-%dT%H:%M:%S", 
						 gmtime(lastmod_time or 
								os.stat(readme_template_path).st_mtime)) +
						 ("+" if timezone < 0 else "-") +
						 strftime("%H:%M", gmtime(abs(timezone)))),
			("VERSION", version),
			("VERSION_LIN", version_lin),
			("VERSION_MAC", version_mac),
			("VERSION_WIN", version_win),
			("VERSION_SRC", version_src)
		]:
			readme_template_html = readme_template_html.replace("${%s}" % key, 
																val)
		readme = open(os.path.join(pydir, "README.html"), "rb")
		readme_html = readme.read()
		readme.close()
		if readme_html != readme_template_html and not dry_run:
			readme = open(os.path.join(pydir, "README.html"), "wb")
			readme.write(readme_template_html)
			readme.close()
		sys.argv.remove("readme")
		if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
			return

	if (("sdist" in sys.argv[1:] or 
		 "install" in sys.argv[1:] or 
		 "bdist_deb" in sys.argv[1:]) and 
		not help) or "buildservice" in sys.argv[1:]:
		# Create control files
		post = open(os.path.join(pydir, "util", "rpm_postinstall.sh"), "r").read()
		postun = open(os.path.join(pydir, "util", "rpm_postuninstall.sh"), "r").read()
		for tmpl_name in ("debian.changelog", "debian.control", "debian.copyright", 
						  "debian.rules", "dispcalGUI.dsc", "dispcalGUI.spec", 
						  "dispcalGUI.autopackage.spec"):
			tmpl_path = os.path.join(pydir, "misc", tmpl_name)
			tmpl = codecs.open(tmpl_path, "r", "UTF-8")
			tmpl_data = tmpl.read()
			tmpl.close()
			if tmpl_name.startswith("debian"):
				longdesc_backup = longdesc
				longdesc = "\n".join([" " + (line if line.strip() else ".") 
									  for line in longdesc.splitlines()])
			for key, val in [
				("DATE", 
					strftime("%a %b %d %Y",  # e.g. Tue Jul 06 2010
							 gmtime(lastmod_time or 
									os.stat(tmpl_path).st_mtime))),
				("DEBPACKAGE", name.lower()),
				("DEBDATETIME", strftime("%a, %d %b %Y %H:%M:%S ",  # e.g. Wed, 07 Jul 2010 15:25:00 +0100
										 gmtime(lastmod_time or 
												os.stat(tmpl_path).st_mtime)) +
										 ("+" if timezone < 0 else "-") +
										 strftime("%H%M", gmtime(abs(timezone)))),
				("SUMMARY", description),
				("DESC", longdesc),
				("MAINTAINER", author),
				("MAINTAINER_EMAIL", author_email),
				("PACKAGE", name),
				("POST", post),
				("POSTUN", postun),
				("PY_MAXVERSION", ".".join(str(n) for n in py_maxversion)),
				("PY_MINVERSION", ".".join(str(n) for n in py_minversion)),
				("VERSION", version_src),
				("URL", "http://%s.hoech.net/" % name),
				("WX_MINVERSION", ".".join(str(n) for n in wx_minversion)),
				("YEAR", strftime("%Y", gmtime())),
			]:
				tmpl_data = tmpl_data.replace("${%s}" % key, val)
			if tmpl_name.startswith("debian"):
				longdesc = longdesc_backup
			if not dry_run:
				if tmpl_name == "debian.copyright":
					tmpl_name = "copyright"
				out_dir = os.path.join(pydir, "dist")
				if not os.path.isdir(out_dir):
					os.makedirs(out_dir)
				out_filename = os.path.join(out_dir, tmpl_name)
				out = codecs.open(out_filename, "w", "UTF-8")
				out.write(tmpl_data)
				out.close()
		if "buildservice" in sys.argv[1:]:
			sys.argv.remove("buildservice")
			if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
				return

	if bdist_appdmg:
		i = sys.argv.index("bdist_appdmg")
		sys.argv = sys.argv[:i] + sys.argv[i + 1:]
		if len(sys.argv) == 1:
			create_appdmg()
			return

	if bdist_deb:
		bdist_args = ["bdist_rpm"]
		if not arch:
			arch = get_platform().split("-")[1]
			bdist_args += ["--force-arch=" + arch]
		i = sys.argv.index("bdist_deb")
		sys.argv = sys.argv[:i] + bdist_args + sys.argv[i + 1:]

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

	if inno and sys.platform == "win32":
		inno_template_path = os.path.join(pydir, "misc", "%s-Setup-%s.iss" % 
										  (name, ("pyi-" + 
												  suffix if bdist_pyi else 
												  bdist_cmd)))
		inno_template = open(inno_template_path, "r")
		inno_script = inno_template.read().decode("MBCS", "replace") % {
			"AppVerName": version,
			"AppPublisherURL": "http://" + domain,
			"AppSupportURL": "http://" + domain,
			"AppUpdatesURL": "http://" + domain,
			"VersionInfoVersion": ".".join(map(str, version_tuple)),
			"VersionInfoTextVersion": version,
			"AppVersion": version,
			"Platform": get_platform(),
			"PythonVersion": sys.version[:3],
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
		db = msilib.OpenDatabase(r"dist\dispcalGUI-%s.win32-py%s.msi" %
								 (msiversion, sys.version[:3]), 
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
										   "DISPCA~1|dispcalGUI")])  # DefaultDir
		msilib.add_data(db, "Icon", [("dispcalGUI.ico",  # Name
									  msilib.Binary(os.path.join(pydir, "dispcalGUI", 
														"theme", "icons", 
														"dispcalGUI.ico")))])  # Data
		msilib.add_data(db, "Icon", [("uninstall.ico",  # Name
									  msilib.Binary(os.path.join(pydir, "dispcalGUI", 
														"theme", "icons", 
														"dispcalGUI-uninstall.ico")))])  # Data
		msilib.add_data(db, "RemoveFile", [("MenuDir",  # FileKey
											"dispcalGUI",  # Component
											None,  # FileName
											"MenuDir",  # DirProperty
											2)])  # InstallMode
		msilib.add_data(db, "Registry", [("DisplayIcon",  # Registry
										  -1,  # Root
										  r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" % 
										  productcode,  # Key
										  "DisplayIcon",  # Name
										  r"[icons]dispcalGUI.ico",  # Value
										  "dispcalGUI")])  # Component
		msilib.add_data(db, "Shortcut", [("dispcalGUI",  # Shortcut
										  "MenuDir",  # Directory
										  "DISPCA~1|dispcalGUI",  # Name
										  "dispcalGUI",  # Component
										  r"[TARGETDIR]pythonw.exe",  # Target
										  r'"[TARGETDIR]Scripts\dispcalGUI"',  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  "dispcalGUI.ico",  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  "dispcalGUI")])  # WkDir
		msilib.add_data(db, "Shortcut", [("LICENSE",  # Shortcut
										  "MenuDir",  # Directory
										  "LICENSE|LICENSE",  # Name
										  "dispcalGUI",  # Component
										  r"[dispcalGUI]LICENSE.txt",  # Target
										  None,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  None,  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  "dispcalGUI")])  # WkDir
		msilib.add_data(db, "Shortcut", [("README",  # Shortcut
										  "MenuDir",  # Directory
										  "README|README",  # Name
										  "dispcalGUI",  # Component
										  r"[dispcalGUI]README.html",  # Target
										  None,  # Arguments
										  None,  # Description
										  None,  # Hotkey
										  None,  # Icon
										  None,  # IconIndex
										  None,  # ShowCmd
										  "dispcalGUI")])  # WkDir
		msilib.add_data(db, "Shortcut", [("Uninstall",  # Shortcut
										  "MenuDir",  # Directory
										  "UNINST|Uninstall",  # Name
										  "dispcalGUI",  # Component
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

	from setup import setup
	setup()
	
	if bdist_appdmg and not dry_run and not help:
		create_appdmg()

	if bdist_deb and not help:
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
			retcode = call(["./debian/rules", "binary"], cwd=target_dir)
			if retcode != 0:
				sys.exit(retcode)
	
	if dry_run or help:
		return

	if setup_cfg or ("bdist_msi" in sys.argv[1:] and use_setuptools):
		shutil.copy2(os.path.join(pydir, "setup.cfg.backup"), 
					 os.path.join(pydir, "setup.cfg"))

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
		retcode = call([sys.executable, "-O", os.path.join(pydir, 
														   "pyinstaller", 
														   "Configure.py")])
		retcode = call([sys.executable, "-O", os.path.join(pydir, 
														   "pyinstaller", 
														   "Build.py"), 
						"-o", os.path.join(pydir, "build", "pyi.%s-%s-%s" % 
										   (get_platform(), sys.version[:3], 
										   suffix), name + "-" + version), 
						os.path.join(pydir, "misc", "%s-pyi-%s.spec" % 
									 (name, suffix))])
		if retcode != 0:
			sys.exit(retcode)


if __name__ == "__main__":
	setup()
