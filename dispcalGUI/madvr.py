# -*- coding: utf-8 -*-

# See developers/interfaces/madTPG.h in the madVR package

from __future__ import with_statement
from ConfigParser import RawConfigParser
from StringIO import StringIO
from time import sleep
from zlib import crc32
import ctypes
import errno
import getpass
import os
import platform
import socket
import struct
import sys
import threading
if sys.platform == "win32":
	import _winreg

if sys.platform == "win32":
	import win32api

import localization as lang
from log import safe_print as log_safe_print
from meta import name as appname, version
from ordereddict import OrderedDict
from util_str import safe_str, safe_unicode


min_version = (0, 87, 14, 0)


# Search for madTPG on the local PC, connect to the first found instance
CM_ConnectToLocalInstance = 0
# Search for madTPG on the LAN, connect to the first found instance
CM_ConnectToLanInstance = 1
# Start madTPG on the local PC and connect to it
CM_StartLocalInstance = 2
# Search local PC and LAN, and let the user choose which instance to connect to
CM_ShowListDialog = 3
# Let the user enter the IP address of a PC which runs madTPG, then connect
CM_ShowIpAddrDialog = 4
# fail immediately
CM_Fail = 5


_methodnames = ("ConnectEx", "Disable3dlut", "Enable3dlut",
				"GetBlackAndWhiteLevel", "GetDeviceGammaRamp",
				"GetSelected3dlut", "GetVersion",
				"IsDisableOsdButtonPressed",
				"IsStayOnTopButtonPressed",
				"IsUseFullscreenButtonPressed",
				"SetDisableOsdButton",
				"SetDeviceGammaRamp", "SetOsdText",
				"GetPatternConfig", "SetPatternConfig",
				"ShowProgressBar", "SetProgressBarPos",
				"SetSelected3dlut", "SetStayOnTopButton",
				"SetUseFullscreenButton", "ShowRGB",
				"ShowRGBEx", "Load3dlutFile", "Disconnect",
				"Quit", "Load3dlutFromArray256")


_lock = threading.RLock()

def safe_print(*args):
	with _lock:
		log_safe_print(*args)


class H3DLUT(object):

	""" 3D LUT file format used by madVR """

	# https://sourceforge.net/projects/thr3dlut

	def __init__(self, filename):
		with open(filename, "rb") as lut:
			data = lut.read()
		self.signature = data[:4]
		self.fileVersion = struct.unpack("<l", data[4:8])[0]
		self.programName = data[8:40].rstrip("\0")
		self.programVersion = struct.unpack("<q", data[40:48])[0]
		self.inputBitDepth = struct.unpack("<3l", data[48:60])
		self.inputColorEncoding = struct.unpack("<l", data[60:64])[0]
		self.outputBitDepth = struct.unpack("<l", data[64:68])[0]
		self.outputColorEncoding = struct.unpack("<l", data[68:72])[0]
		self.parametersFileOffset = struct.unpack("<l", data[72:76])[0]
		self.parametersSize = struct.unpack("<l", data[76:80])[0]
		self.lutFileOffset = struct.unpack("<l", data[80:84])[0]
		self.lutCompressionMethod = struct.unpack("<l", data[84:88])[0]
		if self.lutCompressionMethod != 0:
			raise ValueError("Compression method not supported: %i" %
							 self.lutCompressionMethod)
		self.lutCompressedSize = struct.unpack("<l", data[88:92])[0]
		self.lutUncompressedSize = struct.unpack("<l", data[92:96])[0]
		self.parametersData = data[self.parametersFileOffset:
								   self.parametersFileOffset +
								   self.parametersSize]
		self.LUTDATA = data[self.lutFileOffset:
							self.lutFileOffset + self.lutCompressedSize]
		if len(self.LUTDATA) != self.lutCompressedSize:
			raise ValueError("3DLUT size %i does not match expected size %i" %
							 (len(self.LUTDATA), self.lutCompressedSize))
		if len(data) == self.lutFileOffset + self.lutCompressedSize + 1552:
			# Calibration appendended
			self.LUTDATA += data[self.lutFileOffset + self.lutCompressedSize:
								 self.lutFileOffset + self.lutCompressedSize +
								 1552]
			self.lutCompressedSize += 1552
			self.lutUncompressedSize += 1552


