# -*- coding: utf-8 -*-

from socket import (AF_INET, SHUT_RDWR, SOCK_STREAM, error, gethostbyname, 
					gethostname, socket, timeout)
import errno
import httplib
import struct
import urlparse

import demjson

import localization as lang
from log import safe_print
from util_http import encode_multipart_formdata
from util_str import safe_unicode


class GenHTTPPatternGeneratorClient(object):

	""" Generic pattern generator client using HTTP REST interface """

	def __init__(self, host, port, bits, use_video_levels=False,
				 logfile=None):
		self.host = gethostbyname(host)
		self.port = port
		self.bits = bits
		self.use_video_levels = use_video_levels
		self.logfile = logfile

	def wait(self):
		self.connect()

	def __del__(self):
		self.disconnect_client()

	def _conn_exc(self, exception):
		msg = lang.getstr("connection.fail", safe_unicode(exception))
		raise Exception(msg)

	def _send(self, method, url, params=None, headers=None, validate=None):
		try:
			self.conn.request(method, url, params, headers or {})
			resp = self.conn.getresponse()
		except (error, httplib.HTTPException), exception:
			self._conn_exc(exception)
		else:
			if resp.status == httplib.OK:
				return self._validate(resp, url, validate)
			else:
				raise Exception("%s %s" % (resp.status, resp.reason))

	def _shutdown(self):
		# Override this method in subclass!
		pass

	def _validate(self, resp, url, validate):
		# Override this method in subclass!
		pass

	def connect(self):
		self.conn = httplib.HTTPConnection(self.host, self.port)
		self.conn.connect()

	def disconnect_client(self):
		if hasattr(self, "conn"):
			self._shutdown()
			self.conn.close()
			del self.conn

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), bits=None,
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
		# Override this method in subclass!


class GenTCPSockPatternGeneratorServer(object):

	""" Generic pattern generator server using TCP sockets """

	def __init__(self, port, bits, use_video_levels=False, logfile=None):
		self.port = port
		self.bits = bits
		self.use_video_levels = use_video_levels
		self.socket = socket(AF_INET, SOCK_STREAM)
		self.socket.settimeout(1)
		self.socket.bind(('', port))
		self.socket.listen(1)
		self.listening = False
		self.logfile = logfile

	def wait(self):
		self.listening = True
		if self.logfile:
			self.logfile.write(lang.getstr("connection.waiting") +
							   (" %s:%s\n" % (gethostbyname(gethostname()),
											  self.port)))
		while self.listening:
			try:
				self.conn, addr = self.socket.accept()
			except timeout:
				continue
			self.conn.settimeout(1)
			break
		if self.listening:
			if self.logfile:
				self.logfile.write(lang.getstr("connection.established") + "\n")

	def __del__(self):
		self.disconnect_client()
		self.socket.close()

	def _get_rgb(self, rgb, bgrgb, bits=None, use_video_levels=None):
		""" The RGB range should be 0..1 """
		if not bits:
			bits = self.bits
		if use_video_levels is None:
			use_video_levels = self.use_video_levels
		bitv = 2 ** bits - 1
		if use_video_levels:
			minv = 16.0 / 255.0
			maxv = 235.0 / 255.0 - minv
		else:
			minv = 0.0
			maxv = 1.0
		rgb = [round(minv * bitv + v * bitv * maxv) for v in rgb]
		bgrgb = [round(minv * bitv + v * bitv * maxv) for v in bgrgb]
		return rgb, bgrgb, bits

	def disconnect_client(self):
		self.listening = False
		if hasattr(self, "conn"):
			try:
				self.conn.shutdown(SHUT_RDWR)
			except error, exception:
				if exception.errno != errno.ENOTCONN:
					safe_print("Warning - could not shutdown pattern generator "
							   "connection:", exception)
			self.conn.close()
			del self.conn

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0),
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		for server, bits in ((ResolveLSPatternGeneratorServer, 8),
							 (ResolveCMPatternGeneratorServer, 10)):
			server.__dict__["send"](self, rgb, bgrgb, bits, use_video_levels,
									x, y, w, h)


