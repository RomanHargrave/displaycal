# -*- coding: utf-8 -*-

from __future__ import with_statement
from time import sleep
import atexit
import errno
import logging
import os
import platform
import socket
import sys
import subprocess as sp
import threading
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
					exedir, exename, get_data_path, getcfg, fs_enc, initcfg,
					isapp, isexe, logdir, pydir, pyname, pypath, resfiles,
					runtype, appbasename)
from debughelpers import ResourceError, handle_error
from log import log, safe_print
from meta import VERSION, VERSION_BASE, VERSION_STRING, build, name as appname
from multiprocess import mp
from options import debug, verbose
from util_str import safe_str, safe_unicode
if sys.platform == "win32":
	from util_win import win_ver
	import ctypes


def _excepthook(etype, value, tb):
	handle_error((etype, value, tb))

sys.excepthook = _excepthook


def main(module=None):
	mp.freeze_support()
	if module:
		name = "%s-%s" % (appbasename, module)
	else:
		name = appbasename
	log("=" * 80)
	if verbose >= 1:
		version = VERSION_STRING
		if VERSION > VERSION_BASE:
			 version += " Beta"
		safe_print(pyname + runtype, version, build)
	if sys.platform == "darwin":
		# Python's platform.platform output is useless under Mac OS X
		# (e.g. 'Darwin-15.0.0-x86_64-i386-64bit' for Mac OS X 10.11 El Capitan)
		safe_print("Mac OS X %s %s" % (mac_ver()[0], mac_ver()[-1]))
	elif sys.platform == "win32":
		machine = platform.machine()
		safe_print(*filter(lambda v: v, win_ver()) +
				   ({"AMD64": "x86_64"}.get(machine, machine), ))
	else:
		# Linux
		safe_print(' '.join(platform.dist()), platform.machine())
	safe_print("Python " + sys.version)
	# Enable faulthandler
	try:
		import faulthandler
	except Exception, exception:
		safe_print(exception)
	else:
		try:
			faulthandler.enable(open(os.path.join(logdir, pyname +
														  "-fault.log"), "w"))
		except Exception, exception:
			safe_print(exception)
		else:
			safe_print("Faulthandler", getattr(faulthandler, "__version__", ""))
	from wxaddons import wx
	if u"phoenix" in wx.PlatformInfo:
		# py2exe helper so wx.xml gets picked up
		from wx import xml
	from wxwindows import BaseApp
	safe_print("wxPython " + wx.version())
	safe_print("Encoding: " + enc)
	safe_print("File system encoding: " + fs_enc)
	if sys.platform == "win32" and sys.getwindowsversion() >= (6, 2):
		# HighDPI support
		try:
			shcore = ctypes.windll.shcore
		except Exception, exception:
			safe_print("Warning - could not load shcore:", exception)
		else:
			if hasattr(shcore, "SetProcessDpiAwareness"):
				try:
					# 1 = System DPI aware (wxWpython currently does not
					# support per-monitor DPI)
					shcore.SetProcessDpiAwareness(1)
				except Exception, exception:
					safe_print("Warning - SetProcessDpiAwareness() failed:",
							   exception)
			else:
				safe_print("Warning - SetProcessDpiAwareness not found in shcore")
	lockfilename = None
	port = 0
	# Allow multiple instances only for curve viewer, profile info,
	# scripting client, synthetic profile creator and testchart editor
	multi_instance = ("curve-viewer", "profile-info", "scripting-client",
					  "synthprofile", "testchart-editor")
	try:
		initcfg()
		host = "127.0.0.1"
		if module not in multi_instance:
			# Check lockfile(s) and probe port(s)
			incoming = None
			lockfilebasenames = []
			if module:
				lockfilebasenames.append(name)
			if module not in ("3DLUT-maker", "VRML-to-X3D-converter",
							  "apply-profiles"):
				lockfilebasenames.append(appbasename)
			for lockfilebasename in lockfilebasenames:
				lockfilename = os.path.join(confighome, "%s.lock" %
														lockfilebasename)
				if os.path.isfile(lockfilename):
					try:
						with open(lockfilename) as lockfile:
							port = lockfile.read().strip()
					except EnvironmentError, exception:
						# This shouldn't happen
						safe_print("Warning - could not read lockfile %s:" %
								   lockfilename, exception)
						port = getcfg("app.port")
					else:
						try:
							port = int(port)
						except ValueError:
							# This shouldn't happen
							safe_print("Warning - invalid port number:", port)
							port = getcfg("app.port")
					appsocket = AppSocket()
					if not appsocket:
						break
					else:
						incoming = None
						if appsocket.connect(host, port):
							# Other instance already running?
							# Get appname to check if expected app is actually
							# running under that port
							if appsocket.send("getappname"):
								incoming = appsocket.read()
								if incoming.rstrip("\4") != pyname:
									incoming = None
						if incoming:
							# Send args as UTF-8
							if module == "apply-profiles":
								# Always try to close currently running instance
								data = ["close"]
							else:
								# Send module/appname to notify running app
								data = [module or appname]
								if module != "3DLUT-maker":
									for arg in sys.argv[1:]:
										data.append(safe_str(safe_unicode(arg),
															 "UTF-8"))
							data = sp.list2cmdline(data)
							if appsocket.send(data):
								incoming = appsocket.read()
						appsocket.close()
						if incoming and incoming.rstrip("\4") == "ok":
							# Successfully sent our request
							break
						elif incoming == "" and module == "apply-profiles":
							# Successfully sent our close request.
							# Wait for lockfile to be removed, in which case
							# we know the running instance has successfully
							# closed.
							while os.path.isfile(lockfilename):
								sleep(.05)
							incoming = None
							break
			if incoming is not None:
				# Other instance running?
				import localization as lang
				lang.init()
				if incoming.rstrip("\4") == "ok":
					# Successfully sent our request
					safe_print(lang.getstr("app.otherinstance.notified"))
				else:
					# Other instance busy?
					handle_error(lang.getstr("app.otherinstance", name))
				# Exit
				return
		lockfilename = os.path.join(confighome, "%s.lock" % name)
		# Create listening socket
		appsocket = AppSocket()
		if appsocket:
			sys._appsocket = appsocket.socket
			if getcfg("app.allow_network_clients"):
				host = ""
			for port in (getcfg("app.port"), 0):
				try:
					sys._appsocket.bind((host, port))
				except socket.error, exception:
					if port == 0:
						safe_print("Warning - could not bind to %s:%s:" %
								   (host, port), exception)
						del sys._appsocket
						break
				else:
					try:
						sys._appsocket.settimeout(.2)
					except socket.error, exception:
						safe_print("Warning - could not set socket "
								   "timeout:", exception)
						del sys._appsocket
						break
					try:
						sys._appsocket.listen(1)
					except socket.error, exception:
						safe_print("Warning - could not listen on "
								   "socket:", exception)
						del sys._appsocket
						break
					try:
						port = sys._appsocket.getsockname()[1]
					except socket.error, exception:
						safe_print("Warning - could not get socket "
								   "address:", exception)
						del sys._appsocket
						break
					if module in multi_instance:
						mode = "a"
					else:
						mode = "w"
					write_lockfile(lockfilename, mode, str(port))
					break
		atexit.register(lambda: safe_print("Ran application exit handlers"))
		BaseApp.register_exitfunc(_exit, lockfilename, port)
		# Check for required resource files
		mod2res = {"3DLUT-maker": ["xrc/3dlut.xrc"],
				   "curve-viewer": [],
				   "profile-info": [],
				   "scripting-client": [],
				   "synthprofile": ["xrc/synthicc.xrc"],
				   "testchart-editor": [],
				   "VRML-to-X3D-converter": []}
		for filename in mod2res.get(module, resfiles):
			path = get_data_path(os.path.sep.join(filename.split("/")))
			if not path or not os.path.isfile(path):
				import localization as lang
				lang.init()
				raise ResourceError(lang.getstr("resources.notfound.error") + 
									"\n" + filename)
		# Create main data dir if it does not exist
		if not os.path.exists(datahome):
			try:
				os.makedirs(datahome)
			except Exception, exception:
				handle_error(UserWarning("Warning - could not create "
										 "directory '%s'" % datahome))
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
				sp.call(['osascript', '-e', 
						 'do shell script "%s" with administrator privileges' 
						 % ";".join(script).encode(fs_enc)])
		# Initialize & run
		if module == "3DLUT-maker":
			from wxLUT3DFrame import main
		elif module == "curve-viewer":
			from wxLUTViewer import main
		elif module == "profile-info":
			from wxProfileInfo import main
		elif module == "scripting-client":
			from wxScriptingClient import main
		elif module == "synthprofile":
			from wxSynthICCFrame import main
		elif module == "testchart-editor":
			from wxTestchartEditor import main
		elif module == "VRML-to-X3D-converter":
			from wxVRML2X3D import main
		elif module == "apply-profiles":
			from profile_loader import main
		else:
			from DisplayCAL import main
		main()
	except Exception, exception:
		if isinstance(exception, ResourceError):
			error = exception
		else:
			error = Error(u"Fatal error: " +
						  safe_unicode(traceback.format_exc()))
		handle_error(error)
		_exit(lockfilename, port)