class MadTPG(object):

	""" Minimal madTPG controller class """

	def __init__(self):
		# We only expose stuff we might actually use.

		# Find madHcNet32.dll
		clsid = "{E1A8B82A-32CE-4B0D-BE0D-AA68C772E423}"
		try:
			key = _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT,
								  r"CLSID\%s\InprocServer32" % clsid)
			value, valuetype = _winreg.QueryValueEx(key, "")
		except:
			raise RuntimeError(lang.getstr("madvr.not_found"))
		self.dllpath = os.path.join(os.path.split(value)[0], "madHcNet32.dll")
		if not value or not os.path.isfile(self.dllpath):
			raise OSError(lang.getstr("not_found", self.dllpath))
		handle = win32api.LoadLibrary(self.dllpath)
		self.mad = ctypes.WinDLL(self.dllpath, handle=handle)

		try:
			# Set expected return value types
			for methodname in _methodnames:
				getattr(self.mad, "madVR_%s" % methodname).restype = ctypes.c_bool

			# Set expected argument types
			self.mad.madVR_ShowRGB.argtypes = [ctypes.c_double] * 3
			self.mad.madVR_ShowRGBEx.argtypes = [ctypes.c_double] * 6
		except AttributeError:
			raise RuntimeError(lang.getstr("madhcnet.outdated",
										   tuple(reversed(os.path.split(self.dllpath))) +
										   min_version))

	def __del__(self):
		if hasattr(self, "mad"):
			self.disconnect()

	def __getattr__(self, name):
		# Instead of writing individual method wrappers, we use Python's magic
		# to handle this for us. Note that we're sticking to pythonic method
		# names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

		# Convert from pythonic method name to CamelCase
		methodname = "".join(part.capitalize() for part in name.split("_"))

		# Check if this is a madVR method we support
		if methodname not in _methodnames:
			raise AttributeError("%r object has no attribute %r" %
								 (self.__class__.__name__, name))

		# Call the method and return the result
		return getattr(self.mad, "madVR_%s" % methodname)

	def connect(self, method1=CM_ConnectToLocalInstance, timeout1=1000,
				method2=CM_ConnectToLanInstance, timeout2=3000,
				method3=CM_ShowListDialog, timeout3=0, method4=CM_Fail,
				timeout4=0, parentwindow=None):
		""" Find, select or launch a madTPG instance and connect to it """
		return self.mad.madVR_ConnectEx(method1, timeout1, method2, timeout2,
										method3, timeout3, method4, timeout4,
										parentwindow)

	def get_black_and_white_level(self):
		""" Return madVR output level setup """
		blacklvl, whitelvl = ctypes.c_long(), ctypes.c_long()
		result = self.mad.madVR_GetBlackAndWhiteLevel(*[ctypes.byref(v) for v in
														(blacklvl, whitelvl)])
		return result and (blacklvl.value, whitelvl.value)

	def get_device_gamma_ramp(self):
		""" Calls the win32 API 'GetDeviceGammaRamp' """
		ramp = ((ctypes.c_ushort * 256) * 3)()
		result = self.mad.madVR_GetDeviceGammaRamp(ramp)
		return result and ramp

	def get_pattern_config(self):
		"""
		Return the pattern config as 4-tuple
		
		Pattern area in percent        1-100
		Background level in percent    0-100
		Background mode                0 = constant gray
		                               1 = APL - gamma light
		                               2 = APL - linear light
		Black border width in pixels   0-100
		"""
		area, bglvl, bgmode, border = [ctypes.c_long() for i in xrange(4)]
		result = self.mad.madVR_GetPatternConfig(*[ctypes.byref(v) for v in
												   (area, bglvl, bgmode,
												    border)])
		return result and (area.value, bglvl.value, bgmode.value, border.value)

	def get_selected_3dlut(self):
		thr3dlut = ctypes.c_ulong()
		result = self.mad.madVR_GetSelected3dlut(ctypes.byref(thr3dlut))
		return result and thr3dlut

	def get_version(self):
		version = ctypes.c_ulong()
		result = self.mad.madVR_GetVersion(ctypes.byref(version))
		version = tuple(struct.unpack(">B", c)[0] for c in
						struct.pack(">I", version.value))
		return result and version

	def show_rgb(self, r, g, b, bgr=None, bgg=None, bgb=None):
		""" Shows a specific RGB color test pattern """
		if not None in (bgr, bgg, bgb):
			return self.mad.madVR_ShowRGBEx(r, g, b, bgr, bgg, bgb)
		else:
			return self.mad.madVR_ShowRGB(r, g, b)

	@property
	def uri(self):
		return self.dllpath


