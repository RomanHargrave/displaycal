# -*- coding: utf-8 -*-

from __future__ import with_statement
from time import sleep
import atexit
import errno
import glob
import logging
import os
import platform
import socket
import sys
import subprocess as sp
import threading
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
from util_os import FileLock
from util_str import safe_str, safe_unicode
if sys.platform == "win32":
	from util_win import win_ver
	import ctypes


def _excepthook(etype, value, tb):
	handle_error((etype, value, tb))

sys.excepthook = _excepthook


def _main(module, name, applockfilename, probe_ports=True):
	# Allow multiple instances only for curve viewer, profile info,
	# scripting client, synthetic profile creator and testchart editor
	multi_instance = ("curve-viewer", "profile-info", "scripting-client",
					  "synthprofile", "testchart-editor")
	lock = AppLock(applockfilename, "a+", True, module in multi_instance)
	if not lock:
		# If a race condition occurs, do not start another instance
		safe_print("Not starting another instance.")
		return
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
	cafile = os.getenv("SSL_CERT_FILE")
	if cafile:
		safe_print("CA file", cafile)
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
	initcfg(module)
	host = "127.0.0.1"
	defaultport = getcfg("app.port")
	lock2pids_ports = {}
	opid = os.getpid()
	if probe_ports:
		# Check for currently used ports
		lockfilenames = glob.glob(os.path.join(confighome, "*.lock"))
		for lockfilename in lockfilenames:
			safe_print("Lockfile", lockfilename)
			try:
				if lock and lockfilename == applockfilename:
					lockfile = lock
					lock.seek(0)
				else:
					lockfile = AppLock(lockfilename, "r", True, True)
				if lockfile:
					if not lockfilename in lock2pids_ports:
						lock2pids_ports[lockfilename] = []
					for ln, line in enumerate(lockfile.read().splitlines(), 1):
						if ":" in line:
							# DisplayCAL >= 3.8.8.2 with localhost blocked
							pid, port = line.split(":", 1)
							if pid:
								try:
									pid = int(pid)
								except ValueError, exception:
									# This shouldn't happen
									safe_print("Warning - couldn't parse PID "
											   "as int: %r (%s line %i)" %
											   (pid, lockfilename, ln))
									pid = None
								else:
									safe_print("Existing client using PID", pid)
						else:
							# DisplayCAL <= 3.8.8.1 or localhost ok
							pid = None
							port = line
						if port:
							try:
								port = int(port)
							except ValueError, exception:
								# This shouldn't happen
								safe_print("Warning - couldn't parse port as int: %r "
										   "(%s line %i)" % (port, lockfilename, ln))
								port = None
							else:
								safe_print("Existing client using port", port)
						if pid or port:
							lock2pids_ports[lockfilename].append((pid, port))
				if not lock or lockfilename != applockfilename:
					lockfile.unlock()
			except EnvironmentError, exception:
				# This shouldn't happen
				safe_print("Warning - could not read lockfile %s:" %
						   lockfilename, exception)
		if module not in multi_instance:
			# Check lockfile(s) and probe port(s)
			for lockfilename in [applockfilename]:
				incoming = None
				pids_ports = lock2pids_ports.get(lockfilename)
				if pids_ports:
					pid, port = pids_ports[0]
					appsocket = AppSocket()
					if appsocket and port:
						safe_print("Connecting to %s..." % port)
						if appsocket.connect(host, port):
							safe_print("Connected to", port)
							# Other instance already running?
							# Get appname to check if expected app is actually
							# running under that port
							safe_print("Getting instance name")
							if appsocket.send("getappname"):
								safe_print("Sent scripting request, awaiting response...")
								incoming = appsocket.read().rstrip("\4")
								safe_print("Got response: %r" % incoming)
								if incoming:
									if incoming != pyname:
										incoming = None
								else:
									incoming = False
						while incoming:
							# Send args as UTF-8
							if module == "apply-profiles":
								# Always try to close currently running instance
								safe_print("Closing existing instance")
								cmd = "exit" if incoming == pyname else "close"
								data = [cmd]
								lock.unlock()
							else:
								# Send module/appname to notify running app
								safe_print("Notifying existing instance")
								data = [module or appname]
								if module != "3DLUT-maker":
									for arg in sys.argv[1:]:
										data.append(safe_str(safe_unicode(arg),
															 "UTF-8"))
							data = sp.list2cmdline(data)
							if appsocket.send(data):
								safe_print("Sent scripting request, awaiting response...")
								incoming = appsocket.read().rstrip("\4")
								safe_print("Got response: %r" % incoming)
								if module == "apply-profiles":
									if incoming == "":
										# Successfully sent our close request.
										incoming = "ok"
									elif incoming == "invalid" and cmd == "exit":
										# < 3.8.8.1 didn't have exit command
										continue
							break
						appsocket.close()
				else:
					pid = None
				if not incoming:
					if sys.platform == "win32":
						import pywintypes
						import win32ts
						try:
							osid = win32ts.ProcessIdToSessionId(opid)
						except pywintypes.error, exception:
							safe_print("Enumerating processes failed:",
									   exception)
							osid = None
						try:
							processes = win32ts.WTSEnumerateProcesses()
						except pywintypes.error, exception:
							safe_print("Enumerating processes failed:",
									   exception)
						else:
							appname_lower = appname.lower()
							exename_lower = exename.lower()
							if module:
								pyexe_lower = appname_lower + "-" + module + exe_ext
							else:
								pyexe_lower = appname_lower + exe_ext
							incoming = None
							for (sid, pid2, basename, usid) in processes:
								basename_lower = basename.lower()
								if ((pid and pid2 == pid and
									 basename_lower == exename_lower) or
									((osid is None or sid == osid) and
									 basename_lower == pyexe_lower)) and pid2 != opid:
									# Other instance running
									incoming = False
									if module == "apply-profiles":
										if not os.path.isfile(lockfilename):
											# Create dummy lockfile
											try:
												with open(lockfilename, "w"):
													pass
											except EnvironmentError, exception:
												safe_print("Warning - could "
														   "not create dummy "
														   "lockfile %s: %r" %
														   (lockfilename,
														    exception))
											else:
												safe_print("Warning - had to "
														   "create dummy "
														   "lockfile",
														   lockfilename)
										safe_print("Closing existing instance "
												   "with PID", pid2)
										startupinfo = sp.STARTUPINFO()
										startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
										startupinfo.wShowWindow = sp.SW_HIDE
										lock.unlock()
										try:
											p = sp.Popen(["taskkill", "/PID",
														  "%s" % pid2],
														 stdin=sp.PIPE,
														 stdout=sp.PIPE,
														 stderr=sp.STDOUT,
														 startupinfo=startupinfo)
											stdout, stderr = p.communicate()
										except Exception, exception:
											safe_print(exception)
										else:
											safe_print(stdout)
											if not p.returncode:
												# Successfully sent our close
												# request.
												incoming = "ok"
				if incoming == "ok":
					# Successfully sent our request
					if module == "apply-profiles":
						# Wait for lockfile to be removed, in which case
						# we know the running instance has successfully
						# closed.
						safe_print("Waiting for existing instance to exit and "
								   "delete lockfile", lockfilename)
						while os.path.isfile(lockfilename):
							sleep(.05)
						lock.lock()
						safe_print("Existing instance exited.")
						incoming = None
						if lockfilename in lock2pids_ports:
							del lock2pids_ports[lockfilename]
					break
			if incoming is not None:
				# Other instance running?
				import localization as lang
				lang.init()
				if incoming == "ok":
					# Successfully sent our request
					safe_print(lang.getstr("app.otherinstance.notified"))
				elif module == "apply-profiles":
					safe_print("Not starting another instance.")
				else:
					# Other instance busy?
					handle_error(lang.getstr("app.otherinstance", name))
				# Exit
				return
	# Use exclusive lock during app startup
	with lock:
		# Create listening socket
		appsocket = AppSocket()
		if appsocket:
			if sys.platform != "win32":
				# https://docs.microsoft.com/de-de/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse#using-so_reuseaddr
				# From the above link: "The SO_REUSEADDR socket option allows 
				# a socket to forcibly bind to a port in use by another socket".
				# Note that this is different from the behavior under Linux/BSD,
				# where a socket can only be (re-)bound if no active listening
				# socket is already bound to the address.
				# Consequently, we don't use SO_REUSEADDR under Windows.
				appsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sys._appsocket = appsocket.socket
			if getcfg("app.allow_network_clients"):
				host = ""
			used_ports = [pid_port[1] for pids_ports in lock2pids_ports.values() for pid_port in pids_ports]
			candidate_ports = [0]
			if not defaultport in used_ports:
				candidate_ports.insert(0, defaultport)
			for port in candidate_ports:
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
					sys._appsocket_port = port
					break
		if not hasattr(sys, "_appsocket_port"):
			port = ""
		lock.seek(0)
		if module not in multi_instance:
			lock.truncate(0)
		if not port:
			lock.write("%s:%s" % (opid, port))
		else:
			lock.write(port)
		atexit.register(lambda: safe_print("Ran application exit handlers"))
		from wxwindows import BaseApp
		BaseApp.register_exitfunc(_exit, applockfilename, port)
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
	# Run main after releasing lock
	main()


