# -*- coding: utf-8 -*-

import errno
import socket

import localization as lang
from log import safe_print
from util_str import safe_str, safe_unicode


class ScriptingClientSocket(socket.socket):

	def __del__(self):
		self.disconnect()

	def __enter__(self):
		return self

	def __exit__(self, etype, value, tb):
		self.disconnect()

	def __init__(self):
		socket.socket.__init__(self)
		self.recv_buffer = ""

	def disconnect(self):
		try:
			# Will fail if the socket isn't connected, i.e. if there was an
			# error during the call to connect()
			self.shutdown(socket.SHUT_RDWR)
		except socket.error, exception:
			if exception.errno != errno.ENOTCONN:
				safe_print(exception)
		self.close()

	def get_single_response(self):
		# Buffer received data until EOT (response end marker) and return
		# single response (additional data will still be in the buffer)
		while not "\4" in self.recv_buffer:
			incoming = self.recv(4096)
			if incoming == "":
				raise socket.error(lang.getstr("connection.broken"))
			self.recv_buffer += incoming
		end = self.recv_buffer.find("\4")
		single_response = self.recv_buffer[:end]
		self.recv_buffer = self.recv_buffer[end + 1:]
		return safe_unicode(single_response, "UTF-8")

	def send_command(self, command):
		# Automatically append newline (command end marker)
		self.sendall(safe_str(command, "UTF-8") + "\n")
