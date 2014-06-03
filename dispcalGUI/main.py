# -*- coding: utf-8 -*-

import logging
import os
import platform
import sys
import traceback
if sys.platform == "darwin":
	from platform import mac_ver
	import posix

# Python version check
from meta import py_minversion, py_maxversion

pyver = sys.version_info[:2]
if pyver < py_minversion or pyver > py_maxversion:
	raise RuntimeError("Need Python version >= %s <= %s, got %s" % 
					   (".".join(str(n) for n in py_minversion),
						".".join(str(n) for n in py_maxversion),
					    sys.version.split()[0]))

from config import (autostart_home, confighome, datahome, enc, exe, exe_ext,
					exedir, exename, get_data_path,fs_enc, isapp, isexe,
					logdir, pydir, pyname, pypath, resfiles, runtype)
from debughelpers import ResourceError, handle_error
from log import log, safe_print
from meta import build, name as appname, version
from options import debug, verbose
from util_str import safe_unicode
from wxaddons import wx

def _excepthook(etype, value, tb):
	handle_error((etype, value, tb))

sys.excepthook = _excepthook


def main(module=None):
	log("=" * 80)
	if verbose >= 1:
		safe_print(pyname + runtype, version, build)
	if sys.platform == "darwin":
		safe_print("Mac OS X %s %s" % (mac_ver()[0], mac_ver()[-1]))
	else:
		if sys.platform == "win32":
			# http://msdn.microsoft.com/en-us/library/windows/desktop/ms724832%28v=vs.85%29.aspx
			ver2name = {(5, 0): "2000",
						(5, 1): "XP",
						(5, 2): "XP 64-Bit/Server 2003/Server 2003 R2",
						(6, 0): "Vista/Server 2008",
						(6, 1): "7/Server 2008 R2",
						(6, 2): "8/Server 2012"}
			dist = ver2name.get(sys.getwindowsversion()[:2], "N/A")
		else:
			dist = "%s %s %s" % getattr(platform, "linux_distribution", 
										platform.dist)()
		safe_print("%s %s (%s)" % (platform.system(), platform.version(), dist))
	safe_print("Python " + sys.version)
	safe_print("wxPython " + wx.version())
	try:
		# Check for required resource files
		mod2res = {None: resfiles,
				   "3DLUT-maker": ["xrc/3dlut.xrc"],
				   "curve-viewer": [],
				   "profile-info": [],
				   "synthprofile": ["xrc/synthicc.xrc"],
				   "testchart-editor": [],
				   "VRML-to-X3D-converter": []}
		if module not in mod2res:
			module = None
		for filename in mod2res[module]:
			path = get_data_path(os.path.sep.join(filename.split("/")))
			if not path or not os.path.isfile(path):
				import localization as lang
				lang.init()
				raise ResourceError(lang.getstr("resources.notfound.error") + 
									"\n" + filename)
		# Force to run inside tty with the --terminal option
		if "--terminal" in sys.argv[1:]:
			import subprocess as sp
			if sys.platform == "win32":
				import win32api
			from util_os import which
			if isapp:
				# PyInstaller: executable is app-specific
				# py2app: executable is always the same, differentiation
				# occurs in Resources/main.py
				cmd = u'"%s"' % (exe if exename.startswith(appname)
								 else os.path.join(exedir, appname))
				cwd = None
			elif isexe:
				if sys.platform == "win32":
					cmd = u'"%s"' % win32api.GetShortPathName(exe)
				else:
					cmd = u'"%s"' % exe
				cwd = None
			else:
				if os.path.basename(exe) == "pythonw" + exe_ext:
					python = os.path.join(os.path.dirname(exe), 
										  "python" + exe_ext)
				else:
					python = exe
				if sys.platform == "win32":
					cmd = u'"%s" "%s"' % tuple(
						[win32api.GetShortPathName(path) for path in (python, 
																	  pypath)])
					cwd = win32api.GetShortPathName(pydir)
				else:
					cmd = u'"%s" "%s"' % (exe, pypath)
					cwd = pydir.encode(fs_enc)
			safe_print("Re-launching instance in terminal")
			if sys.platform == "win32":
				cmd = u'start "%s" /WAIT %s' % (pyname, cmd)
				if debug: safe_print("[D]", cmd)
				retcode = sp.call(cmd.encode(fs_enc), shell=True, cwd=cwd)
			elif sys.platform == "darwin":
				if debug: safe_print("[D]", cmd)
				from util_mac import mac_terminal_do_script
				retcode, output, errors = mac_terminal_do_script(cmd)
			else:
				import tempfile
				stdout = tempfile.SpooledTemporaryFile()
				retcode = None
				terminals_opts = {
					"Terminal": "-x",
					"gnome-terminal": "-x",
					"konsole": "-e",
					"xterm": "-e"
				}
				terminals = terminals_opts.keys()
				for terminal in terminals:
					if which(terminal):
						if debug:
							safe_print("[D] %s %s %s" % 
									   (terminal, terminals_opts[terminal], 
										cmd))
						stdout.write('%s %s %s' % 
									 (terminal, terminals_opts[terminal], 
									  cmd.encode(fs_enc)))
						retcode = sp.call(
							[terminal, terminals_opts[terminal]] + 
							cmd.encode(fs_enc).strip('"').split('" "'), 
							stdout=stdout, stderr=sp.STDOUT, cwd=cwd)
						stdout.write('\n\n')
						break
				stdout.seek(0)
			if retcode != 0:
				app = wx.App(redirect=False)
				if sys.platform == "win32":
					msg = (u'An attempt to launch a command prompt failed.')
				elif sys.platform == "darwin":
					msg = (u'An attempt to launch Terminal failed.')
				else:
					if retcode is None:
						msg = (u'An attempt to launch a terminal failed, '
							   'because none of those known seem to be '
							   'installed (%s).' % ", ".join(terminals))
					else:
						msg = (u'An attempt to launch a terminal failed:\n\n%s'
							   % unicode(stdout.read(), enc, "replace"))
				handle_error(msg)
		else:
			# Create main data dir if it does not exist
			if not os.path.exists(datahome):
				try:
					os.makedirs(datahome)
				except Exception, exception:
					handle_error("Warning - could not create directory '%s'" % 
								 datahome)
			elif sys.platform == "darwin":
				# Check & fix permissions if necessary
				import getpass
				user = getpass.getuser().decode(fs_enc)
				script = []
				for directory in (confighome, datahome, logdir):
					if (os.path.isdir(directory) and
						not os.access(directory, os.W_OK)):
						script.append("chown -R '%s' '%s'" % (user, directory))
				if script:
					import subprocess as sp
					sp.Popen(['osascript', '-e', 
							  'do shell script "%s" with administrator privileges' 
							  % ";".join(script).encode(fs_enc)])
			if sys.platform not in ("darwin", "win32"):
				# Linux: Try and fix v0.2.1b calibration loader, because 
				# calibrationloader.sh is no longer present in v0.2.2b+
				desktopfile_name = appname + "-Calibration-Loader-Display-"
				if autostart_home and os.path.exists(autostart_home):
					try:
						autostarts = os.listdir(autostart_home)
					except Exception, exception:
						safe_print(u"Warning - directory '%s' listing failed: "
								   u"%s" % tuple(safe_unicode(s) for s in 
												 (autostarts, exception)))
					import ConfigParser
					from util_io import StringIOu as StringIO
					for filename in autostarts:
						if filename.startswith(desktopfile_name):
							try:
								desktopfile_path = os.path.join(autostart_home, 
																filename)
								cfg = ConfigParser.SafeConfigParser()
								cfg.optionxform = str
								cfg.read([desktopfile_path])
								exec_ = cfg.get("Desktop Entry", "Exec")
								if exec_.find("calibrationloader.sh") > -1:
									cfg.set(
										"Desktop Entry", "Exec", 
										re.sub('"[^"]*calibrationloader.sh"\s*', 
											   '', exec_, 1))
									cfgio = StringIO()
									cfg.write(cfgio)
									desktopfile = open(desktopfile_path, "w")
									cfgio.seek(0)
									desktopfile.write("".join(["=".join(line.split(" = ", 1)) 
															   for line in cfgio]))
									desktopfile.close()
							except Exception, exception:
								safe_print("Warning - could not process old "
										   "calibration loader:", 
										   safe_unicode(exception))
			# Initialize & run
			accepts_filename_argument = False
			if module == "3DLUT-maker":
				from wxLUT3DFrame import main as main
			elif module == "curve-viewer":
				from wxLUTViewer import main as main
				accepts_filename_argument = True
			elif module == "profile-info":
				from wxProfileInfo import main as main
				accepts_filename_argument = True
			elif module == "synthprofile":
				from wxSynthICCFrame import main as main
			elif module == "testchart-editor":
				from wxTestchartEditor import main as main
				accepts_filename_argument = True
			elif module == "VRML-to-X3D-converter":
				from wxVRML2X3D import main as main
				accepts_filename_argument = True
			else:
				from dispcalGUI import main as main
			if accepts_filename_argument:
				main(*[safe_unicode(arg) for arg in
					   sys.argv[max(len(sys.argv) - 1, 1):]])
			else:
				main()
	except Exception, exception:
		if isinstance(exception, ResourceError):
			error = exception
		else:
			error = u"Fatal error: " + safe_unicode(traceback.format_exc())
		handle_error(error)
	try:
		logger = logging.getLogger(appname)
		for handler in logger.handlers:
			logger.removeHandler(handler)
		logging.shutdown()
	except Exception, exception:
		pass


def main_3dlut_maker():
	main("3DLUT-maker")


def main_curve_viewer():
	main("curve-viewer")


def main_profile_info():
	main("profile-info")


def main_synthprofile():
	main("synthprofile")


def main_testchart_editor():
	main("testchart-editor")

if __name__ == "__main__":
	main()
