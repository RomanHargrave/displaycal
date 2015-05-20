# -*- coding: utf-8 -*-

# See developers/interfaces/madTPG.h in the madVR package

from __future__ import with_statement
from ConfigParser import RawConfigParser
from StringIO import StringIO
from binascii import unhexlify
from time import sleep, time
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


def inet_pton(ip_string):
	"""
	inet_pton(string) -> packed IP representation

	Convert an IP address in string format to the  packed
	binary format used in low-level network functions.
	
	"""
	if ":" in ip_string:
		# IPv6
		return "".join([unhexlify(block.rjust(4, "0")) for block in ip_string.split(":")])
	else:
		# IPv4
		return "".join([chr(int(block)) for block in ip_string.split(".")])


def trunc(value, length):
	""" For string types, return value truncated to length """
	if isinstance(value, basestring):
		value = safe_str(value)
		if len(repr(value)) > length:
			value = value[:length - 3 - len(str(length)) - len(repr(value)) + len(value)]
			return "%r[:%i]" % (value, length)
	return repr(value)


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
		return result and thr3dlut.value

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

	def __init__(self):
		self._cast_sockets = {}
		self._casts = []
		self._client_sockets = OrderedDict()
		self._commandno = 0
		self._commands = {}
		hostname = socket.gethostname()
		self._host = socket.gethostbyname(hostname)
		self._incoming = {}
		self._ips = [i[4][0] for i in socket.getaddrinfo(hostname, None)]
		self._pid = 0
		self._reset()
		self._server_sockets = {}
		self._threads = []
		#self.broadcast_ports = (39568, 41513, 45817, 48591, 48912)
		self.broadcast_ports = (37018, 10658, 63922, 53181, 4287)
		self.clients = OrderedDict()
		self.debug = 0
		self.listening = True
		#self.multicast_ports = (34761, )
		self.multicast_ports = (51591, )
		self._event_handlers = {"on_client_added": [],
								"on_client_confirmed": [],
								"on_client_removed": [],
								"on_client_updated": []}
		#self.server_ports = (37612, 43219, 47815, 48291, 48717)
		self.server_ports = (60562, 51130, 54184, 41916, 19902)
		ip = self._host.split(".")
		ip.pop()
		ip.append("255")
		self.broadcast_ip = ".".join(ip)
		self.multicast_ip = "235.117.220.191"

	def listen(self):
		self.listening = True
		# Connection listen sockets
		for port in self.server_ports:
			if ("", port) in self._server_sockets:
				continue
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.settimeout(0)
			try:
				sock.bind(("", port))
				sock.listen(1)
				thread = threading.Thread(target=self._conn_accept_handler,
										  args=(sock, "", port))
				self._threads.append(thread)
				thread.start()
			except socket.error, exception:
				safe_print("MadTPG_Net: TCP Port %i: %s" % (port, exception))
		# Broadcast listen sockets
		for port in self.broadcast_ports:
			if (self.broadcast_ip, port) in self._cast_sockets:
				continue
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			sock.settimeout(0)
			try:
				sock.bind(("", port))
				thread = threading.Thread(target=self._cast_receive_handler,
										  args=(sock, self.broadcast_ip, port))
				self._threads.append(thread)
				thread.start()
			except socket.error, exception:
				safe_print("MadTPG_Net: UDP Port %i: %s" % (port, exception))
		# Multicast listen socket
		for port in self.multicast_ports:
			if (self.multicast_ip, port) in self._cast_sockets:
				continue
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

	def _conn_accept_handler(self, sock, host, port):
		if self.debug:
			safe_print("MadTPG_Net: Entering incoming connection thread for port",
					   port)
		self._server_sockets[(host, port)] = sock
		while getattr(self, "listening", False):
			try:
				# Wait for connection
				conn, addr = sock.accept()
			except socket.timeout, exception:
				# Should never happen for non-blocking socket
				safe_print("MadTPG_Net: In incoming connection thread for port %i:" %
						   port, exception)
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				safe_print("MadTPG_Net: Exception in incoming connection "
						   "thread for %s:%i:" % addr[:2], exception)
				break
			conn.settimeout(0)
			with _lock:
				if self.debug:
					safe_print("MadTPG_Net: Incoming connection from %s:%s to %s:%s" %
							   (addr[:2] + conn.getsockname()[:2]))
				if addr in self._client_sockets:
					if self.debug:
						safe_print("MadTPG_Net: Already connected from %s:%s to %s:%s" %
								   (addr[:2] + conn.getsockname()[:2]))
					self._shutdown(conn, addr)
				else:
					self._client_sockets[addr] = conn
					thread = threading.Thread(target=self._receive_handler,
											  args=(addr, conn, ))
					self._threads.append(thread)
					thread.start()
		self._server_sockets.pop((host, port))
		self._shutdown(sock, (host, port))
		if self.debug:
			safe_print("MadTPG_Net: Exiting incoming connection thread for port",
					   port)

	def _receive_handler(self, addr, conn):
		if self.debug:
			safe_print("MadTPG_Net: Entering receiver thread for %s:%s" %
					   addr[:2])
		self._incoming[addr] = []
		hello = self._hello(conn)
		blob = ""
		send_bye = True
		while (hello and addr in self._client_sockets and
			   getattr(self, "listening", False)):
			# Wait for incoming message
			try:
				incoming = conn.recv(4096)
			except socket.timeout, exception:
				# Should never happen for non-blocking socket
				safe_print("MadTPG_Net: In receiver thread for %s:%i:" %
						   addr[:2], exception)
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.001)
					continue
				if exception.errno not in (errno.EBADF,
										   errno.ECONNRESET) or self.debug:
					safe_print("MadTPG_Net: In receiver thread for %s:%i:" %
							   addr[:2], exception)
				send_bye = False
				break
			else:
				with _lock:
					if not incoming:
						# Connection broken
						if self.debug:
							safe_print("MadTPG_Net: Client %s:%i stopped sending" %
									   addr[:2])
						break
					blob += incoming
					if self.debug:
						safe_print("MadTPG_Net: Received from %s:%s:" %
								   addr[:2])
					while blob and addr in self._client_sockets:
						try:
							record, blob = self._parse(blob)
						except ValueError, exception:
							safe_print("MadTPG_Net:", exception)
							# Invalid, discard
							blob = ""
						else:
							if record is None:
								# Need more data
								break
							self._process(record, conn)
		with _lock:
			self._remove_client(addr, send_bye=addr in self._client_sockets and
											   send_bye)
			self._incoming.pop(addr)
		if self.debug:
			safe_print("MadTPG_Net: Exiting receiver thread for %s:%s" %
					   addr[:2])

	def _remove_client(self, addr, send_bye=True):
		""" Remove client from list of connected clients """
		if addr in self._client_sockets:
			conn = self._client_sockets.pop(addr)
			if send_bye:
				self._send(conn, "bye",
						   component=self.clients.get(addr,
													  {}).get("component", ""))
			if addr in self.clients:
				client = self.clients.pop(addr)
				if self.debug:
					safe_print("MadTPG_Net: Removed client %s:%i" %
							   addr[:2])
				self._dispatch_event("on_client_removed", (addr, client))
			if (self._client_socket and
				self._client_socket == conn):
				self._reset()
			self._shutdown(conn, addr)

	def _cast_receive_handler(self, sock, host, port):
		if host == self.broadcast_ip:
			cast = "broadcast"
		elif host == self.multicast_ip:
			cast = "multicast"
		else:
			cast = "unknown"
		if self.debug:
			safe_print("MadTPG_Net: Entering receiver thread for %s port %i" %
					   (cast, port))
		self._cast_sockets[(host, port)] = sock
		while getattr(self, "listening", False):
			try:
				data, addr = sock.recvfrom(4096)
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
								   (cast, addr[0], addr[1], data))
					if not addr in self._casts:
						for c_port in self.server_ports:
							if (addr[0], c_port) in self._client_sockets:
								if self.debug:
									safe_print("MadTPG_Net: Already connected to %s:%s" %
											   (addr[0], c_port))
							elif (("", c_port) in self._server_sockets and
								  addr[0] in self._ips):
								if self.debug:
									safe_print("MadTPG_Net: Don't connect to self %s:%s" %
											   (addr[0], c_port))
							else:
								conn = self._get_client_socket(addr[0], c_port)
								threading.Thread(target=self._connect,
												 args=(conn, addr[0], c_port)).start()
					else:
						self._casts.remove(addr)
						if self.debug:
							safe_print("MadTPG_Net: Ignoring own %s from %s:%s" %
									   (cast, addr[0], addr[1]))
		self._cast_sockets.pop((host, port))
		self._shutdown(sock, (host, port))
		if self.debug:
			safe_print("MadTPG_Net: Exiting %s receiver thread for port %i" %
					   (cast, port))

	def __del__(self):
		self.shutdown()

	def _shutdown(self, sock, addr):
		try:
			# Will fail if the socket isn't connected, i.e. if there
			# was an error during the call to connect()
			sock.shutdown(socket.SHUT_RDWR)
		except socket.error, exception:
			if exception.errno != errno.ENOTCONN:
				safe_print("MadTPG_Net: SHUT_RDWR for %s:%i failed:" %
						   addr[:2], exception)
		sock.close()

	def shutdown(self):
		self.disconnect()
		self.listening = False
		while self._threads:
			thread = self._threads.pop()
			if thread.isAlive():
				thread.join()

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
		return MadTPG_Net_Sender(self, self._client_socket, methodname)

	def announce(self):
		""" Anounce ourselves """
		for port in self.multicast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
			sock.settimeout(1)
			sock.connect((self.multicast_ip, port))
			addr = sock.getsockname()
			self._casts.append(addr)
			if self.debug:
				safe_print("MadTPG_Net: Sending multicast from %s:%s to port %i" %
						   (addr[0], addr[1], port))
			sock.sendall(struct.pack("<i", 0))
			sock.close()
		for port in self.broadcast_ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			sock.settimeout(1)
			sock.connect((self.broadcast_ip, port))
			addr = sock.getsockname()
			self._casts.append(addr)
			if self.debug:
				safe_print("MadTPG_Net: Sending broadcast from %s:%s to port %i" %
						   (addr[0], addr[1], port))
			sock.sendall(struct.pack("<i", 0))
			sock.close()

	def connect(self, method1=CM_ConnectToLocalInstance, timeout1=1000,
				method2=CM_ConnectToLanInstance, timeout2=3000,
				method3=CM_ShowListDialog, timeout3=0, method4=CM_Fail,
				timeout4=0, parentwindow=None):
		""" Find or select a madTPG instance on the network and connect to it """
		for i in xrange(1, 5):
			method = locals()["method%i" % i]
			timeout = locals()["timeout%i" % i] / 1000.0
			if method in (CM_ConnectToLocalInstance, CM_StartLocalInstance,
						  CM_ConnectToLanInstance, CM_ShowListDialog):
				# NOTE: We treat CM_ConnectToLocalInstance and
				# CM_StartLocalInstance as equivalent to 
				# CM_ConnectToLanInstance.
				if not self._cast_sockets:
					self.listen()
					self.announce()
				if method == CM_ShowListDialog:
					# TODO: Implement
					pass
				else:
					if self._wait_for_client(None, timeout):
						return True
			elif method == CM_ShowIpAddrDialog:
				# TODO: Implement
				pass
		return False

	def connect_to_ip(self, ip, timeout=1000):
		""" Connect to madTPG running under a known IP address """
		ip = socket.gethostbyname(ip)
		for port in self.server_ports:
			conn = self._get_client_socket(ip, port)
			threading.Thread(target=self._connect,
							 args=(conn, ip, port, timeout / 1000.0)).start()
		return self._wait_for_client((ip, port), timeout / 1000.0)

	def _get_client_socket(self, host, port, timeout=1):
		""" Return a new or existing client socket """
		if (host, port) in self._client_sockets:
			return self._client_sockets[(host, port)]
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(timeout)
		self._client_sockets[(host, port)] = sock
		return sock

	def _connect(self, sock, host, port, timeout=1):
		""" Connect to IP:PORT, return socket """
		if self.debug:
			safe_print("MadTPG_Net: Connecting to %s:%s..." %
					   (host, port))
		try:
			sock.connect((host, port))
		except socket.error, exception:
			if self.debug:
				safe_print("MadTPG_Net: Connecting to %s:%s failed:" %
						   (host, port), exception)
			with _lock:
				self._remove_client((host, port), False)
		else:
			if self.debug:
				safe_print("MadTPG_Net: Connected to %s:%s" % (host, port))
			sock.settimeout(0)
			thread = threading.Thread(target=self._receive_handler,
									  args=((host, port), sock, ))
			self._threads.append(thread)
			thread.start()

	def disconnect(self, stop=True):
		returnvalue = False
		conn = self._client_socket
		if conn:
			returnvalue = True
			if stop:
				returnvalue = self._send(conn, "StopTestPattern")
		self._reset()
		return returnvalue

	def _process(self, record, conn):
		""" Process madVR packet """
		command = record["command"]
		if command not in ("bye", "confirm", "hello", "reply"):
			# Ignore
			return
		addr = conn.getpeername()
		commandno = record["commandNo"]
		component = record["component"]
		params = record["params"]
		client = OrderedDict()
		client["processId"] = record["processId"]
		client["module"] = record["module"]
		client["component"] = component
		client["instance"] = record["instance"]
		if command == "reply":
			if params == "+":
				params = True
			elif params == "-":
				params = False
		elif command == "confirm":
			if addr not in self.clients:
				self.clients[addr] = client
				self._dispatch_event("on_client_added",
									 (addr, self.clients[addr]))
			self.clients[addr]["confirmed"] = True
			self._dispatch_event("on_client_confirmed",
								 (addr, self.clients[addr]))
		elif command == "hello":
			client.update(params)
			if addr not in self.clients:
				self.clients[addr] = client
				if self._is_master(conn):
					# Prevent duplicate connections
					for c_addr, c_client in self.clients.iteritems():
						if (c_client.get("confirmed") and
							c_client["processId"] == client["processId"] and
							c_client["module"] == client["module"]):
							if self.debug:
								safe_print("MadTPG_Net: Preventing duplicate connection %s:%i" %
										   addr[:2])
							self._remove_client(addr)
							return
				self._dispatch_event("on_client_added", (addr, client))
			else:
				client_copy = self.clients[addr].copy()
				self.clients[addr].update(client)
				if self.clients[addr] != client_copy:
					self._dispatch_event("on_client_updated",
										 (addr, self.clients[addr]))
			if (not self.clients[addr].get("confirmed") and
				self._is_master(conn) and
				self._send(conn, "confirm", component="")):
				# We are master, sent confirm packet
				self.clients[addr]["confirmed"] = True
				self._dispatch_event("on_client_confirmed",
									 (addr, self.clients[addr]))
				# Close duplicate connections
				for c_addr, c_client in self.clients.iteritems():
					if (c_addr != addr and
						c_client["processId"] == client["processId"] and
						c_client["module"] == client["module"]):
						if self.debug:
							safe_print("MadTPG_Net: Closing duplicate connection %s:%i" %
									   c_addr[:2])
						self._remove_client(c_addr)
		elif command == "bye":
			if self.debug:
				safe_print("MadTPG_Net: Client %s:%i disconnected" % addr[:2])
			self._remove_client(addr)
		self._incoming[addr].append((commandno, command, params, component))

	def get_version(self):
		""" Return madVR version """
		return (self._client_socket and
				self.clients.get(self._client_socket.getpeername(),
								 {}).get("mvrVersion") or False)

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

	def _hello(self, conn):
		""" Send 'hello' packet. Return boolean wether send succeeded or not """
		params = self._assemble_hello_params()
		return self._send(conn, "hello", params, "")

	def _is_master(self, conn):
		""" Return wether our end of the connection is the master or not """
		local = conn.getsockname()
		remote = conn.getpeername()
		return (inet_pton(local[0]) > inet_pton(remote[0]) or
				(inet_pton(local[0]) == inet_pton(remote[0]) and
				 self.clients[remote]["processId"] < os.getpid()))

	def _expect(self, conn, commandno=-1, command=None, params=(), component="",
				timeout=3):
		""" Wait until expected reply or timeout. Return reply params or None. """
		if not isinstance(params, (list, tuple)):
			params = (params, )
		addr = conn.getpeername()
		start = end = time()
		while end - start < timeout:
			for reply in self._incoming.get(addr, []):
				r_commandno, r_command, r_params, r_component = reply
				if (commandno in (r_commandno, -1) and
					command in (r_command, None)
					and not params or (r_params in params) and
					component in (r_component, None)):
					self._incoming[addr].remove(reply)
					return r_params
			sleep(0.001)
			end = time()
		return False

	def _wait_for_client(self, addr=None, timeout=1):
		""" Wait for (first) client connection and handshake """
		start = end = time()
		while end - start < timeout:
			clients = self.clients.copy()
			if clients:
				addr = addr or clients.keys()[0]
				client = clients.get(addr)
				conn = self._client_sockets.get(addr)
				if (client["component"] == "madTPG" and
					client.get("confirmed") and conn and
					self._send(conn, "StartTestPattern")):
					self._client_socket = conn
					return True
			sleep(0.001)
			end = time()
		return False

	def _parse(self, blob=""):
		""" Consume blob, return record + remaining blob """
		if len(blob) < 12:
			return None, blob
		crc = struct.unpack("<I", blob[8:12])[0]
		# Check CRC
		check = crc32(blob[:8]) & 0xFFFFFFFF
		if check != crc:
			raise ValueError("MadTPG_Net: Invalid madVR packet: CRC check "
							 "failed: Expected %i, got %i" % (crc, check))
		datalen = struct.unpack("<i", blob[4:8])[0]
		if len(blob) < datalen + 12:
			return None, blob
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
		record["command"] = command = blob[b:a]
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
		if command == "hello":
			io = StringIO("[Default]\n" +
						  "\n".join(params.decode("UTF-16-LE",
												  "replace").strip().split("\t")))
			cfg = RawConfigParser()
			cfg.optionxform = str
			cfg.readfp(io)
			params = OrderedDict(cfg.items("Default"))
			# Convert version strings to tuples with integers
			for param in ("mvr", "exe"):
				param += "Version"
				if param in params:
					values = params[param].split(".")
					for i, value in enumerate(values):
						try:
							values[i] = int(value)
						except ValueError:
							pass
					params[param] = tuple(values)
		elif command == "reply":
			commandno = record["commandNo"]
			repliedcomamnd = self._commands.get(commandno)
			if repliedcomamnd:
				self._commands.pop(commandno)
				if repliedcomamnd == "GetBlackAndWhiteLevel":
					if len(params) == 8:
						params = struct.unpack("<ii", params)
					else:
						params = False
				elif repliedcomamnd == "GetDeviceGammaRamp":
					# Convert to ushort_Array_256_Array_3
					ramp = ((ctypes.c_ushort * 256) * 3)()
					if len(params) == 1536:
						for j in xrange(3):
							for i in xrange(256):
								ramp[j][i] = int(round(struct.unpack("<H", params[:2])[0]))
								params = params[2:]
						params = ramp
					else:
						params = False
				elif repliedcomamnd == "GetPatternConfig":
					if len(params) == 16:
						params = struct.unpack("<iiii", params)
					else:
						params = False
				elif repliedcomamnd in ("GetSelected3dlut", ):
					if len(params) == 4:
						params = struct.unpack("<i", params[0:4])[0]
					else:
						params = False
			else:
				# Got a reply for a command we never issued?
				if self.debug:
					safe_print("MadTPG_Net: Got reply %i for unknown command" %
							   commandno)
		record["params"] = params
		if self.debug:
			with _lock:
				safe_print(record["processId"], record["module"],
						   record["commandNo"], record["component"],
						   record["instance"], record["command"])
				for key, value in record.iteritems():
					if key == "params" or self.debug > 2:
						if isinstance(value, dict):
							safe_print("  %s:" % key)
							for subkey, subvalue in value.iteritems():
								safe_print("    %s = %s" % (subkey.ljust(16),
															trunc(subvalue, 56)))
						else:
							safe_print("  %s = %s" % (key.ljust(16),
													  trunc(value, 58)))
		blob = blob[a:]
		return record, blob

	def _assemble(self, conn, commandno=1, command="", params="", component="madTPG"):
		""" Assemble packet """
		magic = "mad."
		data = struct.pack("<i", os.getpid())  # processId
		data += struct.pack("<q", id(sys.modules[__name__]))  # module/DLL handle
		data += struct.pack("<i", commandno)
		data += struct.pack("<i", len(component))  # sizeOfComponent
		data += component
		if component == "madTPG":
			instance = self.clients.get(conn.getpeername(), {}).get("instance", 0)
		else:
			instance = 0
		data += struct.pack("<q", instance)  # instance
		data += struct.pack("<i", len(command))  # sizeOfCommand
		data += command
		data += struct.pack("<i", len(params))  # sizeOfParams
		data += params
		datalen = len(data)
		packet = magic + struct.pack("<i", datalen)
		packet += struct.pack("<I", crc32(packet) & 0xFFFFFFFF)
		packet += data
		if self.debug:
			with _lock:
				safe_print("MadTPG_Net: Assembled madVR packet:")
				self._parse(packet)
		return packet

	def _send(self, conn, command="", params="", component="madTPG"):
		""" Send madTPG command and return reply """
		if not conn:
			return False
		self._commandno += 1
		commandno = self._commandno
		try:
			packet = self._assemble(conn, commandno, command, params,
									component)
			if self.debug:
				safe_print("MadTPG_Net: Sending command %i %r to %s:%s" %
						   ((commandno, command) + conn.getpeername()[:2]))
			conn.sendall(packet)
		except socket.error, exception:
			safe_print("MadTPG_Net: Sending command %i %r failed" %
					   (commandno, command), exception)
			return False
		if command not in ("confirm", "hello", "reply",
						   "bye") and not command.startswith("store:"):
			self._commands[commandno] = command
			# Get reply
			if self.debug:
				safe_print("MadTPG_Net: Expecting reply for command %i %r" %
						   (commandno, command))
			return self._expect(conn, commandno, "reply")
		return True

	@property
	def uri(self):
		return "%s:%s" % (self._client_socket and
						  self._client_socket.getpeername()[:2] or
						  ("0.0.0.0", 0))


class MadTPG_Net_Sender(object):

	def __init__(self, madtpg, conn, command):
		self.madtpg = madtpg
		self._conn = conn
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
		elif self.command == "SetDeviceGammaRamp":
			params = ""
			for j in xrange(3):
				for i in xrange(256):
					if args[0] is None:
						# Clear device gamma ramp
						v = i * 257
					else:
						# Convert ushort_Array_256_Array_3 to string
						v = args[0][j][i]
					params += struct.pack("<H", v)
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
		return self.madtpg._send(self._conn, self.command, params)


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