class MadTPG_Net(object):

	""" Implementation of madVR network protocol in pure python """

	# FIXME/NOTE this isn't working yet

	# Wireshark filter to help ananlyze traffic:
	# (tcp.dstport != 1900 and tcp.dstport != 443) or (udp.dstport != 1900 and udp.dstport != 137 and udp.dstport != 138 and udp.dstport != 5355 and udp.dstport != 547 and udp.dstport != 10111)

	def __init__(self, host=None, port=60562, debug=0):
		self._broadcast_sockets = {}
		self._casts = []
		self._conn_sockets = {}
		self._instance = 0
		self._multicast_sockets = {}
		self._pid = 0
		self._reset()
		self._server_sockets = {}
		self._threads = []
		#self.broadcast_ports = (39568, 41513, 45817, 48591, 48912)
		self.broadcast_ports = (37018, 10658, 63922, 53181, 4287)
		self.clients = {}
		self.port = port
		self.ports = (port, )
		self.debug = debug
		self.host = host or socket.gethostbyname(socket.gethostname())
		self.listening = False
		#self.multicast_ports = (34761, )
		self.multicast_ports = (51591, )
		self._event_handlers = {"on_client_added": [],
								"on_client_removed": []}
		#self.server_ports = (37612, 43219, 47815, 48291, 48717)
		self.server_ports = (60562, 51130, 54184, 41916, 19902)
		ip = self.host.split(".")
		ip.pop()
		ip.append("255")
		self.broadcast_ip = ".".join(ip)
		self.multicast_ip = "235.117.220.191"

	def listen(self):
		if self.listening:
			return
		self.listening = True
		# Connection listen sockets
		for port in self.server_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.settimeout(1)
			try:
				sock.bind(("", port))
				sock.listen(1)
				self._server_sockets[("", port)] = sock
				thread = threading.Thread(target=self._conn_accept_handler,
										  args=(sock, "", port))
				self._threads.append(thread)
				thread.start()
			except socket.error, exception:
				safe_print("MadTPG_Net: TCP Port %i: %s" % (port, exception))
		# Broadcast listen sockets
		for port in self.broadcast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			sock.settimeout(0)
			try:
				sock.bind(("", port))
				self._broadcast_sockets[(self.broadcast_ip, port)] = sock
				thread = threading.Thread(target=self._cast_receive_handler,
										  args=(sock, self.broadcast_ip, port))
				self._threads.append(thread)
				thread.start()
			except socket.error, exception:
				safe_print("MadTPG_Net: UDP Port %i: %s" % (port, exception))
		# Multicast listen socket
		for port in self.multicast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
							struct.pack("4sl",
										socket.inet_aton(self.multicast_ip),
										socket.INADDR_ANY))
			sock.settimeout(0)
			try:
				sock.bind(("", port))
				self._multicast_sockets[(self.multicast_ip, port)] = sock
				thread = threading.Thread(target=self._cast_receive_handler,
										  args=(sock, self.multicast_ip, port))
				self._threads.append(thread)
				thread.start()
			except socket.error, exception:
				safe_print("MadTPG_Net: UDP Port %i: %s" % (port, exception))

	def bind(self, event_name, handler):
		""" Bind a handler to an event """
		if not event_name in self._event_handlers:
			self._event_handlers[event_name] = []
		self._event_handlers[event_name].append(handler)

	def unbind(self, event_name, handler=None):
		"""
		Unbind (remove) a handler from an event
		
		If handler is None, remove all handlers for the event.
		
		"""
		if event_name in self._event_handlers:
			if handler in self._event_handlers[event_name]:
				self._event_handlers[event_name].remove(handler)
				return handler
			else:
				return self._event_handlers.pop(event_name)

	def _dispatch_event(self, event_name, event_data=None):
		""" Dispatch events """
		if self.debug:
			safe_print("MadTPG_Net: Dispatching", event_name)
		for handler in self._event_handlers.get(event_name, []):
			handler(event_data)

	def _reset(self):
		self._client_socket = None
		self._command = None
		self._commandno = 0
		self._conn_confirmed = False
		self._madtpg_hello_received = False
		self._mvrversion = False

	def _conn_accept_handler(self, sock, host, port):
		if self.debug:
			safe_print("MadTPG_Net: Entering incoming connection thread for port",
					   port)
		while self and getattr(self, "listening", False):
			try:
				# Wait for connection
				conn, addr_port = sock.accept()
			except socket.timeout, exception:
				sleep(.05)
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				safe_print("MadTPG_Net: Exception in incoming connection "
						   "thread for %s:%i:" % addr_port, exception)
				break
			if self.debug:
				safe_print("MadTPG_Net: Incoming connection from %s:%s" %
						   addr_port)
			conn.settimeout(0)
			if addr_port in self._conn_sockets:
				if self.debug:
					safe_print("MadTPG_Net: Ignoring connection from %s:%s" %
							   addr_port)
			else:
				self._conn_sockets[addr_port] = conn
				thread = threading.Thread(target=self._receive_handler,
										  args=(conn, ) + addr_port)
				self._threads.append(thread)
				thread.start()
		try:
			# Will fail if the socket isn't connected, i.e. if there
			# was an error during the call to connect()
			sock.shutdown(socket.SHUT_RDWR)
		except socket.error, exception:
			if exception.errno != errno.ENOTCONN:
				safe_print("MadTPG_Net: Disconnect:", exception)
		sock.close()
		if self.debug:
			safe_print("MadTPG_Net: Exiting incoming connection thread for port",
					   port)

	def _receive_handler(self, conn, addr, port):
		if self.debug:
			safe_print("MadTPG_Net: Entering receiver thread for %s:%s" %
					   (addr, port))
		while self and getattr(self, "listening", False):
			# Wait for incoming message
			try:
				incoming = conn.recv(4096)
			except socket.timeout, exception:
				safe_print("MadTPG_Net: In receiver thread for %s:%i:" %
						   (addr, port), exception)
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				if exception.errno != errno.ECONNRESET or self.debug:
					safe_print("MadTPG_Net: In receiver thread for %s:%i:" %
							   (addr, port), exception)
				break
			else:
				if not incoming:
					# Connection closed
					break
				with _lock:
					if self.debug:
						safe_print("MadTPG_Net: Received from %s:%s" %
								   (addr, port))
					self._client_socket = conn
					ohost = self.host
					oport = self.port
					self.host = addr
					self.port = port
					result = self._expect_hello(incoming)
					if self.debug:
						safe_print("MadTPG_Net: Result =", repr(result))
					self._client_socket = None
					self.host = ohost
					self.port = oport
					if result in ("Stopped", False, None):
						if self.debug:
							safe_print("MadTPG_Net: Client %s PID %i disconnected" %
									   (addr, self._pid))
						self._remove_client(addr, self._pid)
						break
		for addr_port, sock in self._conn_sockets.items():
			if sock is conn:
				self._conn_sockets.pop(addr_port)
		try:
			# Will fail if the socket isn't connected, i.e. if there
			# was an error during the call to connect()
			conn.shutdown(socket.SHUT_RDWR)
		except socket.error, exception:
			if exception.errno != errno.ENOTCONN:
				safe_print("MadTPG_Net: In receiver thread for %s:%i:" %
						   (addr, port), exception)
		conn.close()
		if self.debug:
			safe_print("MadTPG_Net: Exiting receiver thread for %s:%s" %
					   (addr, port))

	def _remove_client(self, addr, pid):
		for host_pid, client in self.clients.items():
			if (addr, pid) == host_pid:
				self.clients.pop(host_pid)
				if self.debug:
					safe_print("MadTPG_Net: Removed client %s PID %i" %
							   host_pid)
				self._dispatch_event("on_client_removed", (addr, pid))

	def _cast_receive_handler(self, sock, host, port):
		if (host, port) in self._broadcast_sockets:
			cast = "broadcast"
		elif (host, port) in self._multicast_sockets:
			cast = "multicast"
		else:
			cast = "unknown"
		if self.debug:
			safe_print("MadTPG_Net: Entering receiver thread for %s port %i" %
					   (cast, port))
		while self and getattr(self, "listening", False):
			try:
				data, (srcaddr, srcport) = sock.recvfrom(4096)
			except socket.timeout, exception:
				safe_print("MadTPG_Net: In receiver thread for %s port %i:" %
						   (cast, port), exception)
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				if exception.errno != errno.ECONNRESET or self.debug:
					safe_print("MadTPG_Net: In receiver thread for %s port %i:" %
							   (cast, port), exception)
				break
			else:
				with _lock:
					if self.debug:
						safe_print("MadTPG_Net: Received %s from %s:%s: %r" %
								   (cast, srcaddr, srcport, data))
					if not (srcaddr, srcport) in self._casts:
						if (not (srcaddr, self.port) in self._conn_sockets and
							srcaddr != self.host):
							ohost = self.host
							self.host = srcaddr
							if self.connect(start=False):
								if self.debug:
									safe_print("MadTPG_Net: Connected to %s:%s" %
											   (srcaddr, self.port))
								thread = threading.Thread(target=self._receive_handler,
														  args=(self._client_socket,
															    srcaddr, self.port))
								self._threads.append(thread)
								thread.start()
							else:
								safe_print("MadTPG_Net: Connecting to %s:%s failed" %
										   (srcaddr, self.port))
							self._reset()
							self.host = ohost
						elif self.debug:
							safe_print("MadTPG_Net: Already connected to %s:%s" %
									   (srcaddr, self.port))
					elif self.debug:
						safe_print("MadTPG_Net: Ignoring own %s from %s:%s" %
								   (cast, srcaddr, srcport))
		if self.debug:
			safe_print("MadTPG_Net: Exiting %s receiver thread for port %i" %
					   (cast, port))

	def __del__(self):
		self.shutdown()

	def shutdown(self, socketgroups=None):
		self.listening = False
		while self._threads:
			thread = self._threads.pop()
			if thread.isAlive():
				thread.join()
		if not socketgroups:
			socketgroups = (self._broadcast_sockets, self._conn_sockets,
							self._multicast_sockets)
		for sockets in socketgroups:
			for host_port, sock in sockets.items():
				sockets.pop(host_port)
				if sock is self._client_socket:
					continue
				try:
					# Will fail if the socket isn't connected, i.e. if there
					# was an error during the call to connect()
					sock.shutdown(socket.SHUT_RDWR)
				except socket.error, exception:
					if exception.errno != errno.ENOTCONN:
						safe_print("MadTPG_Net: Shutdown socket for %s:%i:" % host_port,
								   exception)
				sock.close()
		self.disconnect()

	def __getattr__(self, name):
		# Instead of writing individual method wrappers, we use Python's magic
		# to handle this for us. Note that we're sticking to pythonic method
		# names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

		# Convert from pythonic method name to CamelCase
		methodname = "".join(part.capitalize() for part in name.split("_"))

		if methodname == "ShowRgb":
			methodname = "ShowRGB"

		# Check if this is a madVR method we support
		if methodname not in _methodnames:
			raise AttributeError("%r object has no attribute %r" %
								 (self.__class__.__name__, name))

		# Call the method and return the result
		return MadTPG_Net_Sender(self, methodname)

	def announce(self):
		""" Anounce ourselves """
		for port in self.multicast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
			sock.settimeout(1)
			sock.connect((self.multicast_ip, port))
			srcaddr, srcport = sock.getsockname()
			self._casts.append((srcaddr, srcport))
			if self.debug:
				safe_print("MadTPG_Net: Sending multicast from %s:%s to port %i" %
						   (srcaddr, srcport, port))
			sock.sendall(struct.pack("<i", 0))
			sock.close()
		for port in self.broadcast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			sock.settimeout(1)
			sock.connect((self.broadcast_ip, port))
			srcaddr, srcport = sock.getsockname()
			self._casts.append((srcaddr, srcport))
			if self.debug:
				safe_print("MadTPG_Net: Sending broadcast from %s:%s to port %i" %
						   (srcaddr, srcport, port))
			sock.sendall(struct.pack("<i", 0))
			sock.close()

	def connect(self, method1=None, timeout1=1000,
				method2=None, timeout2=3000,
				method3=None, timeout3=0, method4=CM_Fail,
				timeout4=0, parentwindow=None, start=True):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(timeout2)
		returnvalue = False
		if self.debug:
			safe_print("MadTPG_Net: Connecting to %s:%s..." %
					   (self.host, self.port))
		try:
			sock.connect((self.host, self.port))
		except socket.error, exception:
			if start or self.debug:
				safe_print("MadTPG_Net: Connecting to %s:%s failed:" %
						   (self.host, self.port), exception)
		else:
			sock.settimeout(0)
			self._client_socket = sock
			self._conn_sockets[sock.getpeername()] = sock
			self._conn_sockets[sock.getsockname()] = sock
			if self.hello():
				incoming = self._expect_hello()
				if start:
					for i in xrange(2):
						# Retrieve madVR packets until madTPG GraphState was
						# received
						if incoming in ("Paused", "Running", False, None):
							break
						if self.debug:
							safe_print("MadTPG_Net: Expecting GraphState (%i)" %
									   (i + 1))
						incoming = self._process(timeout=timeout2)
					if incoming in ("Paused", "Running"):
						# Successfully connected & received GraphState
						# Start test pattern
						returnvalue = self._send("StartTestPattern")
				else:
					returnvalue = self._madtpg_hello_received
			if start and not returnvalue:
				self.disconnect(False)
		return returnvalue

	def disconnect(self, stop=True):
		returnvalue = False
		if self._client_socket:
			returnvalue = True
			if stop:
				returnvalue = self._send("StopTestPattern")
			if self.debug:
				safe_print("MadTPG_Net: Disconnecting from %s:%s" %
						   (self.host, self.port))
			try:
				# Will fail if the socket isn't connected, i.e. if there
				# was an error during the call to connect()
				self._client_socket.shutdown(socket.SHUT_RDWR)
			except socket.error, exception:
				if exception.errno != errno.ENOTCONN:
					safe_print("MadTPG_Net: Disconnect:", exception)
			self._client_socket.close()
			for addr_port, sock in self._conn_sockets.items():
				if sock is self._client_socket:
					self._conn_sockets.pop(addr_port)
		self._reset()
		return returnvalue

	def _process(self, blob="", timeout=1):
		""" Process madVR packets """
		if self._client_socket:
			blob = self._get(blob, timeout)
		if blob is False:
			returnvalue = False
		else:
			returnvalue = None
		while blob:
			try:
				record, blob = self._parse(blob)
			except ValueError, exception:
				safe_print("MadTPG_Net:", exception)
				break
			pid = record["processId"]
			self._pid = pid
			component = record["component"]
			instance = record["instance"]
			command = record["command"]
			params = record["params"]
			if command == "reply" and record["commandNo"] == self._commandno:
				if self._command == "GetBlackAndWhiteLevel":
					if len(params) == 8:
						returnvalue = struct.unpack("<ii", params)
				elif self._command == "GetPatternConfig":
					if len(params) == 16:
						returnvalue = struct.unpack("<iiii", params)
				elif self._command in ("GetSelected3dlut", ):
					if len(params) == 4:
						returnvalue = struct.unpack("<i", params[0:4])[0]
				else:
					returnvalue = params
				if returnvalue == "+":
					returnvalue = True
				elif returnvalue == "-":
					returnvalue = False
			elif command == "confirm":
				self._conn_confirmed = returnvalue = True
			elif command == "hello":
				if (params.get("exeFile", "").lower() == "madtpg.exe" or
					component == "madTPG"):
					client = OrderedDict()
					client["processId"] = pid
					client["module"] = record["module"]
					if component == "madTPG":
						self._instance = instance
						self._madtpg_hello_received = True
						client["instance"] = instance
					client.update(params)
					if "mvrVersion" in params:
						self._mvrversion = tuple(int(v) for v in
												 params["mvrVersion"].split("."))
					if (self.host, pid) not in self.clients:
						self.clients[(self.host, pid)] = client
						self._dispatch_event("on_client_added",
											 (self.host, pid))
					else:
						client_copy = self.clients[(self.host, pid)].copy()
						self.clients[(self.host, pid)].update(client)
						if self.clients[(self.host, pid)] != client_copy:
							self._dispatch_event("on_client_updated",
												 (self.host, pid))
				returnvalue = params
			elif command.startswith("store:"):
				returnvalue = params
			elif command == "bye":
				returnvalue = False
		return returnvalue

	def get_version(self):
		""" Return madVR version """
		return self._mvrversion

	def _assemble_hello_params(self):
		""" Assemble 'hello' packet parameters """
		info = [("computerName", safe_unicode(socket.gethostname().upper())),
				("userName", safe_unicode(getpass.getuser())),
				("os", "%s %s" % (platform.system(), platform.release())),
				("exeFile", os.path.basename(sys.executable)), ("exeVersion",
															    version),
				("exeDescr", ""), ("exeIcon", "")]
		params = ""
		for key, value in info:
			params += ("%s=%s\t" % (key, value)).encode("UTF-16-LE", "replace")
		return params

	def hello(self):
		""" Send 'hello' packet. Return boolean wether send succeeded or not """
		params = self._assemble_hello_params()
		return self._send("hello", params, "")

	def _expect_hello(self, blob=""):
		""" Retrieve madVR packets until madTPG 'hello' was received """
		self._madtpg_hello_received = False
		if self.debug:
			safe_print("MadTPG_Net: Expecting hello (1)")
		returnvalue = self._process(blob)
		for i in xrange(4):
			# Wait for incoming madTPG hello
			if returnvalue in (False, None) or self._madtpg_hello_received:
				break
			if self.debug:
				safe_print("MadTPG_Net: Expecting hello (%i)" % (i + 2))
			incoming = self._process()
			if incoming is None:
				break
			else:
				returnvalue = incoming
		return returnvalue

	def _get(self, blob="", timeout=1):
		""" Retrieve madVR packets """
		if self.debug:
			safe_print("MadTPG_Net: Receiving from %s:%s" % (self.host,
															 self.port))
		while len(blob) < 12:
			try:
				buffer = self._client_socket.recv(4096)
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					if timeout > 0:
						sleep(.05)
						timeout -= .05
						continue
					if self.debug:
						safe_print("MadTPG_Net: Finished receiving")
					return blob
				if exception.errno != errno.ECONNRESET or self.debug:
					safe_print("MadTPG_Net: Receive failed:", exception)
				return False
			if not buffer:
				return False
			blob += buffer
		crc = struct.unpack("<I", blob[8:12])[0]
		# Check CRC
		check = crc32(blob[:8]) & 0xFFFFFFFF
		if check != crc:
			if self.debug:
				safe_print("MadTPG_Net: Invalid madVR packet: CRC check "
						   "failed: Expected %i, got %i" % (crc, check))
			return False
		datalen = struct.unpack("<i", blob[4:8])[0]
		while len(blob) < datalen + 12:
			try:
				buffer = self._client_socket.recv(4096)
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					if timeout > 0:
						sleep(.05)
						timeout -= .05
						continue
					if self.debug:
						safe_print("MadTPG_Net: Finished receiving")
					return blob
				if exception.errno != errno.ECONNRESET or self.debug:
					safe_print("MadTPG_Net: Receive failed:", exception)
				return False
			if not buffer:
				return False
			blob += buffer
		if self.debug:
			safe_print("MadTPG_Net: Finished receiving")
		return blob

	def _parse(self, blob=""):
		""" Parse blob into record, return remaining blob """
		record = OrderedDict([("magic", blob[0:4]),
							  ("len", struct.unpack("<i", blob[4:8])[0]),
							  ("crc", struct.unpack("<i", blob[8:12])[0]),
							  ("processId",
							   struct.unpack("<i", blob[12:16])[0]),
							  ("module", struct.unpack("<q", blob[16:24])[0]),
							  ("commandNo",
							   struct.unpack("<i", blob[24:28])[0]),
							  ("sizeOfComponent",
							   struct.unpack("<i", blob[28:32])[0])])
		a = 32
		b = a + record["sizeOfComponent"]
		if b > len(blob):
			raise ValueError("Corrupt madVR packet: Expected component "
							 "len %i, got %i" % (b - a, len(blob[a:b])))
		record["component"] = blob[a:b]
		a = b + 8
		if a > len(blob):
			raise ValueError("Corrupt madVR packet: Expected instance "
							 "len %i, got %i" % (a - b, len(blob[b:a])))
		record["instance"] = struct.unpack("<q", blob[b:a])[0]
		b = a + 4
		if b > len(blob):
			raise ValueError("Corrupt madVR packet: Expected sizeOfCommand "
							 "len %i, got %i" % (b - a, len(blob[a:b])))
		record["sizeOfCommand"] = struct.unpack("<i", blob[a:b])[0]
		a = b + record["sizeOfCommand"]
		if a > len(blob):
			raise ValueError("Corrupt madVR packet: Expected command "
							 "len %i, got %i" % (a - b, len(blob[b:a])))
		record["command"] = blob[b:a]
		b = a + 4
		if b > len(blob):
			raise ValueError("Corrupt madVR packet: Expected sizeOfParams "
							 "len %i, got %i" % (b - a, len(blob[a:b])))
		record["sizeOfParams"] = struct.unpack("<i", blob[a:b])[0]
		a = b + record["sizeOfParams"]
		if a > record["len"] + 12:
			raise ValueError("Corrupt madVR packet: Expected params "
							 "len %i, got %i" % (a - b, len(blob[b:a])))
		params = blob[b:a]
		if self.debug > 1:
			record["rawParams"] = params
		if record["command"] == "hello":
			io = StringIO("[Default]\n" +
						  "\n".join(params.decode("UTF-16-LE",
												  "replace").strip().split("\t")))
			cfg = RawConfigParser()
			cfg.optionxform = str
			cfg.readfp(io)
			params = OrderedDict(cfg.items("Default"))
		record["params"] = params
		if self.debug:
			safe_print(record["processId"], record["module"],
					   record["commandNo"], record["component"],
					   record["instance"], record["command"])
			for key, value in record.iteritems():
				if key == "params" or self.debug > 2:
					if (value and isinstance(value,
											 basestring)) or self.debug > 1:
						if isinstance(value, basestring):
							tvalue = value[:256]
							if tvalue != value:
								value = "%r[:256]" % tvalue
							else:
								value = "%r" % value
						safe_print("    %s = %s" % (key, value))
		blob = blob[a:]
		return record, blob

	def _assemble(self, command="", params="", component="madTPG"):
		""" Assemble packet """
		magic = "mad."
		data = struct.pack("<i", os.getpid())  # processId
		data += struct.pack("<q", id(__name__))  # module/DLL handle
		self._commandno += 1
		data += struct.pack("<i", self._commandno)
		data += struct.pack("<i", len(component))  # sizeOfComponent
		data += component
		if component == "madTPG":
			instance = self._instance
		else:
			instance = 0
		data += struct.pack("<q", instance)  # instance
		data += struct.pack("<i", len(command))  # sizeOfCommand
		self._command = command
		data += command
		data += struct.pack("<i", len(params))  # sizeOfParams
		data += params
		datalen = len(data)
		packet = magic + struct.pack("<i", datalen)
		packet += struct.pack("<I", crc32(packet) & 0xFFFFFFFF)
		packet += data
		if self.debug:
			safe_print("MadTPG_Net: Assembled madVR packet:")
			self._parse(packet)
		return packet

	def _send(self, command="", params="", component="madTPG"):
		""" Send madTPG command """
		packet = self._assemble(command, params, component)
		if self._client_socket:
			try:
				if self.debug:
					safe_print("MadTPG_Net: Sending packet to %s:%s" %
							   (self.host, self.port))
				self._client_socket.sendall(packet)
			except socket.error, exception:
				safe_print("MadTPG_Net:", exception)
				return False
			if command not in ("confirm", "hello", "reply",
							   "bye") and not command.startswith("store:"):
				# Get reply
				if self.debug:
					safe_print("MadTPG_Net: Expecting reply")
				returnvalue = self._process()
				return returnvalue
			return True
		return False

	@property
	def uri(self):
		return "%s:%s" % (self.host, self.port)


