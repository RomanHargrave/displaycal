#!/usr/bin/env python
# -*- coding: utf-8 -*-

from hashlib import md5
import os
import struct
import sys
xrandr = None
if sys.platform == "win32":
	if sys.getwindowsversion() >= (6, ):
		# Use WMI for Vista/Win7
		import wmi
		wmi_connection = wmi.WMI(namespace="WMI")
	else:
		# Use registry as fallback for Win2k/XP/2003
		import _winreg
		wmi_connection = None
	import win32api
elif sys.platform != "darwin":
	try:
		import xrandr
	except ImportError:
		pass

atoz = dict([(i, char) for i, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")])
pnpidcache = {}

def COMBINE_HI_8LO(hi, lo):
	return hi << 8 | lo


def get_edid(display_no):
	""" Get and parse EDID. Return dict. """
	edid_data = None
	if sys.platform == "win32":
		# The ordering will work as long as Argyll continues using
		# EnumDisplayMonitors
		monitors = win32api.EnumDisplayMonitors(None, None)
		moninfo = win32api.GetMonitorInfo(monitors[display_no][0])
		device = win32api.EnumDisplayDevices(moninfo["Device"])
		id = device.DeviceID.split("\\")[1]
		if wmi_connection:
			# Use WMI for Vista/Win7
			# http://msdn.microsoft.com/en-us/library/Aa392707
			try:
				msmonitors = wmi_connection.WmiMonitorDescriptorMethods()
			except AttributeError, exception:
				raise WMIConnectionAttributeError(exception)
			for msmonitor in msmonitors:
				if msmonitor.InstanceName.split("\\")[1] == id:
					try:
						edid_data = msmonitor.WmiGetMonitorRawEEdidV1Block(0)
					except:
						# No EDID entry
						pass
					else:
						edid_data = "".join(chr(i) for i in edid_data[0])
					break
		else:
			# Use registry as fallback for Win2k/XP/2003
			# http://msdn.microsoft.com/en-us/library/ff546173%28VS.85%29.aspx
			# "The Enum tree is reserved for use by operating system components, 
			#  and its layout is subject to change. (...) Drivers and Windows 
			#  applications must not access the Enum tree directly."
			# But do we care? Probably not, as older Windows' API isn't likely
			# gonna change.
			driver = "\\".join(device.DeviceID.split("\\")[-2:])
			subkey = "\\".join(["SYSTEM", "CurrentControlSet", "Enum", 
								"DISPLAY", id])
			key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, subkey)
			numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
			for i in range(numsubkeys):
				hkname = _winreg.EnumKey(key, i)
				hk = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, 
									 "\\".join([subkey, hkname]))
				if _winreg.QueryValueEx(hk, "Driver")[0] == driver:
					# Found our display device
					devparms = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, 
									 "\\".join([subkey, hkname, 
												"Device Parameters"]))
					try:
						edid_data = _winreg.QueryValueEx(devparms, "EDID")[0]
					except WindowsError:
						# No EDID entry
						pass
	elif xrandr:
		# Check XrandR output properties
		edid_data = None
		for key in ("EDID", "EDID_DATA"):
			try:
				edid_data = xrandr.get_output_property(display_no, key, 
													   xrandr.XA_INTEGER)
			except ValueError:
				pass
			else:
				break
		if not edid_data:
			# Check X11 atoms
			for key in ("XFree86_DDC_EDID1_RAWDATA", 
						"XFree86_DDC_EDID2_RAWDATA"):
				if display_no > 0:
					key += "_%s" % display_no
				try:
					edid_data = xrandr.get_atom(key)
				except ValueError:
					pass
				else:
					break
		if edid_data:
			edid_data = "".join(chr(i) for i in edid_data)
	if edid_data and len(edid_data) >= 128:
		return parse_edid(edid_data)
	return {}


def parse_manufacturer_id(block):
	""" Parse the manufacturer id and return decoded string. """
	h = COMBINE_HI_8LO(ord(block[0]), ord(block[1]))
	manufacturer_id = []
	manufacturer_id.append(atoz.get(((h>>10) & 0x1f) - 1, ""))
	manufacturer_id.append(atoz.get(((h>>5) & 0x1f) - 1, ""))
	manufacturer_id.append(atoz.get((h & 0x1f) - 1, ""))
	return "".join(manufacturer_id).strip()


def get_manufacturer_name(manufacturer_id):
	""" Try and get a nice descriptive string for our manufacturer id.
	This uses pnp.ids which will be looked for in several places.
	If it can't find the file, it simply returns the manufacturer id.
	
	Examples:
	SAM -> Samsung Electric Company
	NEC -> NEC Corporation
	
	pnp.ids can be created from Excel data available from Microsoft:
	http://www.microsoft.com/whdc/system/pnppwr/pnp/pnpid.mspx
	
	"""
	if not pnpidcache:
		paths = ["/usr/share/hwdata/pnp.ids",  # hwdata, e.g. Red Hat
				 "/usr/share/misc/pnp.ids",  # pnputils, e.g. Debian
				 "/usr/share/libgnome-desktop/pnp.ids",  # fallback gnome-desktop
				 os.path.join(os.path.dirname(sys.executable 
											  if getattr(sys, 'frozen', 
														 False) else 
											  os.path.abspath(__file__)), 
							  "pnp.ids")]  # fallback
		for path in paths:
			if os.path.isfile(path):
				try:
					pnp_ids = open(path, "r")
				except IOError:
					pass
				else:
					try:
						for line in pnp_ids:
							try:
								id, name = line.strip().split(None, 1)
							except ValueError:
								continue
							pnpidcache[id] = name
					except OSError:
						pass
					pnp_ids.close()
	return pnpidcache.get(manufacturer_id, manufacturer_id)


def parse_edid(edid):
	""" Parse raw EDID data (binary string) and return dict. """
	hash = md5(edid).hexdigest()
	header = edid[0:8]
	manufacturer_id = parse_manufacturer_id(edid[8:10])
	manufacturer = get_manufacturer_name(manufacturer_id)
	
	product_id = struct.unpack("<H", edid[10:12])[0]
	serial_32 = struct.unpack("<I", edid[12:16])[0]
	week_of_manufacture = ord(edid[16])
	year_of_manufacture = ord(edid[17]) + 1990
	edid_version = ord(edid[18])
	edid_revision = ord(edid[19])
	
	max_h_size_cm = ord(edid[21])
	max_v_size_cm = ord(edid[22])
	gamma = ord(edid[23]) / 100.0 + 1
	features = ord(edid[24])
	
	# descriptor blocks
	for block in (edid[54:72], edid[72:90], edid[90:108], edid[108:126]):
		#if "\0" in (block[0], block[1]):
		block_type = block[3]
		if block_type == "\xff":
			# Monitor serial
			serial_ascii = block[5:18].strip()
		elif block_type == "\xfe":
			# ASCII
			ascii = block[5:18].strip()
		elif block_type == "\xfc":
			# Monitor name
			monitor_name = block[5:18].strip()
		#else:
			#pixel_clock_lsb = ord(block[0])
			#pixel_clock_msb = ord(block[1])
	del block, block_type
	
	result = locals()
	
	return result


class WMIConnectionAttributeError(AttributeError):
	pass
