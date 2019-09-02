# -*- coding: utf-8 -*-

import decimal
Decimal = decimal.Decimal
import os
import traceback
from time import strftime

from debughelpers import Error
from options import debug
from ordereddict import OrderedDict
from safe_print import safe_print
from util_io import StringIOu as StringIO
from util_str import safe_unicode
import CGATS
import ICCProfile as ICCP
import colormath
import localization as lang

cals = {}

def quote_nonoption_args(args):
	""" Puts quotes around all arguments which are not options 
	(ie. which do not start with a hyphen '-')
	
	"""
	args = list(args)
	for i, arg in enumerate(args):
		if arg[0] != "-":
			args[i] = '"' + arg + '"'
	return args


def add_dispcal_options_to_cal(cal, options_dispcal):
	# Add dispcal options to cal
	options_dispcal = quote_nonoption_args(options_dispcal)
	try:
		cgats = CGATS.CGATS(cal)
		cgats[0].add_section("ARGYLL_DISPCAL_ARGS", 
							 " ".join(options_dispcal).encode("UTF-7", 
															  "replace"))
		return cgats
	except Exception, exception:
		safe_print(safe_unicode(traceback.format_exc()))


def add_options_to_ti3(ti3, options_dispcal=None, options_colprof=None):
	# Add dispcal and colprof options to ti3
	try:
		cgats = CGATS.CGATS(ti3)
		if options_colprof:
			options_colprof = quote_nonoption_args(options_colprof)
			cgats[0].add_section("ARGYLL_COLPROF_ARGS", 
							   " ".join(options_colprof).encode("UTF-7", 
																"replace"))
		if options_dispcal and 1 in cgats:
			options_dispcal = quote_nonoption_args(options_dispcal)
			cgats[1].add_section("ARGYLL_DISPCAL_ARGS", 
							   " ".join(options_dispcal).encode("UTF-7", 
																"replace"))
		return cgats
	except Exception, exception:
		safe_print(safe_unicode(traceback.format_exc()))


def cal_to_fake_profile(cal):
	""" 
	Create and return a 'fake' ICCProfile with just a vcgt tag.
	
	cal must refer to a valid Argyll CAL file and can be a CGATS instance 
	or a filename.
	
	"""
	vcgt, cal = cal_to_vcgt(cal, True)
	if not vcgt:
		return
	profile = ICCP.ICCProfile()
	profile.fileName = cal.filename
	profile._data = "\0" * 128
	profile._tags.desc = ICCP.TextDescriptionType("", "desc")
	profile._tags.desc.ASCII = safe_unicode(
				os.path.basename(cal.filename)).encode("ascii", "asciize")
	profile._tags.desc.Unicode = safe_unicode(os.path.basename(cal.filename))
	profile._tags.vcgt = vcgt
	profile.size = len(profile.data)
	profile.is_loaded = True
	return profile