class PrismaPatternGeneratorClient(GenHTTPPatternGeneratorClient):

	""" Prisma HTTP REST interface """

	def __init__(self, host, port=80, use_video_levels=False, logfile=None):
		self._host = host
		GenHTTPPatternGeneratorClient.__init__(self, host, port, 8,
											   use_video_levels=use_video_levels,
											   logfile=logfile)

	def _get_rgb(self, rgb, bgrgb, bits=8, use_video_levels=None):
		""" The RGB range should be 0..1 """
		_get_rgb = GenTCPSockPatternGeneratorServer.__dict__["_get_rgb"]
		rgb, bgrgb, bits = _get_rgb(self, rgb, bgrgb, 8, use_video_levels)
		# Encode RGB values for Prisma HTTP REST interface
		# See prisma-sdk/prisma.cpp, PrismaIo::wincolor
		rgb = [int(round(v)) for v in rgb]
		bgrgb = [int(round(v)) for v in bgrgb]
		rgb = ((rgb[0] & 0xff) << 16 |
			   (rgb[1] & 0xff) << 8 |
			   (rgb[2] & 0xff) << 0)
		bgrgb = ((bgrgb[0] & 0xff) << 16 |
				 (bgrgb[1] & 0xff) << 8 |
				 (bgrgb[2] & 0xff) << 0)
		return rgb, bgrgb, bits

	def _shutdown(self):
		try:
			self._send("GET", "/window?m=off&sz=10", validate={"off": "Ok"})
		except:
			pass

	def _validate(self, resp, url, validate):
		raw = resp.read()
		if isinstance(validate, dict):
			data = demjson.decode(raw)
			components = urlparse.urlparse(url)
			api = components.path[1:]
			query = urlparse.parse_qs(components.query)
			method = query['m'][0]
			if data.get(method) == "Error" and "msg" in data:
				raise Exception("%s: %s" % (self._host, data["msg"]))
			for key, value in validate.iteritems():
				if key not in data:
					raise Exception(lang.getstr("response.invalid.missing_key",
												(self._host, key, raw)))
				elif value is not None and data[key] != value:
					raise Exception(lang.getstr("response.invalid.value",
												(self._host, key, value, raw)))
			return data, raw
		elif validate:
			if raw != validate:
				raise Exception(lang.getstr("response.invalid",
											(self._host, raw)))
		return raw

	def disable_processing(self, size=10):
		self.enable_processing(False, size)

	def enable_processing(self, enable=True, size=10):
		if enable:
			win = 1
		else:
			win = 2
		self._send("GET", "/window?m=win%i&sz=%i" % (win, size),
				   validate={"win%i" % win: "Ok"})

	def get_installed_3dluts(self):
		return self._send("GET", "/cube?m=list", validate={"list": "Ok",
														   "tables": None})

	def load_preset(self, presetname=None):
		validate = {"settings": None}
		if presetname:
			query = "?m=loadPreset&n=" + presetname
		else:
			query = ""
			validate["preset"] = None
		return self._send("GET", "/setup" + query, validate=validate)

	def load_3dlut_file(self, path, filename):
		with open(path, "rb") as lut3d:
			data = lut3d.read()
		files = [("cubeFile", filename, data)]
		content_type, params = encode_multipart_formdata([], files)
		headers = {"Content-Type": content_type,
				   "Content-Length": str(len(params))}
		# Upload 3D LUT
		self._send("POST", "/fwupload", params, headers)

	def remove_3dlut(self, filename):
		self._send("GET", "/cube?m=remove&n=" + filename,
				   validate={"remove": "Ok"})

	def set_3dlut(self, filename):
		# Select 3D LUT
		self._send("GET", "/setup?m=setCube&n=%s&f=null" % filename,
				   validate={"setCube": "Ok"})

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), bits=None,
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
		self._send("GET", "/window?m=color&bg=%i&fg=%i" % (bgrgb, rgb),
				   validate={"color": "Ok"})


class ResolveLSPatternGeneratorServer(GenTCPSockPatternGeneratorServer):

	def __init__(self, port=20002, bits=8, use_video_levels=False,
				 logfile=None):
		GenTCPSockPatternGeneratorServer.__init__(self, port, bits,
												  use_video_levels, logfile)

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), bits=None,
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		""" Send an RGB color to the pattern generator. The RGB range should be 0..1 """
		rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
		xml = ('<?xml version="1.0" encoding="UTF-8" ?><calibration><shapes>'
			   '<rectangle><color red="%i" green="%i" blue="%i" />'
			   '<geometry x="%.2f" y="%.2f" cx="%.2f" cy="%.2f" /></rectangle>'
			   '</shapes></calibration>' % tuple(rgb + [x, y,  w, h]))
		self.conn.sendall("%s%s" % (struct.pack(">I", len(xml)), xml))


class ResolveCMPatternGeneratorServer(GenTCPSockPatternGeneratorServer):

	def __init__(self, port=20002, bits=10, use_video_levels=False,
				 logfile=None):
		GenTCPSockPatternGeneratorServer.__init__(self, port, bits,
												  use_video_levels, logfile)

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), bits=None,
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		""" Send an RGB color to the pattern generator. The RGB range should be 0..1 """
		rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
		xml = ('<?xml version="1.0" encoding="utf-8"?><calibration>'
			   '<color red="%i" green="%i" blue="%i" bits="%i"/>'
			   '<background red="%i" green="%i" blue="%i" bits="%i"/>'
			   '<geometry x="%.2f" y="%.2f" cx="%.2f" cy="%.2f"/>'
			   '</calibration>' % tuple(rgb + [bits] + bgrgb + [bits, x, y,
																  w, h]))
		self.conn.sendall("%s%s" % (struct.pack(">I", len(xml)), xml))
	

if __name__ == "__main__":
	patterngenerator = GenTCPSockPatternGeneratorServer()
