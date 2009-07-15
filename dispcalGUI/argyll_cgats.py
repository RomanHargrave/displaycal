#!/usr/bin/env python
# -*- coding: utf-8 -*-

from StringIOu import StringIOu as StringIO
from safe_print import safe_print
import CGATS
import ICCProfile as ICCP

debug = False

def cal_to_fake_profile(cal):
	""" Create and return a 'fake' ICCProfile with just a vcgt tag from CAL data.
	cal can be a CGATS instance or a filename. """
	if not isinstance(cal, CGATS.CGATS):
		try:
			cal = CGATS.CGATS(cal)
		except (IOError, CGATS.CGATSInvalidError, 
			CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
			CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			safe_print("Warning - couldn't process CGATS file '%s': %s" % (cal, str(exception)))
			return None
	data_format = cal.queryv1("DATA_FORMAT")
	if data_format:
		required_fields = ("RGB_I", "RGB_R", "RGB_G", "RGB_B")
		for field in required_fields:
			if not field in data_format.values():
				if debug: safe_print("Missing required field:", field)
				return None
		for field in data_format.values():
			if not field in required_fields:
				if debug: safe_print("Unknown field:", field)
				return None
	entries = cal.queryv(required_fields)
	profile = ICCP.ICCProfile()
	profile.fileName = cal.filename
	profile._tags = ICCP.Dict()
	profile._tags.desc = os.path.basename(cal.filename)
	profile._tags.vcgt = ICCP.Dict({
		"channels": 3,
		"entryCount": len(entries),
		"entrySize": 2,
		"data": [[], [], []]
	})
	for n in entries:
		for i in range(3):
			profile._tags.vcgt.data[i].append(int(round(entries[n][i + 1] * 65535.0)))
	return profile

cals = {}

def can_update_cal(path):
	try:
		calstat = os.stat(path)
	except Exception, exception:
		safe_print("Warning - os.stat('%s') failed: %s" % (path, str(exception)))
		return False
	if not path in cals or cals[path].mtime != calstat.st_mtime:
		try:
			cal = CGATS.CGATS(path)
		except (IOError, CGATS.CGATSInvalidError, 
			CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
			CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			if path in cals:
				del cals[path]
			safe_print("Warning - couldn't process CGATS file '%s': %s" % (path, str(exception)))
		else:
			if cal.queryv1("DEVICE_TYPE") in ("CRT", "LCD") and \
			   not None in (cal.queryv1("TARGET_WHITE_XYZ"), 
			   cal.queryv1("TARGET_GAMMA"), 
			   cal.queryv1("BLACK_POINT_CORRECTION"), 
			   cal.queryv1("QUALITY")):
				cals[path] = cal
	return path in cals and cals[path].mtime == calstat.st_mtime

def extract_cal_from_ti3(ti3_data):
	""" Extract and return the CAL section of a TI3.
	ti3_data can be a file object or a string holding the data. """
	if isinstance(ti3_data, (str, unicode)):
		ti3 = StringIO(ti3_data)
	else:
		ti3 = ti3_data
	cal = False
	cal_lines = []
	for line in ti3:
		line = line.strip()
		if line == "CAL":
			line = "CAL    " # Make sure CGATS file identifiers are always a minimum of 7 characters
			cal = True
		if cal:
			cal_lines += [line]
			if line == 'END_DATA':
				break
	if isinstance(ti3, file):
		ti3.close()
	return "\n".join(cal_lines)

def ti3_to_ti1(ti3_data):
	""" Create and return TI1 data converted from TI3.
	ti3_data can be a file object or a string holding the data. """
	if isinstance(ti3_data, (str, unicode)):
		ti3 = StringIO(ti3_data)
	else:
		ti3 = ti3_data
	ti1_lines = []
	for line in ti3:
		line = line.strip()
		if line == "CTI3":
			line = 'CTI1   ' # Make sure CGATS file identifiers are always a minimum of 7 characters
		else:
			values = line.split()
			if len(values) > 1:
				if len(values) == 2:
					values[1] = values[1].strip('"')
					if values[0] == "DESCRIPTOR":
						values[1] = ("Argyll Calibration Target chart "
							"information 1")
					elif values[0] == "ORIGINATOR":
						values[1] = "Argyll targen"
					elif values[0] == "COLOR_REP":
						values[1] = values[1].split('_')[0]
				if "DEVICE_CLASS" in values or "LUMINANCE_XYZ_CDM2" in values:
					continue
				if len(values) > 2:
					line = " ".join(values)
				else:
					line = '%s "%s"' % tuple(values)
		ti1_lines += [line]
		if line == 'END_DATA':
			break
	if isinstance(ti3, file):
		ti3.close()
	return "\n".join(ti1_lines)

def verify_ti1_rgb_xyz(cgats):
	""" Verify if a CGATS instance has a TI1 section with all required fields for RGB
	devices. Return the TI1 section as CGATS instance on success, None on failure. """
	required = ("SAMPLE_ID", "RGB_R", "RGB_B", "RGB_G", "XYZ_X", "XYZ_Y", 
		"XYZ_Z")
	ti1_1 = cgats.queryi1(required)
	if ti1_1 and ti1_1.parent and ti1_1.parent.parent:
		ti1_1 = ti1_1.parent.parent
		if ti1_1.queryv1("NUMBER_OF_SETS"):
			if ti1_1.queryv1("DATA_FORMAT"):
				for field in required:
					if not field in ti1_1.queryv1("DATA_FORMAT").values():
						if debug: safe_print("Missing required field:", 
							field)
						return None
				for field in ti1_1.queryv1("DATA_FORMAT").values():
					if not field in required:
						if debug: safe_print("Unknown field:", field)
						return None
			else:
				if debug: safe_print("Missing DATA_FORMAT")
				return None
		else:
			if debug: safe_print("Missing DATA")
			return None
		ti1_1.filename = cgats.filename
		return ti1_1
	else:
		if debug: safe_print("Invalid TI1")
		return None