def cal_to_vcgt(cal, return_cgats=False):
	""" 
	Create a vcgt tag from calibration data.
	
	cal must refer to a valid Argyll CAL file and can be a CGATS instance 
	or a filename.
	
	"""
	if not isinstance(cal, CGATS.CGATS):
		try:
			cal = CGATS.CGATS(cal)
		except (IOError, CGATS.CGATSInvalidError, 
			CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
			CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			safe_print(u"Warning - couldn't process CGATS file '%s': %s" % 
					   tuple(safe_unicode(s) for s in (cal, exception)))
			return None
	required_fields = ("RGB_I", "RGB_R", "RGB_G", "RGB_B")
	data_format = cal.queryv1("DATA_FORMAT")
	if data_format:
		for field in required_fields:
			if not field in data_format.values():
				if debug: safe_print("[D] Missing required field:", field)
				return None
		for field in data_format.values():
			if not field in required_fields:
				if debug: safe_print("[D] Unknown field:", field)
				return None
	entries = cal.queryv(required_fields)
	if len(entries) < 1:
		if debug: safe_print("[D] No entries found in calibration",
							 cal.filename)
		return None
	vcgt = ICCP.VideoCardGammaTableType("", "vcgt")
	vcgt.update({
		"channels": 3,
		"entryCount": len(entries),
		"entrySize": 2,
		"data": [[], [], []]
	})
	for n in entries:
		for i in range(3):
			vcgt.data[i].append(entries[n][i + 1] * 65535.0)
	if return_cgats:
		return vcgt, cal
	return vcgt
	


def can_update_cal(path):
	""" Check if cal can be updated by checking for required fields. """
	try:
		calstat = os.stat(path)
	except Exception, exception:
		safe_print(u"Warning - os.stat('%s') failed: %s" % 
				   tuple(safe_unicode(s) for s in (path, exception)))
		return False
	if not path in cals or cals[path].mtime != calstat.st_mtime:
		try:
			cal = CGATS.CGATS(path)
		except (IOError, CGATS.CGATSInvalidError, 
			CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
			CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			if path in cals:
				del cals[path]
			safe_print(u"Warning - couldn't process CGATS file '%s': %s" % 
					   tuple(safe_unicode(s) for s in (path, exception)))
		else:
			if cal.queryv1("DEVICE_CLASS") == "DISPLAY" and not None in \
			   (cal.queryv1("TARGET_WHITE_XYZ"), 
				cal.queryv1("TARGET_GAMMA"), 
				cal.queryv1("BLACK_POINT_CORRECTION"), 
				cal.queryv1("QUALITY")):
				cals[path] = cal
	return path in cals and cals[path].mtime == calstat.st_mtime


def extract_cal_from_profile(profile, out_cal_path=None,
							 raise_on_missing_cal=True,
							 prefer_cal=False):
	""" Extract calibration from 'targ' tag in profile or vcgt as fallback """

	white = False

	# Check if calibration is included in TI3
	targ = profile.tags.get("targ", profile.tags.get("CIED"))
	if isinstance(targ, ICCP.Text):
		cal = extract_cal_from_ti3(targ)
		if cal:
			check = cal
			get_cgats = CGATS.CGATS
			arg = cal
	else:
		cal = None
	if not cal:
		# Convert calibration information from embedded WCS profile
		# (if present) to VideCardFormulaType if the latter is not present
		if (isinstance(profile.tags.get("MS00"), ICCP.WcsProfilesTagType) and
			not "vcgt" in profile.tags):
			profile.tags["vcgt"] = profile.tags["MS00"].get_vcgt()

		# Get the calibration from profile vcgt
		check = isinstance(profile.tags.get("vcgt"),
						   ICCP.VideoCardGammaType)
		get_cgats = vcgt_to_cal
		arg = profile

	if not check:
		if raise_on_missing_cal:
			raise Error(lang.getstr("profile.no_vcgt"))
		else:
			return False
	else:
		try:
			cgats = get_cgats(arg)
		except (IOError, CGATS.CGATSError), exception:
			raise Error(lang.getstr("cal_extraction_failed"))
	if (cal and not prefer_cal and isinstance(profile.tags.get("vcgt"),
											  ICCP.VideoCardGammaType)):
		# When vcgt is nonlinear, prefer it
		# Check for video levels encoding
		if cgats.queryv1("TV_OUTPUT_ENCODING") == "YES":
			black, white = (16, 235)
		else:
			output_enc = cgats.queryv1("OUTPUT_ENCODING")
			if output_enc:
				try:
					black, white = (float(v) for v in
									output_enc.split())
				except (TypeError, ValueError):
					white = False
		cgats = vcgt_to_cal(profile)
		if white and (black, white) != (0, 255):
			safe_print("Need to un-scale vcgt from video levels (%s..%s)" %
					   (black, white))
			# Need to un-scale video levels
			data = cgats.queryv1("DATA")
			if data:
				safe_print("Un-scaling vcgt from video levels (%s..%s)" %
						   (black, white))
				encoding_mismatch = False
				# For video encoding the extra bits of
				# precision are created by bit shifting rather
				# than scaling, so we need to scale the fp
				# value to account for this
				oldmin = (black / 256.0) * (65536 / 65535.)
				oldmax = (white / 256.0) * (65536 / 65535.)
				for entry in data.itervalues():
					for column in "RGB":
						v_old = entry["RGB_" + column]
						lvl = round(v_old * (65535 / 65536.) * 256, 2)
						if lvl < round(black, 2) or lvl > round(white, 2):
							# Can't be right. Metadata says it's video encoded,
							# but clearly exceeds the encoding range.
							safe_print("Warning: Metadata claims video levels "
									   "(%s..%s) but vcgt value %s exceeds "
									   "encoding range. Using values as-is." %
									   (round(black, 2), round(white, 2), lvl))
							encoding_mismatch = True
							break
						v_new = colormath.convert_range(v_old, oldmin, oldmax, 0, 1)
						entry["RGB_" + column] = min(max(v_new, 0), 1)
					if encoding_mismatch:
						break
				if encoding_mismatch:
					cgats = vcgt_to_cal(profile)
				# Add video levels hint to CGATS
				elif (black, white) == (16, 235):
					cgats[0].add_keyword("TV_OUTPUT_ENCODING", "YES")
				else:
					cgats[0].add_keyword("OUTPUT_ENCODING",
										 " ".join(str(v) for v in (black, white)))
			else:
				safe_print("Warning - no un-scaling applied - no "
						   "calibration data!")
	if out_cal_path:
		cgats.write(out_cal_path)
	return cgats


def extract_cal_from_ti3(ti3):
	"""
	Extract and return the CAL section of a TI3.
	
	ti3 can be a file object or a string holding the data.
	
	"""
	if isinstance(ti3, CGATS.CGATS):
		ti3 = str(ti3)
	if isinstance(ti3, basestring):
		ti3 = StringIO(ti3)
	cal = False
	cal_lines = []
	for line in ti3:
		line = line.strip()
		if line == "CAL":
			line = "CAL    "  # Make sure CGATS file identifiers are 
							  # always a minimum of 7 characters
			cal = True
		if cal:
			cal_lines.append(line)
			if line == 'END_DATA':
				break
	if isinstance(ti3, file):
		ti3.close()
	return "\n".join(cal_lines)


def extract_fix_copy_cal(source_filename, target_filename=None):
	"""
	Return the CAL section from a profile's embedded measurement data.
	
	Try to 'fix it' (add information needed to make the resulting .cal file
	'updateable') and optionally copy it to target_filename.
	
	"""
	from worker import get_options_from_profile
	try:
		profile = ICCP.ICCProfile(source_filename)
	except (IOError, ICCP.ICCProfileInvalidError), exception:
		return exception
	if "CIED" in profile.tags or "targ" in profile.tags:
		cal_lines = []
		ti3 = StringIO(profile.tags.get("CIED", "") or 
					   profile.tags.get("targ", ""))
		ti3_lines = [line.strip() for line in ti3]
		ti3.close()
		cal_found = False
		for line in ti3_lines:
			line = line.strip()
			if line == "CAL":
				line = "CAL    "  # Make sure CGATS file identifiers are 
								  #always a minimum of 7 characters
				cal_found = True
			if cal_found:
				cal_lines.append(line)
				if line == 'DEVICE_CLASS "DISPLAY"':
					options_dispcal = get_options_from_profile(profile)[0]
					if options_dispcal:
						whitepoint = False
						b = profile.tags.lumi.Y
						for o in options_dispcal:
							if o[0] == "y":
								cal_lines.append('KEYWORD "DEVICE_TYPE"')
								if o[1] == "c":
									cal_lines.append('DEVICE_TYPE "CRT"')
								else:
									cal_lines.append('DEVICE_TYPE "LCD"')
								continue
							if o[0] in ("t", "T"):
								continue
							if o[0] == "w":
								continue
							if o[0] in ("g", "G"):
								if o[1:] == "240":
									trc = "SMPTE240M"
								elif o[1:] == "709":
									trc = "REC709"
								elif o[1:] == "l":
									trc = "L_STAR"
								elif o[1:] == "s":
									trc = "sRGB"
								else:
									trc = o[1:]
									if o[0] == "G":
										try:
											trc = 0 - Decimal(trc)
										except decimal.InvalidOperation, \
											   exception:
											continue
								cal_lines.append('KEYWORD "TARGET_GAMMA"')
								cal_lines.append('TARGET_GAMMA "%s"' % trc)
								continue
							if o[0] == "f":
								cal_lines.append('KEYWORD '
									'"DEGREE_OF_BLACK_OUTPUT_OFFSET"')
								cal_lines.append(
									'DEGREE_OF_BLACK_OUTPUT_OFFSET "%s"' % 
									o[1:])
								continue
							if o[0] == "k":
								cal_lines.append('KEYWORD '
									'"BLACK_POINT_CORRECTION"')
								cal_lines.append(
									'BLACK_POINT_CORRECTION "%s"' % o[1:])
								continue
							if o[0] == "B":
								cal_lines.append('KEYWORD '
									'"TARGET_BLACK_BRIGHTNESS"')
								cal_lines.append(
									'TARGET_BLACK_BRIGHTNESS "%s"' % o[1:])
								continue
							if o[0] == "q":
								if o[1] == "l":
									q = "low"
								elif o[1] == "m":
									q = "medium"
								else:
									q = "high"
								cal_lines.append('KEYWORD "QUALITY"')
								cal_lines.append('QUALITY "%s"' % q)
								continue
						if not whitepoint:
							cal_lines.append('KEYWORD "NATIVE_TARGET_WHITE"')
							cal_lines.append('NATIVE_TARGET_WHITE ""')
		if cal_lines:
			if target_filename:
				try:
					f = open(target_filename, "w")
					f.write("\n".join(cal_lines))
					f.close()
				except Exception, exception:
					return exception
			return cal_lines
	else:
		return None


def extract_device_gray_primaries(ti3, gray=True, logfn=None,
								  include_neutrals=False,
								  neutrals_ab_threshold=0.1):
	"""
	Extract gray or primaries into new TI3
	
	Return extracted ti3, extracted RGB to XYZ mapping and remaining RGB to XYZ

	"""
	filename = ti3.filename
	ti3 = ti3.queryi1("DATA")
	ti3.filename = filename
	ti3_extracted = CGATS.CGATS("""CTI3
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB_XYZ"
BEGIN_DATA_FORMAT
END_DATA_FORMAT
BEGIN_DATA
END_DATA""")[0]
	ti3_extracted.DATA_FORMAT.update(ti3.DATA_FORMAT)
	subset = [(100.0, 100.0, 100.0),
			  (0.0, 0.0, 0.0)]
	if not gray:
		subset.extend([(100.0, 0.0, 0.0),
					   (0.0, 100.0, 0.0),
					   (0.0, 0.0, 100.0),
					   (50.0, 50.0, 50.0)])
		if logfn:
			logfn(u"Extracting neutrals and primaries from %s" %
				  ti3.filename)
	else:
		if logfn:
			logfn(u"Extracting neutrals from %s" %
				  ti3.filename)
	RGB_XYZ_extracted = OrderedDict()
	RGB_XYZ_remaining = OrderedDict()
	dupes = {}
	if include_neutrals:
		white = ti3.get_white_cie("XYZ")
		str_thresh = str(neutrals_ab_threshold)
		round_digits = len(str_thresh[str_thresh.find(".") + 1:])
	for i, item in ti3.DATA.iteritems():
		if not i:
			# Check if fields are missing
			for prefix in ("RGB", "XYZ"):
				for suffix in prefix:
					key = "%s_%s" % (prefix, suffix)
					if not key in item:
						raise Error(lang.getstr("error.testchart.missing_fields",
												(ti3.filename, key)))
		RGB = (item["RGB_R"], item["RGB_G"], item["RGB_B"])
		XYZ = (item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"])
		for RGB_XYZ in (RGB_XYZ_extracted, RGB_XYZ_remaining):
			if RGB in RGB_XYZ:
				if RGB != (100.0, 100.0, 100.0):
					# Add to existing values for averaging later
					# if it's not white (all other readings are scaled to the
					# white Y by dispread, so we don't alter it. Note that it's
					# always the first encountered white that will have Y = 100,
					# even if subsequent white readings may be higher)
					XYZ = tuple(RGB_XYZ[RGB][i] + XYZ[i]
								for i in xrange(3))
					if not RGB in dupes:
						dupes[RGB] = 1.0
					dupes[RGB] += 1.0
				elif RGB in subset:
					# We have white already, remove it from the subset so any
					# additional white readings we encounter are ignored
					subset.remove(RGB)
		if ((gray and
			 (item["RGB_R"] == item["RGB_G"] == item["RGB_B"] or
			  (include_neutrals and
			   all(round(abs(v), round_digits) <= neutrals_ab_threshold
				   for v in colormath.XYZ2Lab(item["XYZ_X"],
											  item["XYZ_Y"],
											  item["XYZ_Z"],
											  whitepoint=white)[1:]))) and
			 not RGB in [(100.0, 100.0, 100.0),
						 (0.0, 0.0, 0.0)]) or
			RGB in subset):
			ti3_extracted.DATA.add_data(item)
			RGB_XYZ_extracted[RGB] = XYZ
		elif not RGB in [(100.0, 100.0, 100.0),
						 (0.0, 0.0, 0.0)]:
			RGB_XYZ_remaining[RGB] = XYZ
	for RGB, count in dupes.iteritems():
		for RGB_XYZ in (RGB_XYZ_extracted, RGB_XYZ_remaining):
			if RGB in RGB_XYZ:
				# Average values
				XYZ = tuple(RGB_XYZ[RGB][i] / count for i in xrange(3))
				RGB_XYZ[RGB] = XYZ
	return ti3_extracted, RGB_XYZ_extracted, RGB_XYZ_remaining


def ti3_to_ti1(ti3_data):
	"""
	Create and return TI1 data converted from TI3.
	
	ti3_data can be a file object, a list of strings or a string holding the data.
	
	"""
	ti3 = CGATS.CGATS(ti3_data)
	if not ti3:
		return ""
	ti3[0].type = "CTI1"
	ti3[0].DESCRIPTOR = "Argyll Calibration Target chart information 1"
	ti3[0].ORIGINATOR = "Argyll targen"
	if hasattr(ti3[0], "COLOR_REP"):
		color_rep = ti3[0].COLOR_REP.split('_')[0]
	else:
		color_rep = "RGB"
	ti3[0].add_keyword("COLOR_REP", color_rep)
	ti3[0].remove_keyword("DEVICE_CLASS")
	if hasattr(ti3[0], "LUMINANCE_XYZ_CDM2"):
		ti3[0].remove_keyword("LUMINANCE_XYZ_CDM2")
	if hasattr(ti3[0], "ARGYLL_COLPROF_ARGS"):
		del ti3[0].ARGYLL_COLPROF_ARGS
	return str(ti3[0])


def vcgt_to_cal(profile):
	""" Return a CAL (CGATS instance) from vcgt """
	cgats = CGATS.CGATS(file_identifier="CAL")
	context = cgats.add_data({"DESCRIPTOR": "Argyll Device Calibration State"})
	context.add_data({"ORIGINATOR": "vcgt"})
	context.add_data({"CREATED": strftime("%a %b %d %H:%M:%S %Y",
										  profile.dateTime.timetuple())})
	context.add_keyword("DEVICE_CLASS", "DISPLAY")
	context.add_keyword("COLOR_REP", "RGB")
	context.add_keyword("RGB_I")
	key = "DATA_FORMAT"
	context[key] = CGATS.CGATS()
	context[key].key = key
	context[key].parent = context
	context[key].root = cgats
	context[key].type = key
	context[key].add_data(("RGB_I", "RGB_R", "RGB_G", "RGB_B"))
	key = "DATA"
	context[key] = CGATS.CGATS()
	context[key].key = key
	context[key].parent = context
	context[key].root = cgats
	context[key].type = key
	values = profile.tags.vcgt.getNormalizedValues()
	for i, triplet in enumerate(values):
		context[key].add_data(("%.7f" % (i / float(len(values) - 1)), ) + triplet)
	return cgats


def verify_cgats(cgats, required, ignore_unknown=True):
	"""
	Verify and return a CGATS instance or None on failure.
	
	Verify if a CGATS instance has a section with all required fields. 
	Return the section as CGATS instance on success, None on failure.
	
	If ignore_unknown evaluates to True, ignore fields which are not required.
	Otherwise, the CGATS data must contain only the required fields, no more,
	no less.
	"""
	cgats_1 = cgats.queryi1(required)
	if cgats_1 and cgats_1.parent and cgats_1.parent.parent:
		cgats_1 = cgats_1.parent.parent
		if cgats_1.queryv1("NUMBER_OF_SETS"):
			if cgats_1.queryv1("DATA_FORMAT"):
				for field in required:
					if not field in cgats_1.queryv1("DATA_FORMAT").values():
						raise CGATS.CGATSKeyError("Missing required field: %s" % field)
				if not ignore_unknown:
					for field in cgats_1.queryv1("DATA_FORMAT").values():
						if not field in required:
							raise CGATS.CGATSError("Unknown field: %s" % field)
			else:
				raise CGATS.CGATSInvalidError("Missing DATA_FORMAT")
		else:
			raise CGATS.CGATSInvalidError("Missing NUMBER_OF_SETS")
		modified = cgats_1.modified
		cgats_1.filename = cgats.filename
		cgats_1.modified = modified
		return cgats_1
	else:
		raise CGATS.CGATSKeyError("Missing required fields: %s" % 
								  ", ".join(required))

def verify_ti1_rgb_xyz(cgats):
	"""
	Verify and return a CGATS instance or None on failure.
	
	Verify if a CGATS instance has a TI1 section with all required fields 
	for RGB devices. Return the TI1 section as CGATS instance on success, 
	None on failure.
	
	"""
	return verify_cgats(cgats, ("RGB_R", "RGB_B", "RGB_G", 
								"XYZ_X", "XYZ_Y", "XYZ_Z"))