def _exit(lockfilename, port):
	for process in mp.active_children():
		if not "Manager" in process.name:
			safe_print("Terminating zombie process", process.name)
			process.terminate()
			safe_print(process.name, "terminated")
	for thread in threading.enumerate():
		if (thread.isAlive() and thread is not threading.currentThread() and
			not thread.isDaemon()):
			safe_print("Waiting for thread %s to exit" % thread.getName())
			thread.join()
			safe_print(thread.getName(), "exited")
	if lockfilename and os.path.isfile(lockfilename):
		# Each lockfile may contain multiple ports of running instances
		try:
			with open(lockfilename) as lockfile:
				ports = lockfile.read().splitlines()
		except EnvironmentError, exception:
			safe_print("Warning - could not read lockfile %s: %r" %
					   (lockfilename, exception))
			ports = []
		else:
			# Remove ourself
			if port and str(port) in ports:
				ports.remove(str(port))

			# Determine if instances still running. If not still running,
			# remove from list of ports
			for i in reversed(xrange(len(ports))):
				try:
					port = int(ports[i])
				except ValueError:
					# This shouldn't happen
					continue
				appsocket = AppSocket()
				if not appsocket:
					break
				if not appsocket.connect("127.0.0.1", port):
					# Other instance probably died
					del ports[i]
				appsocket.close()
			if ports:
				# Write updated lockfile
				write_lockfile(lockfilename, "w", "\n".join(ports))
		# If no ports of running instances, ok to remove lockfile
		if not ports:
			try:
				os.remove(lockfilename)
			except EnvironmentError, exception:
				safe_print("Warning - could not remove lockfile %s: %r" %
						   (lockfilename, exception))
	safe_print("Exiting", pyname)


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


