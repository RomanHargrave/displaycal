# -*- coding: utf-8 -*-

from socket import (AF_INET, SHUT_RDWR, SOCK_STREAM, error, gethostbyname, 
					gethostname, socket, timeout)
import errno
import struct

import localization as lang
from log import safe_print
from util_str import safe_unicode


class PatternGeneratorServer(object):

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


class ResolveLSPatternGeneratorServer(PatternGeneratorServer):

	def __init__(self, port=20002, bits=8, use_video_levels=False,
				 logfile=None):
		PatternGeneratorServer.__init__(self, port, bits, use_video_levels,
										logfile)

	def send(self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), bits=None,
			 use_video_levels=None, x=0, y=0, w=1, h=1):
		""" Send an RGB color to the pattern generator. The RGB range should be 0..1 """
		rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
		xml = ('<?xml version="1.0" encoding="UTF-8" ?><calibration><shapes>'
			   '<rectangle><color red="%i" green="%i" blue="%i" />'
			   '<geometry x="%.2f" y="%.2f" cx="%.2f" cy="%.2f" /></rectangle>'
			   '</shapes></calibration>' % tuple(rgb + [x, y,  w, h]))
		self.conn.sendall("%s%s" % (struct.pack(">I", len(xml)), xml))


class ResolveCMPatternGeneratorServer(PatternGeneratorServer):

	def __init__(self, port=20002, bits=10, use_video_levels=False,
				 logfile=None):
		PatternGeneratorServer.__init__(self, port, bits, use_video_levels,
										logfile)

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
	patterngenerator = PatternGeneratorServer()
