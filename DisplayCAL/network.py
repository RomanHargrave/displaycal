# -*- coding: utf-8 -*-

import errno
import os
import socket

import localization as lang
from log import safe_print
from util_str import safe_str, safe_unicode


def get_network_addr():
	"""
	Tries to get the local machine's network address.
	
	"""
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# Opening a connection on an UDP socket does nothing except give the socket
	# the network address of the (local) machine. We use Google's DNS server
	# as remote address, but could use any valid non-local address (doesn't
	# matter if it is actually reachable)
	try:
		s.connect(('8.8.8.8', 53))
		return s.getsockname()[0]  # Return network address
	finally:
		s.close()


def get_valid_host(hostname=None):
	"""
	Tries to verify the hostname by resolving to an IPv4 address.
	
	Both hostname with and without .local suffix will be tried if necessary.
	
	Returns a tuple hostname, addr
	
	"""
	if hostname is None:
		hostname = socket.gethostname()
	hostnames = [hostname]
	if hostname.endswith(".local"):
		hostnames.insert(0, os.path.splitext(hostname)[0])
	elif not "." in hostname:
		hostnames.insert(0, hostname + ".local")
	while hostnames:
		hostname = hostnames.pop()
		try:
			addr = socket.gethostbyname(hostname)
		except socket.error:
			if not hostnames:
				raise
		else:
			return hostname, addr


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