def write_lockfile(lockfilename, mode, contents):
	try:
		# Create lockfile
		with open(lockfilename, mode) as lockfile:
			lockfile.write("%s\n" % contents)
	except EnvironmentError, exception:
		# This shouldn't happen
		safe_print("Warning - could not write lockfile %s:" % lockfilename,
				   exception)


class AppSocket(object):

	def __init__(self):
		try:
			self.socket = socket.socket(socket.AF_INET,
										socket.SOCK_STREAM)
		except socket.error, exception:
			# This shouldn't happen
			safe_print("Warning - could not create TCP socket:", exception)

	def __getattr__(self, name):
		return getattr(self.socket, name)

	def __nonzero__(self):
		return hasattr(self, "socket")

	def connect(self, host, port):
		try:
			self.socket.connect((host, port))
		except socket.error, exception:
			# Other instance probably died
			safe_print("Connection to %s:%s failed:" % (host, port), exception)
			return False
		return True

	def read(self):
		incoming = ""
		while not "\4" in incoming:
			try:
				data = self.socket.recv(1024)
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				safe_print("Warning - could not receive data:", exception)
				break
			if not data:
				break
			incoming += data
		return incoming

	def send(self, data):
		try:
			self.socket.sendall(data + "\n")
		except socket.error, exception:
			# Connection lost?
			safe_print("Warning - could not send data %r:" % data, exception)
			return False
		return True


class Error(Exception):
	pass

if __name__ == "__main__":
	main()
