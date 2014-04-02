# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import re
import shutil
import subprocess as sp
import sys
from time import sleep

try:
	if not "--use-gi" in sys.argv:
		raise ImportError("")
	from gi.repository import Colord
	from gi.repository import Gio
except ImportError:
	Colord = None
	Gio = None
else:
	cancellable = Gio.Cancellable.new();

if sys.platform not in ("darwin", "win32"):
	from defaultpaths import xdg_data_home

from util_os import which
from util_str import safe_str

if not Colord or not hasattr(Colord, 'quirk_vendor_name'):
	from config import get_data_path
	import demjson

	quirk_cache = {'suffixes': [],
				   'vendor_names': {}}


prefix = "/org/freedesktop/ColorManager/"


def client_connect():
	""" Connect to colord """
	client = Colord.Client.new()

	# Connect to colord
	if not client.connect_sync(cancellable):
		raise CDError("Couldn't connect to colord")
	return client


def device_connect(client, device_id):
	""" Connect to device """
	if isinstance(device_id, unicode):
		device_id = device_id.encode('UTF-8')
	try:
		device = client.find_device_sync(device_id, cancellable)
	except Exception, exception:
		raise CDError(exception.args[0])

	# Connect to device
	if not device.connect_sync(cancellable):
		raise CDError("Couldn't connect to device with ID %r" % device_id)
	return device


def device_id_from_edid(edid, quirk=True, use_serial_32=True,
						truncate_edid_strings=False):
	""" Assemble device key from EDID """
	# https://github.com/hughsie/colord/blob/master/doc/device-and-profile-naming-spec.txt
	# Should match device ID returned by gcm_session_get_output_id in
	# gnome-settings-daemon/plugins/color/gsd-color-state.c
	# and Edid::deviceId in colord-kde/colord-kded/Edid.cpp respectively
	parts = ["xrandr"]
	edid_keys = ["manufacturer", "monitor_name", "serial_ascii"]
	if use_serial_32:
		edid_keys += ["serial_32"]
	for name in edid_keys:
		value = edid.get(name)
		if value:
			if name == "serial_32" and "serial_ascii" in edid:
				# Only add numeric serial if no ascii serial
				continue
			elif name == "manufacturer":
				if quirk:
					value = quirk_manufacturer(value)
			elif isinstance(value, basestring) and truncate_edid_strings:
				# Older versions of colord used only the first 12 bytes
				value = value[:12]
			parts.append(str(value))
	if len(parts) > 1:
		return "-".join(parts)
	# TODO: Should fall back to xrandr name


def get_default_profile(device_id):
	"""
	Get default profile filename for device
	
	"""
	if not Colord:
		colormgr = which("colormgr")
		if not colormgr:
			raise CDError("colormgr helper program not found")

		# Find device object path
		device = get_object_path(device_id, "devices", "display")
		
		# Get default profile
		try:
			p = sp.Popen([safe_str(colormgr), "device-get-default-profile",
						  device],
						 stdout=sp.PIPE, stderr=sp.PIPE)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))
		else:
			if stderr.strip():
				raise CDError(stderr)
			match = re.search(":\s*([^\r\n]+\.ic[cm])", stdout, re.I)
			if match:
				return match.groups()[0]
			else:
				raise CDError("Couldn't get default profile for device ID %r" %
							  device_id)
		
	client = client_connect()

	# Connect to existing device
	device = device_connect(client, device_id)
	
	# Get default profile
	profile = device.get_default_profile()
	if not profile:
		# No assigned profile
		return

	# Connect to profile
	if not profile.connect_sync(cancellable):
		raise CDError("Couldn't get default profile for device ID %r" % device_id)
	filename = profile.get_filename()
	if not isinstance(filename, unicode):
		filename = filename.decode('UTF-8')
	return filename


def get_object_path(search, object_type, object_subtype=None):
	colormgr = which("colormgr")
	if not colormgr:
		raise CDError("colormgr helper program not found")
	args = ["get-%s" % object_type]
	if object_subtype:
		args.append(object_subtype)
	try:
		p = sp.Popen([safe_str(colormgr)] + args, stdout=sp.PIPE,
					 stderr=sp.PIPE)
		stdout, stderr = p.communicate()
	except Exception, exception:
		raise CDError(safe_str(exception))
	else:
		if stderr.strip():
			raise CDError(stderr)
		object_path = None
		oprefix = prefix + object_type + "/"
		for block in stdout.strip().split(oprefix):
			match = re.search(":\s*%s" % re.escape(search), block)
			if match:
				# Object path is the first line of the block
				object_path = oprefix + block.strip().splitlines()[0].strip()
				break
		if not object_path:
			raise CDError("Could not find object path for %s" % search)
	return object_path


