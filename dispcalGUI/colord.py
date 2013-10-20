#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import shutil
import sys
from time import sleep

try:
	from gi.repository import Colord
	from gi.repository import Gio
except ImportError:
	Colord = None
	Gio = None
else:
	cancellable = Gio.Cancellable.new();

if sys.platform not in ("darwin", "win32"):
	from defaultpaths import xdg_data_home

if not Colord or not hasattr(Colord, 'quirk_vendor_name'):
	from config import get_data_path
	import demjson

	quirk_cache = {'suffixes': [],
				   'vendor_names': {}}


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


def device_id_from_edid(edid, quirk=True, use_unused_edid_keys=False):
	""" Assemble device key from EDID """
	# https://gitorious.org/colord/master/blobs/master/doc/device-and-profile-naming-spec.txt
	incomplete = False
	parts = ["xrandr"]
	if use_unused_edid_keys:
		# Not currently used by colord
		edid_keys = ["manufacturer", "monitor_name", "ascii", "serial_ascii",
					 "serial_32"]
	else:
		edid_keys = ["manufacturer", "monitor_name", "serial_ascii"]
	for name in edid_keys:
		value = edid.get(name)
		if value:
			if name == "serial_32" and "serial_ascii" in edid:
				# Only add numeric serial if no ascii serial
				continue
			elif name == "manufacturer" and quirk:
				value = quirk_manufacturer(value)
			parts.append(str(value))
		elif name == "manufacturer":
			# Do not allow the manufacturer to be missing or empty
			# TODO: Should fall back to xrandr name in that case
			incomplete = True
			break
	if not incomplete:
		return "-".join(parts)


def get_default_profile(device_id):
	"""
	Get default profile filename for device
	
	"""
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
	client = client_connect()

	# Connect to existing device
	device = device_connect(client, device_id)

	# Copy profile
	if not profile_installname:
		profile_installname = os.path.join(xdg_data_home, 'icc',
										   os.path.basename(profile_filename))
	shutil.copyfile(profile_filename, profile_installname)
	
	if isinstance(profile_installname, unicode):
		profile_installname = profile_installname.encode('UTF-8')

	# Query colord for newly added profile
	for i in xrange(int(timeout / .5)):
		try:
			profile = client.find_profile_by_filename_sync(profile_installname,
														   cancellable)
			if profile:
				break
		except Exception, exception:
			# Profile not found
			pass
		# Give colord time to pick up the profile
		sleep(.5)

	if not profile:
		raise CDError("Querying for profile %r returned no result for %s secs" %
					  (profile_installname, timeout))

	# Connect to profile
	if not profile.connect_sync(cancellable):
		raise CDError("Could not connect to profile")

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
