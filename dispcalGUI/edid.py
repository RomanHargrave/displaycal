#!/usr/bin/env python
# -*- coding: utf-8 -*-

from hashlib import md5
import os
import struct
try:
	import xrandr
except ImportError:
	xrandr = None

atoz = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
pnpidcache = {}

def COMBINE_HI_8LO(hi, lo):
	return hi << 8 | lo


if xrandr:
	def get_edid(display_no):
		""" Get and parse EDID. Return dict. """
		edid_data = None
		# Check XrandR output properties
		for key in ("EDID", "EDID_DATA"):
			edid_data = xrandr.get_output_property(display_no, key, 
												   xrandr.XA_INTEGER)
			if edid_data:
				break
		if not edid_data:
			# Check X11 atoms
			for key in ("XFree86_DDC_EDID1_RAWDATA", 
						"XFree86_DDC_EDID2_RAWDATA"):
				if display_no > 0:
					key += "_%s" % display_no
				edid_data = xrandr.get_atom(key, xrandr.XA_INTEGER)
				if edid_data:
					break
		if edid_data:
			return parse_edid("".join(chr(i) for i in edid_data))
		return {}


def parse_manufacturer_id(block):
	""" Parse the manufacturer id and return decoded string. """
	h = COMBINE_HI_8LO(ord(block[0]), ord(block[1]))
	manufacturer_id = []
	manufacturer_id.append(atoz[((h>>10) & 0x1f) - 1])
	manufacturer_id.append(atoz[((h>>5) & 0x1f) - 1])
	manufacturer_id.append(atoz[(h & 0x1f) - 1])
	return "".join(manufacturer_id).strip()


def get_manufacturer_name(manufacturer_id):
	""" Try and get a nice descriptive string for our manufacturer id.
	This uses pnp.ids which will be looked for in several places.
	If it can't find the file, it simply returns the manufacturer id.
	
	Examples:
	SAM -> Samsung Electric Company
	NEC -> NEC Corporation
	
	"""
	if not pnpidcache:
		paths = ["/usr/share/hwdata/pnp.ids",  # hwdata, e.g. Red Hat
				 "/usr/share/misc/pnp.ids",  # pnputils, e.g. Debian
				 "/usr/share/libgnome-desktop/pnp.ids"]  # fallback gnome-desktop
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