def install_profile(device_id, profile_filename, profile_installname=None,
					timeout=2):
	"""
	Install profile for device
	
	profile_installname   filename of the installed profile (full path).
						  The profile is copied to this location.
						  If profile_installname is None, it defaults to
						  ~/.local/share/icc/<profile basename>
	timeout				  Time to allow for colord to pick up new profiles
						  (recommended not below 2 secs)
	
	"""

	# Copy profile
	if not profile_installname:
		profile_installname = os.path.join(xdg_data_home, 'icc',
										   os.path.basename(profile_filename))
	profile_installdir = os.path.dirname(profile_installname)
	if not os.path.isdir(profile_installdir):
		os.makedirs(profile_installdir)
	shutil.copyfile(profile_filename, profile_installname)
	
	if isinstance(profile_installname, unicode):
		profile_installname = profile_installname.encode('UTF-8')

	if Colord:
		client = client_connect()
	else:
		colormgr = which("colormgr")
		if not colormgr:
			raise CDError("colormgr helper program not found")

		profile = None

	# Query colord for newly added profile
	for i in xrange(int(timeout / .5)):
		try:
			if Colord:
				profile = client.find_profile_by_filename_sync(profile_installname,
															   cancellable)
			else:
				profile = get_object_path(profile_installname, "profiles")
		except Exception, exception:
			# Profile not found
			pass
		if profile:
			break
		# Give colord time to pick up the profile
		sleep(.5)

	if not profile:
		raise CDError("Querying for profile %r returned no result for %s secs" %
					  (profile_installname, timeout))

	if Colord:
		# Connect to profile
		if not profile.connect_sync(cancellable):
			raise CDError("Could not connect to profile")

		# Connect to existing device
		device = device_connect(client, device_id)

		# Add profile to device
		try:
			device.add_profile_sync(Colord.DeviceRelation.HARD, profile, cancellable)
		except Exception, exception:
			# Profile may already have been added
			pass

		# Make profile default for device
		if not device.make_profile_default_sync(profile, cancellable):
			raise CDError("Could not make profile %r default for device ID %s" %
						  (profile.get_filename(), device_id))
	else:
		# Find device object path
		device = get_object_path(device_id, "devices", "display")

		# Add profile to device
		# (Ignore stderr as profile may already have been added)
		try:
			p = sp.Popen([safe_str(colormgr), "device-add-profile",
						  device, profile], stdout=sp.PIPE, stderr=sp.PIPE)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))

		# Make profile default for device
		try:
			p = sp.Popen([safe_str(colormgr), "device-make-profile-default",
						  device, profile], stdout=sp.PIPE, stderr=sp.PIPE)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))
		else:
			if stderr.strip():
				raise CDError(stderr)


def quirk_manufacturer(manufacturer):
	if Colord and hasattr(Colord, 'quirk_vendor_name'):
		return Colord.quirk_vendor_name(manufacturer)

	if not quirk_cache['suffixes'] or not quirk_cache['vendor_names']:
		quirk_filename = get_data_path('quirk.json')
		if quirk_filename:
			with open(quirk_filename) as quirk_file:
				quirk = demjson.decode(quirk_file.read())
				quirk_cache['suffixes'] = quirk['suffixes']
				quirk_cache['vendor_names'] = quirk['vendor_names']

	# Correct some company names
	for old, new in quirk_cache['vendor_names'].iteritems():
		if manufacturer.startswith(old):
			manufacturer = new
			break

	# Get rid of suffixes
	for suffix in quirk_cache['suffixes']:
		if manufacturer.endswith(suffix):
			manufacturer = manufacturer[0:len(manufacturer) - len(suffix)]

	manufacturer = manufacturer.rstrip()

	return manufacturer


class CDError(Exception):
	pass


if __name__ == "__main__":
	import sys
	for arg in sys.argv[1:]:
		print get_default_profile(arg)
