#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ctypes import cdll, util
from hashlib import md5
import os
import shutil
from time import sleep, time

from gtypes import GError, gchar_p
from defaultpaths import xdg_data_home


CD_DEVICE_RELATION_HARD = 2

colord = cdll.LoadLibrary(util.find_library('colord'))


def cd_client_connect():
	""" Connect to colord """
	colord.g_type_init()
	client = colord.cd_client_new()
	error = GError()

	# Connect to colord
	if not colord.cd_client_connect_sync(client, None, error):
		raise CDError("No connection to colord: %s" % error.message.value)
	return client


def cd_device_connect(client, device_key):
	""" Connect to device """
	if isinstance(device_key, unicode):
		device_key = device_key.encode('UTF-8')
	device_object_path = '/org/freedesktop/ColorManager/devices/%s' % device_key.replace('-', '_').replace(' ', '_')
	device = colord.cd_device_new_with_object_path(device_object_path)
	error = GError()
	
	# Check is valid object path
	if not colord.g_variant_is_object_path(device_object_path):
		raise CDError("Not a valid object path: %s" % device_object_path)

	# Connect to device
	if not colord.cd_device_connect_sync(device, None, error):
		raise CDError("Device does not exist: %s" % device_object_path)
	return device


def cd_get_default_profile(device_key):
	"""
	Get default profile filename for device
	
	device_key   object path without /org/freedesktop/ColorManager/devices/
	
	"""
	client = cd_client_connect()
	error = GError()

	# Connect to existing device
	device = cd_device_connect(client, device_key)
	
	# Get default profile
	profile = colord.cd_device_get_default_profile(device)
	if not profile:
		# No assigned device
		return

	# Connect to profile
	if not colord.cd_profile_connect_sync(profile, None, error):
		raise CDError(error.message.value)
	return gchar_p(colord.cd_profile_get_filename(profile)).value.decode('UTF-8')


def cd_install_profile(device_key, profile_filename, profile_installname=None,
					   timeout=2):
	"""
	Install profile for device
	
	device_key 			  object path without /org/freedesktop/ColorManager/devices/
	profile_installname   filename of the installed profile (full path).
						  The profile is copied to this location.
						  If profile_installname is None, it defaults to
						  ~/.local/share/icc/<profile basename>
	timeout				  Time to allow for colord to pick up new profiles
						  (recommended not below 2 secs)
	
	"""
	client = cd_client_connect()
	error = GError()

	# Connect to existing device
	device = cd_device_connect(client, device_key)

	# Copy profile
	if not profile_installname:
		profile_installname = os.path.join(xdg_data_home, 'icc',
										   os.path.basename(profile_filename))
	shutil.copyfile(profile_filename, profile_installname)
	
	if isinstance(profile_installname, unicode):
		profile_installname = profile_installname.encode('UTF-8')

	# Query colord for newly added profile
	for i in xrange(int(timeout / .05)):
		profile = colord.cd_client_find_profile_by_filename_sync(client,
																 profile_installname,
																 None, error)
		if profile:
			break
		# Give colord time to pick up the profile
		sleep(.05)

	if not profile:
		if error.message.value:
			raise CDError(error.message.value)
		else:
			raise CDError("Querying for profile returned empty result for %s secs: %s"
						  % (timeout, profile_installname))

	# Connect to profile
	if not colord.cd_profile_connect_sync(profile, None, error):
		raise CDError(error.message.value)

	# Add profile to device
	if not colord.cd_device_add_profile_sync(device, CD_DEVICE_RELATION_HARD,
											 profile, None, error):
		# Profile may already have been added
		pass

	# Make profile default for device
	if not colord.cd_device_make_profile_default(device, profile, None, error):
		raise CDError("Could not make profile default for device: %s" %
					  error.message.value)


class CDError(Exception):
	pass