def main(module=None):
	mp.freeze_support()
	if mp.current_process().name != "MainProcess":
		return
	if module:
		name = "%s-%s" % (appbasename, module)
	else:
		name = appbasename
	applockfilename = os.path.join(confighome, "%s.lock" % name)
	try:
		_main(module, name, applockfilename)
	except Exception, exception:
		if isinstance(exception, ResourceError):
			error = exception
		else:
			error = Error(u"Fatal error: " +
						  safe_unicode(exception))
		handle_error(error)
		_exit(applockfilename, getattr(sys, "_appsocket_port", ""))


def _exit(lockfilename, oport):
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
		with AppLock(lockfilename, "r+", True, True) as lock:
			_update_lockfile(lockfilename, oport, lock)
	safe_print("Exiting", pyname)


def _update_lockfile(lockfilename, oport, lock):
	if lock:
		# Each lockfile may contain multiple ports of running instances
		try:
			pids_ports = lock.read().splitlines()
		except EnvironmentError, exception:
			safe_print("Warning - could not read lockfile %s: %r" %
					   (lockfilename, exception))
			filtered_pids_ports = []
		else:
			opid = os.getpid()

			# Determine if instances still running. If not still running,
			# remove from list of ports
			for i in reversed(xrange(len(pids_ports))):
				pid_port = pids_ports[i]
				if ":" in pid_port:
					# DisplayCAL >= 3.8.8.2 with localhost blocked
					pid, port = pid_port.split(":", 1)
					if pid:
						try:
							pid = int(pid)
						except ValueError:
							# This shouldn't happen
							pid = None
				else:
					# DisplayCAL <= 3.8.8.1 or localhost ok
					pid = None
					port = pid_port
				if port:
					try:
						port = int(port)
					except ValueError:
						# This shouldn't happen
						continue
				if (pid and pid == opid and not port) or (port and port == oport):
					# Remove ourself
					pids_ports[i] = ""
					continue
				if not port:
					continue
				appsocket = AppSocket()
				if not appsocket:
					break
				if not appsocket.connect("127.0.0.1", port):
					# Other instance probably died
					pids_ports[i] = ""
				appsocket.close()
			# Filtered PIDs & ports (only used for checking)
			filtered_pids_ports = filter(lambda pid_port: pid_port, pids_ports)
			if filtered_pids_ports:
				# Write updated lockfile
				try:
					lock.seek(0)
					lock.truncate(0)
				except EnvironmentError, exception:
					safe_print("Warning - could not update lockfile %s: %r" %
							   (lockfilename, exception))
				else:
					lock.write("\n".join(pids_ports))
			else:
				lock.close()
				try:
					os.remove(lockfilename)
				except EnvironmentError, exception:
					safe_print("Warning - could not remove lockfile %s: %r" %
							   (lockfilename, exception))

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


