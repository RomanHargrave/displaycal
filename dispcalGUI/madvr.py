# -*- coding: utf-8 -*-

# See developers/interfaces/madTPG.h in the madVR package

from ConfigParser import RawConfigParser
from StringIO import StringIO
from time import sleep
from zlib import crc32
import ctypes
import errno
import getpass
import logging
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
				"Quit")


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


class MadTPG_Net(object):

	""" Implementation of madVR network protocol in pure python """

	# FIXME/NOTE this isn't working yet

	# Wireshark filter to help ananlyze traffic:
	# tcp.port == 37612 or tcp.port == 43219 or tcp.port == 47815 or tcp.port == 60562 or udp.port == 39568 or udp.port == 41513 or udp.port == 45817 or udp.port == 34761

	def __init__(self, host="localhost", ports=(54184, 60562), timeout=3):
		self._broadcast_sockets = {}
		self._command = None
		self._commandcount = 0
		self._commandno = 0
		self._conn_sockets = {}
		self._instance = id(self)
		self._multicast_sockets = {}
		self._serv_sockets = {}
		self.debug = 0
		self.host = host
		self.listening = True
		self.ports = ports
		self.records = []
		self.timeout = timeout
		logging.getLogger().setLevel(logging.INFO)
		# Connection listen sockets
		for port in (37612, 43219, 47815):
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(1)
			sock.bind(("", port))
			sock.listen(1)
			threading.Thread(target=self._conn_accept_handler,
							 args=(sock, port)).start()
			self._serv_sockets[port] = sock
		# Broadcast listen sockets
		self._broadcast_ip = "255.255.255.255"
		for port in (39568, 41513, 45817):
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			sock.settimeout(1)
			sock.bind(("", port))
			self._broadcast_sockets[port] = sock
			threading.Thread(target=self._xcast_receive_handler,
							 args=(sock, port)).start()
		# Multicast listen socket
		self._multicast_ip = "235.117.220.191"
		for port in (34761, ):
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
			sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
							struct.pack("4sl",
										socket.inet_aton(self._multicast_ip),
										socket.INADDR_ANY))
			sock.settimeout(1)
			sock.bind(("", port))
			self._multicast_sockets[port] = sock
			threading.Thread(target=self._xcast_receive_handler,
							 args=(sock, port)).start()
		# Announce
		threading.Thread(target=self.announce).start()

	def _conn_accept_handler(self, sock, port):
		logging.info("ENTERING INCOMING CONNECTION THREAD FOR PORT %i" % port)
		while self and getattr(self, "listening", False):
			try:
				# Wait for connection
				conn, addrport = sock.accept()
				logging.info("INCOMING CONNECTION FROM %s" % addrport)
			except socket.timeout:
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				raise
			threading.Thread(target=self._receive_handler,
							 args=(conn, addrport)).start()
		logging.info("EXITING INCOMING CONNECTION THREAD FOR PORT %i" % port)

	def _receive_handler(self, conn, addrport):
		logging.info("ENTERING INCOMING MESSAGES THREAD FOR %s:%s" % addrport)
		while self and getattr(self, "listening", False):
			# Wait for incoming message
			try:
				incoming = conn.recv(4096)
			except socket.timeout:
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				break
			else:
				if not incoming:
					break
				logging.info("RECEIVED MESSAGE FROM %s: %s" % (addrport, incoming))
		logging.info("EXITING INCOMING MESSAGES THREAD FOR %s:%s" % addrport)

	def _xcast_receive_handler(self, sock, port):
		if port in self._broadcast_sockets:
			xcast = "BROADCAST"
		elif port in self._multicast_sockets:
			xcast = "MULTICAST"
		else:
			xcast = "XCAST"
		logging.info("ENTERING %s RECEIVER THREAD FOR PORT %i" % (xcast, port))
		while self and getattr(self, "listening", False):
			try:
				logging.info("RECEIVED %s AT PORT %i: %s" % (xcast, port,
															 sock.recv(4096)))
			except socket.timeout:
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				raise
		logging.info("EXITING %s RECEIVER THREAD FOR PORT %i" % (xcast, port))

	def __del__(self):
		self.shutdown()

	def shutdown(self):
		self.listening = False
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
		# Announce
		for port, sock in self._broadcast_sockets.iteritems():
			conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			conn.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			conn.settimeout(1)
			logging.info("SENDING BROADCAST TO PORT %i" % port)
			conn.sendto("\0\0\0\0", (self._broadcast_ip, port))
		for port, sock in self._multicast_sockets.iteritems():
			conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			conn.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
			conn.settimeout(1)
			logging.info("SENDING MULTICAST TO PORT %i" % port)
			conn.sendto("\0\0\0\0", (self._multicast_ip, port))

	def connect(self, method1=None, timeout1=1000,
				method2=None, timeout2=3000,
				method3=None, timeout3=0, method4=CM_Fail,
				timeout4=0, parentwindow=None):
		for port in self.ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(self.timeout)
			sock.connect((self.host, port))
			self._conn_sockets[port] = sock
			self.hello(port)
			returnvalue = self.get(port)
		if returnvalue:
			returnvalue = self._send("StartTestPattern", port=self.ports[-1])
		return returnvalue

	def disconnect(self):
		if self._conn_sockets:
			returnvalue = self._send("StopTestPattern", port=self.ports[-1])
			for port, sock in self._conn_sockets.iteritems():
				try:
					# Will fail if the socket isn't connected, i.e. if there was an
					# error during the call to connect()
					sock.shutdown(socket.SHUT_RDWR)
				except socket.error, exception:
					if exception.errno != errno.ENOTCONN:
						raise
				sock.close()
				return returnvalue

	def get(self, port=None):
		""" Retrieve madVR packets """
		self._get("", port)
		returnvalue = ""
		while self.records:
			record = self.records.pop(0)
			self._commandcount = record["commandNo"]
			component = record["component"]
			command = record["command"]
			params = record["params"]
			if command == "reply" and record["commandNo"] != self._commandno:
				if self._command == "GetBlackAndWhiteLevel":
					if len(params) == 8:
						returnvalue = tuple(struct.unpack("<I", params[i:i + 4])[0]
											for i in xrange(2))
					else:
						returnvalue = False
				elif self._command == "GetPatternConfig":
					if len(params) == 16:
						returnvalue = tuple(struct.unpack("<I", params[i:i + 4])[0]
											for i in xrange(4))
					else:
						returnvalue = False
				elif self._command in ("GetSelected3dlut", ):
					if len(params) == 4:
						returnvalue = struct.unpack("<I", params[0:4])[0]
					else:
						returnvalue = False
				else:
					returnvalue += params
			elif command == "confirm":
				returnvalue = True
		if returnvalue == "+":
			returnvalue = True
		elif returnvalue == "-":
			returnvalue = False
		return returnvalue

	def hello(self, port=None):
		info = [("computerName", safe_unicode(socket.gethostname().upper())),
				("userName", safe_unicode(getpass.getuser())),
				("os", "%s %s" % (platform.system(), platform.release())),
				("exeFile", os.path.basename(sys.executable)), ("exeVersion",
															    version),
				("exeDescr", ""), ("exeIcon", "")]
		params = ""
		for key, value in info:
			params += ("%s=%s\t" % (key, value)).encode("UTF-16-LE", "replace")
		return self._send("hello", params, "", port)

	def _get(self, blob="", port=None):
		""" Retrieve madVR packets """
		if not port:
			port = self.ports[-1]
		if self.debug:
			logging.info("RECEIVING FROM PORT %i" % port)
		while len(blob) < 12:
			try:
				buffer = self._conn_sockets[port].recv(4096)
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					return
				raise
			blob += buffer
		crc = struct.unpack("<I", blob[8:12])[0]
		# Check CRC
		check = crc32(blob[:8]) & 0xFFFFFFFF
		if check != crc:
			raise ValueError("Invalid madVR packet: CRC check failed: Expected %i, got %i" %
							 (crc, check))
		datalen = struct.unpack("<I", blob[4:8])[0]
		while len(blob) < datalen + 12:
			blob += self._conn_sockets[port].recv(4096)
		while blob:
			record, blob = self._parse(blob)
			self.records.append(record)

	def _parse(self, blob=""):
		""" Parse blob into record, return remaining blob """
		record = OrderedDict([("magic", blob[0:4]),
							  ("len", struct.unpack("<I", blob[4:8])[0]),
							  ("crc", struct.unpack("<I", blob[8:12])[0]),
							  ("processId", struct.unpack("<I", blob[12:16])[0]),
							  ("module", struct.unpack("<Q", blob[16:24])[0]),
							  ("commandNo", struct.unpack("<I", blob[24:28])[0]),
							  ("sizeOfComponent", struct.unpack("<I", blob[28:32])[0])])
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
		record["instance"] = struct.unpack("<Q", blob[b:a])[0]
		b = a + 4
		if b > len(blob):
			raise ValueError("Corrupt madVR packet: Expected sizeOfCommand "
							 "len %i, got %i" % (b - a, len(blob[a:b])))
		record["sizeOfCommand"] = struct.unpack("<I", blob[a:b])[0]
		a = b + record["sizeOfCommand"]
		if a > len(blob):
			raise ValueError("Corrupt madVR packet: Expected command "
							 "len %i, got %i" % (a - b, len(blob[b:a])))
		record["command"] = blob[b:a]
		b = a + 4
		if b > len(blob):
			raise ValueError("Corrupt madVR packet: Expected sizeOfParams "
							 "len %i, got %i" % (b - a, len(blob[a:b])))
		record["sizeOfParams"] = struct.unpack("<I", blob[a:b])[0]
		a = b + record["sizeOfParams"]
		if a > record["len"] + 12:
			raise ValueError("Corrupt madVR packet: Expected params "
							 "len %i, got %i" % (a - b, len(blob[b:a])))
		params = blob[b:a]
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
			logging.info("%i %s %s" % (record["commandNo"], record["component"], record["command"]))
			for key, value in record.iteritems():
				if key in ("instance", "params") or self.debug > 1:
					logging.info("    %s = %r" % (key, value))
		blob = blob[a:]
		return record, blob

	def _send(self, command="", params="", component="madTPG", port=None):
		""" Send madTPG command """
		# Assemble packet
		magic = "mad."
		data = struct.pack("<I", os.getpid())  # processId
		data += struct.pack("<Q", id(__name__))  # module/DLL handle
		self._commandno += 1
		data += struct.pack("<I", self._commandno)
		data += struct.pack("<I", len(component))  # sizeOfComponent
		data += component
		data += struct.pack("<Q", self._instance)  # instance
		data += struct.pack("<I", len(command))  # sizeOfCommand
		self._command = command
		data += command
		data += struct.pack("<I", len(params))  # sizeOfParams
		data += params
		datalen = len(data)
		packet = magic + struct.pack("<I", datalen)
		packet += struct.pack("<I", crc32(packet) & 0xFFFFFFFF)
		packet += data
		if self.debug:
			logging.info("SENDING")
			self._parse(packet)
		# Send packet
		if self._conn_sockets:
			if port:
				logging.info("SENDING TO PORT %i" % port)
				self._conn_sockets[port].sendall(packet)
			else:
				for port, sock in self._conn_sockets.iteritems():
					logging.info("SENDING TO PORT %i" % port)
					sock.sendall(packet)
		if command not in ("confirm", "hello", "reply",
						   "bye") and not command.startswith("store:"):
			# Get reply
			returnvalue = self.get(port)
			return returnvalue


class MadTPG_Net_Sender(object):

	def __init__(self, madtpg, command):
		self.madtpg = madtpg
		self.command = command

	def __call__(self, *args, **kwargs):
		if self.command == "SetDeviceGammaRamp" and args[0] is None:
			# Clear device gamma ramp
			params = ""
			for i in xrange(3):
				for j in xrange(256):
					params += chr(i) * 2
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
		return self.madtpg._send(self.command, params,
								 port=self.madtpg.ports[-1])


if __name__ == "__main__":
	import config
	config.initcfg()
	lang.init()
	madtpg = MadTPG()
	if madtpg.connect(method3=CM_StartLocalInstance, timeout3=5000):
		madtpg.show_rgb(1, 0, 0)