class MadTPG_Net_Sender(object):

	def __init__(self, madtpg, command):
		self.madtpg = madtpg
		if command == "Quit":
			command = "Exit"
		self.command = command

	def __call__(self, *args, **kwargs):
		if self.command == "Load3dlutFile":
			lut = H3DLUT(args[0])
			lutdata = lut.LUTDATA
			self.command = "Load3dlut"
		elif self.command == "Load3dlutFromArray256":
			lutdata = args[0]
			self.command = "Load3dlut"
		if self.command == "Load3dlut":
			params = struct.pack("<i", args[1])  # Save to settings?
			params += struct.pack("<i", args[2])  # 3D LUT slot
			params += lutdata
		elif self.command == "SetDeviceGammaRamp" and args[0] is None:
			# Clear device gamma ramp
			params = ""
			for i in xrange(3):
				for j in xrange(256):
					params += struct.pack("<H", j * 257)
		elif self.command in ("SetDisableOsdButton", "SetStayOnTopButton",
							  "SetUseFullscreenButton"):
			if args[0]:
				params = "+"
			else:
				params = "-"
		elif self.command == "SetOsdText":
			params = args[0].encode("UTF-16-LE")
		elif self.command in ("SetPatternConfig", "SetProgressBarPos"):
			params = "|".join(str(v) for v in args)
		elif self.command == "ShowRGB":
			r, g, b, bgr, bgg, bgb = (None, ) * 6
			for name in ("r", "g", "b", "bgr", "bgg", "bgb"):
				locals()[name] = kwargs.get(name)
			if len(args) >= 3:
				r, g, b = args[:3]
			if len(args) > 3:
				bgr = args[3]
			if len(args) > 4:
				bgg = args[4]
			if len(args) > 5:
				bgb = args[5]
			rgb = r, g, b
			if not None in (bgr, bgg, bgb):
				command += "Ex"
				rgb += (bgr, bgg, bgb)
			if None in (r, g, b):
				raise TypeError("show_rgb() takes at least 4 arguments (%i given)" %
								len(filter(lambda v: v, rgb)))
			params = "|".join(str(v) for v in rgb)
		else:
			params = str(*args)
		return self.madtpg._send(self.command, params)


if __name__ == "__main__":
	import config
	config.initcfg()
	lang.init()
	if sys.platform == "win32":
		madtpg = MadTPG()
	else:
		madtpg = MadTPG_Net()
	if madtpg.connect(method3=CM_StartLocalInstance, timeout3=5000):
		madtpg.show_rgb(1, 0, 0)
