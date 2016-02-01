# -*- coding: utf-8 -*-

from __future__ import with_statement
from binascii import hexlify
import os
import re
import subprocess as sp
import sys
import warnings
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
from util_str import safe_str, safe_unicode
import localization as lang

if not Colord or not hasattr(Colord, 'quirk_vendor_name'):
	from config import get_data_path
	import demjson

	quirk_cache = {'suffixes': [],
				   'vendor_names': {}}


prefix = "/org/freedesktop/ColorManager/"
device_ids = {}


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
	if "hash" in edid:
		device_id = device_ids.get(edid["hash"])
		if device_id:
			return device_id
		elif sys.platform not in ("darwin", "win32") and which("colormgr"):
			try:
				device = find("device-by-property", ["OutputEdidMd5",
													 edid["hash"]])
			except CDError, exception:
				warnings.warn(safe_str(exception), Warning)
			else:
				device_id = re.search(r":\s*(xrandr-[^\r\n]+)", device)
				if device_id:
					device_id = device_id.groups()[0]
					device_ids[edid["hash"]] = device_id
					return device_id
	parts = ["xrandr"]
	edid_keys = ["manufacturer", "monitor_name", "serial_ascii"]
	if use_serial_32:
		edid_keys.append("serial_32")
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
		device_id = "-".join(parts)
		if "hash" in edid:
			device_ids[edid["hash"]] = device_id
		return device_id


def find(what, search):
	colormgr = which("colormgr")
	if not colormgr:
		raise CDError("colormgr helper program not found")
	if not isinstance(search, list):
		search = [search]
	args = ["find-%s" % what] + search
	try:
		p = sp.Popen([safe_str(colormgr)] + args, stdout=sp.PIPE,
					 stderr=sp.STDOUT)
		stdout, stderr = p.communicate()
	except Exception, exception:
		raise CDError(safe_str(exception))
	else:
		errmsg = "Could not find %s for %s" % (what, search)
		if p.returncode != 0:
			raise CDObjectQueryError(stdout.strip() or errmsg)
		result = stdout.strip()
		if not result:
			raise CDObjectNotFoundError(errmsg)
	return result


def get_default_profile(device_id):
	"""
	Get default profile filename for device
	
	"""
	if not Colord:
		colormgr = which("colormgr")
		if not colormgr:
			raise CDError("colormgr helper program not found")

		# Find device object path
		device = get_object_path(device_id, "device")
		
		# Get default profile
		try:
			p = sp.Popen([safe_str(colormgr), "device-get-default-profile",
						  device],
						 stdout=sp.PIPE, stderr=sp.STDOUT)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))
		else:
			errmsg = "Couldn't get default profile for device %s" % device_id
			if p.returncode != 0:
				raise CDError(stdout.strip() or errmsg)
			match = re.search(":\s*([^\r\n]+\.ic[cm])", stdout, re.I)
			if match:
				return safe_unicode(match.groups()[0])
			else:
				raise CDError(errmsg)
		
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


def get_object_path(search, object_type):
	result = find(object_type, search)
	if result:
		result = result.splitlines()[0].split(":", 1)[-1].strip()
	if not result:
		raise CDObjectNotFoundError("Could not find object path for %s" % search)
	return result


def install_profile(device_id, profile, profile_installname=None,
					timeout=5, logfn=None):
	"""
	Install profile for device
	
	profile_installname   filename of the installed profile (full path).
						  The profile is copied to this location.
						  If profile_installname is None, it defaults to
						  ~/.local/share/icc/<profile basename>
	timeout				  Time to allow for colord to pick up new profiles
						  (recommended not below 2 secs)
	
	"""

	if profile.ID == "\0" * 16:
		profile.calculateID()
	profile_id = "icc-" + hexlify(profile.ID)

	# Write profile to destination
	if not profile_installname:
		profile_installname = os.path.join(xdg_data_home, 'icc',
										   os.path.basename(profile.fileName))
	profile_installdir = os.path.dirname(profile_installname)
	if not os.path.isdir(profile_installdir):
		os.makedirs(profile_installdir)
	profile.write(profile_installname)
	
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
	for i in xrange(int(timeout / 1.0)):
		try:
			if Colord:
				profile = client.find_profile_sync(profile_id, cancellable)
			else:
				profile = get_object_path(profile_id, "profile")
		except CDObjectQueryError, exception:
			# Profile not found
			pass
		if profile:
			break
		# Give colord time to pick up the profile
		sleep(1)

	if not profile:
		raise CDTimeout("Querying for profile %r returned no result for %s secs" %
						(profile_id, timeout))

	errmsg = "Could not make profile %s default for device %s" % (profile_id,
																  device_id)

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
			warnings.warn(safe_str(exception), Warning)

		# Make profile default for device
		if not device.make_profile_default_sync(profile, cancellable):
			raise CDError(errmsg)
	else:
		# Find device object path
		device = get_object_path(device_id, "device")
		
		if logfn:
			logfn("-" * 80)
			logfn(lang.getstr("commandline"))

		from worker import printcmdline

		cmd = safe_str(colormgr)

		# Add profile to device
		# (Ignore returncode as profile may already have been added)
		args = [cmd, "device-add-profile", device, profile]
		printcmdline(args[0], args[1:], fn=logfn)
		if logfn:
			logfn("")
		try:
			p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))
		if logfn and stdout.strip():
			logfn(stdout.strip())

		if logfn:
			logfn("")
			logfn(lang.getstr("commandline"))

		# Make profile default for device
		args = [cmd, "device-make-profile-default", device, profile]
		printcmdline(args[0], args[1:], fn=logfn)
		if logfn:
			logfn("")
		try:
			p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
			stdout, stderr = p.communicate()
		except Exception, exception:
			raise CDError(safe_str(exception))
		else:
			if p.returncode != 0:
				raise CDError(stdout.strip() or errmsg)
		if logfn and stdout.strip():
			logfn(stdout.strip())


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


class CDObjectQueryError(CDError):
	pass


class CDObjectNotFoundError(CDObjectQueryError):
	pass


class CDTimeout(CDError):
	pass


if __name__ == "__main__":
	import sys
	for arg in sys.argv[1:]:
		print get_default_profile(arg)