class AppLock(object):

	def __init__(self, lockfilename, mode, exclusive=False, blocking=False):
		self._lockfilename = lockfilename
		self._mode = mode
		self._lockfile = None
		self._lock = None
		self._exclusive = exclusive
		self._blocking = blocking
		self.lock()

	def __enter__(self):
		return self

	def __exit__(self, etype, value, traceback):
		self.unlock()

	def __getattr__(self, name):
		return getattr(self._lockfile, name)

	def __iter__(self):
		return self._lockfile

	def __nonzero__(self):
		return bool(self._lock)

	def lock(self):
		lockdir = os.path.dirname(self._lockfilename)
		try:
			if not os.path.isdir(lockdir):
				os.makedirs(lockdir)
			# Create lockfile
			self._lockfile = open(self._lockfilename, self._mode)
		except EnvironmentError, exception:
			# This shouldn't happen
			safe_print("Error - could not open lockfile %s:" % self._lockfilename,
					   exception)
		else:
			try:
				self._lock = FileLock(self._lockfile, self._exclusive,
									  self._blocking)
			except FileLock.LockingError, exception:
				pass
			except EnvironmentError, exception:
				# This shouldn't happen
				safe_print("Error - could not lock lockfile %s:" %
						   self._lockfile.name, exception)
			else:
				return True
		return False

	def unlock(self):
		if self._lockfile:
			try:
				self._lockfile.close()
			except EnvironmentError, exception:
				# This shouldn't happen
				safe_print("Error - could not close lockfile %s:" %
						   self._lockfile.name, exception)
		if self._lock:
			try:
				self._lock.unlock()
			except FileLock.UnlockingError, exception:
				# This shouldn't happen
				safe_print("Warning - could not unlock lockfile %s:" %
						   self._lockfile.name, exception)

	def write(self, contents):
		if self._lockfile:
			try:
				self._lockfile.write("%s\n" % contents)
			except EnvironmentError, exception:
				# This shouldn't happen
				safe_print("Error - could not write to lockfile %s:" %
						   self._lockfile.name, exception)


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
