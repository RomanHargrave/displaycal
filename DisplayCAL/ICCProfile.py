# -*- coding: utf-8 -*-

from __future__ import with_statement
from copy import copy
from hashlib import md5
import atexit
import binascii
import ctypes
import datetime
import locale
import math
import os
import re
import struct
import sys
import warnings
import zlib
from itertools import izip, imap
from time import localtime, mktime, strftime
from UserString import UserString
if sys.platform == "win32":
	import _winreg
else:
	import subprocess as sp
	if sys.platform == "darwin":
		from platform import mac_ver

if sys.platform == "win32":
	try:
		import win32api
		import win32gui
	except ImportError:
		pass

try:
	import colord
except ImportError:
	class Colord:
		Colord = None
		def quirk_manufacturer(self, manufacturer):
			return manufacturer
		def which(self, executable, paths=None):
			return None
	colord = Colord()
import colormath
import edid
import imfile
from colormath import NumberTuple
from defaultpaths import iccprofiles, iccprofiles_home
from encoding import get_encodings
from ordereddict import OrderedDict
try:
	from log import safe_print
except ImportError:
	from safe_print import safe_print
from util_decimal import float2dec
from util_list import intlist
from util_str import hexunescape, safe_str, safe_unicode

if sys.platform not in ("darwin", "win32"):
	from defaultpaths import xdg_config_dirs, xdg_config_home
	from edid import get_edid
	from util_x import get_display
	try:
		import xrandr
	except ImportError:
		xrandr = None
	from util_os import dlopen, which
elif sys.platform == "win32":
	import util_win
	if sys.getwindowsversion() < (6, ):
		# WCS only available under Vista and later
		mscms = None
	else:
		mscms = util_win._get_mscms_dll_handle()
	if mscms:
		mscms.WcsGetDefaultColorProfileSize.restype = ctypes.c_bool
		mscms.WcsGetDefaultColorProfile.restype = ctypes.c_bool
		mscms.WcsAssociateColorProfileWithDevice.restype = ctypes.c_bool
		mscms.WcsDisassociateColorProfileFromDevice.restype = ctypes.c_bool
elif sys.platform == "darwin":
	from util_mac import osascript


# Gamut volumes in cubic colorspace units (L*a*b*) as reported by Argyll's 
# iccgamut
GAMUT_VOLUME_SRGB = 833675.435316  # rel. col.
GAMUT_VOLUME_ADOBERGB = 1209986.014983  # rel. col.
GAMUT_VOLUME_SMPTE431_P3 = 1176953.485921  # rel. col.

# http://msdn.microsoft.com/en-us/library/dd371953%28v=vs.85%29.aspx
COLORPROFILESUBTYPE = {"NONE": 0x0000,
					   "RGB_WORKING_SPACE": 0x0001,
					   "PERCEPTUAL": 0x0002,
					   "ABSOLUTE_COLORIMETRIC": 0x0004,
					   "RELATIVE_COLORIMETRIC": 0x0008,
					   "SATURATION": 0x0010,
					   "CUSTOM_WORKING_SPACE": 0x0020}

# http://msdn.microsoft.com/en-us/library/dd371955%28v=vs.85%29.aspx (wrong)
# http://msdn.microsoft.com/en-us/library/windows/hardware/ff546018%28v=vs.85%29.aspx (ok)
COLORPROFILETYPE = {"ICC": 0,
					"DMP": 1,
					"CAMP": 2,
					"GMMP": 3}

WCS_PROFILE_MANAGEMENT_SCOPE = {"SYSTEM_WIDE": 0,
								"CURRENT_USER": 1}

debug = False

enc, fs_enc = get_encodings()

cmms = {"argl": "ArgyllCMS",
		"ADBE": "Adobe",
		"ACMS": "Agfa",
		"Agfa": "Agfa",
		"APPL": "Apple",
		"appl": "Apple",
		"CCMS": "ColorGear",
		"UCCM": "ColorGear Lite",
		"DL&C": "Digital Light & Color",
		"EFI ": "EFI",
		"FF  ": "Fuji Film",
		"HCMM": "Harlequin RIP",
		"LgoS": "LogoSync",
		"HDM ": "Heidelberg",
		"Lino": "Linotype",
		"lino": "Linotype",
		"lcms": "Little CMS",
		"KCMS": "Kodak",
		"MCML": "Konica Minolta",
		"MSFT": "Microsoft",
		"SIGN": "Mutoh",
		"RGMS": "DeviceLink",
		"SICC": "SampleICC",
		"32BT": "the imaging factory",
		"WTG ": "Ware to Go",
		"zc00": "Zoran"}

encodings = {
	"mac": {
		141: "africaans",
		36: "albanian",
		85: "amharic",
		12: "arabic",
		51: "armenian",
		68: "assamese",
		134: "aymara",
		49: "azerbaijani-cyrllic",
		50: "azerbaijani-arabic",
		129: "basque",
		67: "bengali",
		137: "dzongkha",
		142: "breton",
		44: "bulgarian",
		77: "burmese",
		46: "byelorussian",
		78: "khmer",
		130: "catalan",
		92: "chewa",
		33: "simpchinese",
		19: "tradchinese",
		18: "croatian",
		38: "czech",
		7: "danish",
		4: "dutch",
		0: "roman",
		94: "esperanto",
		27: "estonian",
		30: "faeroese",
		31: "farsi",
		13: "finnish",
		34: "flemish",
		1: "french",
		140: "galician",
		144: "scottishgaelic",
		145: "manxgaelic",
		52: "georgian",
		2: "german",
		14: "greek-monotonic",
		148: "greek-polytonic",
		133: "guarani",
		69: "gujarati",
		10: "hebrew",
		21: "hindi",
		26: "hungarian",
		15: "icelandic",
		81: "indonesian",
		143: "inuktitut",
		35: "irishgaelic",
		146: "irishgaelic-dotsabove",
		3: "italian",
		11: "japanese",
		138: "javaneserom",
		73: "kannada",
		61: "kashmiri",
		48: "kazakh",
		90: "kiryarwanda",
		54: "kirghiz",
		91: "rundi",
		23: "korean",
		60: "kurdish",
		79: "lao",
		131: "latin",
		28: "latvian",
		24: "lithuanian",
		43: "macedonian",
		93: "malagasy",
		83: "malayroman-latin",
		84: "malayroman-arabic",
		72: "malayalam",
		16: "maltese",
		66: "marathi",
		53: "moldavian",
		57: "mongolian",
		58: "mongolian-cyrillic",
		64: "nepali",
		9: "norwegian",
		71: "oriya",
		87: "oromo",
		59: "pashto",
		25: "polish",
		8: "portuguese",
		70: "punjabi",
		132: "quechua",
		37: "romanian",
		32: "russian",
		29: "sami",
		65: "sanskrit",
		42: "serbian",
		62: "sindhi",
		76: "sinhalese",
		39: "slovak",
		40: "slovenian",
		88: "somali",
		6: "spanish",
		139: "sundaneserom",
		89: "swahili",
		5: "swedish",
		82: "tagalog",
		55: "tajiki",
		74: "tamil",
		135: "tatar",
		75: "telugu",
		22: "thai",
		63: "tibetan",
		86: "tigrinya",
		147: "tongan",
		17: "turkish",
		56: "turkmen",
		136: "uighur",
		45: "ukrainian",
		20: "urdu",
		47: "uzbek",
		80: "vietnamese",
		128: "welsh",
		41: "yiddish"
	}
}

colorants = {
	0: {
		"description": "unknown",
		"channels": ()
		},
	1: {
		"description": "ITU-R BT.709",
		"channels": ((0.64, 0.33), (0.3, 0.6), (0.15, 0.06))
		},
	2: {
		"description": "SMPTE RP145-1994",
		"channels": ((0.63, 0.34), (0.31, 0.595), (0.155, 0.07))
		},
	3: {
		"description": "EBU Tech.3213-E",
		"channels": ((0.64, 0.33), (0.29, 0.6), (0.15, 0.06))
		},
	4: {
		"description": "P22",
		"channels": ((0.625, 0.34), (0.28, 0.605), (0.155, 0.07))
		}
}

geometry = {
	0: "unknown",
	1: "0/45 or 45/0",
	2: "0/d or d/0"
}

illuminants = {
	0: "unknown",
	1: "D50",
	2: "D65",
	3: "D93",
	4: "F2",
	5: "D55",
	6: "A",
	7: "E",
	8: "F8"
}

observers = {
	0: "unknown",
	1: "CIE 1931",
	2: "CIE 1964"
}

manufacturers = {"ADBE": "Adobe Systems Incorporated",
				 "APPL": "Apple Computer, Inc.",
				 "agfa": "Agfa Graphics N.V.",
				 "argl": "ArgyllCMS",
				 "bICC": "basICColor GmbH",
				 "DL&C": "Digital Light & Color",
				 "EPSO": "Seiko Epson Corporation",
				 "HDM ": "Heidelberger Druckmaschinen AG",
				 "HP  ": "Hewlett-Packard",
				 "KODA": "Kodak",
				 "lcms": "Little CMS",
				 "MONS": "Monaco Systems Inc.",
				 "MSFT": "Microsoft Corporation",
				 "qato": "QUATOGRAPHIC Technology GmbH",
				 "XRIT": "X-Rite"}

platform = {"APPL": "Apple",
			"MSFT": "Microsoft",
			"SGI ": "Silicon Graphics",
			"SUNW": "Sun Microsystems"}

profileclass = {"scnr": "Input device profile",
				"mntr": "Display device profile",
				"prtr": "Output device profile",
				"link": "DeviceLink profile",
				"spac": "Color space Conversion profile",
				"abst": "Abstract profile",
				"nmcl": "Named color profile"}

tags = {"A2B0": "Device to PCS: Intent 0",
		"A2B1": "Device to PCS: Intent 1",
		"A2B2": "Device to PCS: Intent 2",
		"B2A0": "PCS to device: Intent 0",
		"B2A1": "PCS to device: Intent 1",
		"B2A2": "PCS to device: Intent 2",
		"CIED": "Characterization measurement values",  # Non-standard
		"DevD": "Characterization device values",  # Non-standard
		"arts": "Absolute to media relative transform",  # Non-standard (Argyll)
		"bkpt": "Media black point",
		"bTRC": "Blue tone response curve",
		"bXYZ": "Blue matrix column",
		"chad": "Chromatic adaptation transform",
		"ciis": "Colorimetric intent image state",
		"clro": "Colorant order",
		"cprt": "Copyright",
		"desc": "Description",
		"dmnd": "Device manufacturer name",
		"dmdd": "Device model name",
		"gamt": "Out of gamut tag",
		"gTRC": "Green tone response curve",
		"gXYZ": "Green matrix column",
		"kTRC": "Gray tone response curve",
		"lumi": "Luminance",
		"meas": "Measurement type",
		"mmod": "Make and model",
		"ncl2": "Named colors",
		"rTRC": "Red tone response curve",
		"rXYZ": "Red matrix column",
		"targ": "Characterization target",
		"tech": "Technology",
		"vcgt": "Video card gamma table",
		"view": "Viewing conditions",
		"vued": "Viewing conditions description",
		"wtpt": "Media white point"}

tech = {"fscn": "Film scanner",
		"dcam": "Digital camera",
		"rscn": "Reflective scanner",
		"ijet": "Ink jet printer",
		"twax": "Thermal wax printer",
		"epho": "Electrophotographic printer",
		"esta": "Electrostatic printer",
		"dsub": "Dye sublimation printer",
		"rpho": "Photographic paper printer",
		"fprn": "Film writer",
		"vidm": "Video monitor",
		"vidc": "Video camera",
		"pjtv": "Projection television",
		"CRT ": "Cathode ray tube display",
		"PMD ": "Passive matrix display",
		"AMD ": "Active matrix display",
		"KPCD": "Photo CD",
		"imgs": "Photographic image setter",
		"grav": "Gravure",
		"offs": "Offset lithography",
		"silk": "Silkscreen",
		"flex": "Flexography",
		"mpfs": "Motion picture film scanner",
		"mpfr": "Motion picture film recorder",
		"dmpc": "Digital motion picture camera",
		"dcpj": "Digital cinema projector"}

ciis = {"scoe": "Scene colorimetry estimates",
		"sape": "Scene appearance estimates",
		"fpce": "Focal plane colorimetry estimates",
		"rhoc": "Reflection hardcopy original colorimetry",
		"rpoc": "Reflection print output colorimetry"}

			
def PCSLab_dec_to_uInt16(L, a, b):
	return [v * (655.35, 256, 256)[i] + (0, 32768, 32768)[i]
			for i, v in enumerate((L, a, b))]


def PCSLab_uInt16_to_dec(L_uInt16, a_uInt16, b_uInt16):
	return [(v - (0, 32768, 32768)[i]) / (65535.0, 32768.0, 32768.0)[i] *
			(100, 128, 128)[i]
			for i, v in enumerate((L_uInt16, a_uInt16, b_uInt16))]


def Property(func):
	return property(**func())


def create_RGB_A2B_XYZ(input_curves, clut):
	"""
	Create RGB device A2B from input curve XYZ values and cLUT
	
	Note that input curves and cLUT should already be adapted to D50.
	
	"""
	if len(input_curves) != 3:
		raise ValueError("Wrong number of input curves: %i" % len(input_curves))

	white_XYZ = clut[-1][-1]

	clutres = len(clut[0])

	itable = LUT16Type(None, "A2B0")
	itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	
	# Input curve interpolation
	# Normlly the input curves would either be linear (= 1:1 mapping to
	# cLUT) or the respective tone response curve.
	# We use a overall linear curve that is 'bent' in <clutres> intervals
	# to accomodate the non-linear TRC. Thus, we can get away with much
	# fewer cLUT grid points.
	
	# Use higher interpolation size than actual number of curve entries
	steps = 2 ** 15 + 1
	maxv = steps - 1.0
	
	fwd = []
	bwd = []
	for i, input_curve in enumerate(input_curves):
		if isinstance(input_curve, (tuple, list)):
			linear = [v / (len(input_curve) - 1.0)
					  for v in xrange(len(input_curve))]
			fwd.append(colormath.Interp(linear, input_curve, use_numpy=True))
			bwd.append(colormath.Interp(input_curve, linear, use_numpy=True))
		else:
			# Gamma
			fwd.append(lambda v, p=input_curve: colormath.specialpow(v, p))
			bwd.append(lambda v, p=input_curve: colormath.specialpow(v, 1.0 / p))
		itable.input.append([])
		itable.output.append([0, 65535])

	for i in xrange(3):
		maxi = bwd[i](white_XYZ[1])
		segment = 1.0 / (clutres - 1.0) * maxi
		iv = 0.0
		prevpow = 0.0
		nextpow = fwd[i](segment)
		xp = []
		for j in xrange(steps):
			v = (j / maxv) * maxi
			if v > iv + segment:
				iv += segment
				prevpow = nextpow
				nextpow = fwd[i](iv + segment)
			prevs = 1.0 - (v - iv) / segment
			nexts = (v - iv) / segment
			vv = (prevs * prevpow + nexts * nextpow)
			out = bwd[i](vv)
			xp.append(out)
		# Fill input curves from interpolated values
		interp = colormath.Interp(xp, range(steps), use_numpy=True)
		entries = 2049
		for j in xrange(entries):
			v = j / (entries - 1.0)
			itable.input[i].append(interp(v) / maxv * 65535)
	
	# Fill cLUT
	clut = list(clut)
	itable.clut = []
	step = 1.0 / (clutres - 1.0)
	for R in xrange(clutres):
		for G in xrange(clutres):
			row = list(clut.pop(0))
			itable.clut.append([])
			for B in xrange(clutres):
				X, Y, Z = row.pop(0)
				itable.clut[-1].append([max(v / white_XYZ[1] * 32768, 0)
										for v in (X, Y, Z)])
	
	return itable


def create_synthetic_clut_profile(rgb_space, description, XYZbp=None,
								  white_Y=1.0, clutres=9):
	"""
	Create a synthetic cLUT profile from a colorspace definition
	
	"""
	profile = ICCProfile()
	
	profile.tags.desc = TextDescriptionType("", "desc")
	profile.tags.desc.ASCII = description
	profile.tags.cprt = TextType("text\0\0\0\0Public domain\0", "cprt")
	
	profile.tags.wtpt = XYZType(profile=profile)
	(profile.tags.wtpt.X,
	 profile.tags.wtpt.Y,
	 profile.tags.wtpt.Z) = colormath.get_whitepoint(rgb_space[1])
	
	itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
	itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	
	otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
	Xr, Yr, Zr = colormath.adapt(*colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
								 whitepoint_source=rgb_space[1])
	Xg, Yg, Zg = colormath.adapt(*colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
								 whitepoint_source=rgb_space[1])
	Xb, Yb, Zb = colormath.adapt(*colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
								 whitepoint_source=rgb_space[1])
	m1 = colormath.Matrix3x3(((Xr, Xg, Xb),
							  (Yr, Yg, Yb),
							  (Zr, Zg, Zb))).inverted()
	scale = 1 + (32767 / 32768.0)
	m3 = colormath.Matrix3x3(((scale, 0, 0),
							  (0, scale, 0),
							  (0, 0, scale)))
	otable.matrix = m1 * m3
	
	# Input curve interpolation
	# Normlly the input curves would either be linear (= 1:1 mapping to
	# cLUT) or the respective tone response curve.
	# We use a overall linear curve that is 'bent' in <clutres> intervals
	# to accomodate the non-linear TRC. Thus, we can get away with much
	# fewer cLUT grid points.
	
	# Use higher interpolation size than actual number of curve entries
	steps = 2 ** 15 + 1
	maxv = steps - 1.0
	gamma = rgb_space[0]
	maxi = colormath.specialpow(white_Y, 1.0 / gamma)
	segment = 1.0 / (clutres - 1.0) * maxi
	iv = 0.0
	prevpow = 0.0
	nextpow = colormath.specialpow(segment, gamma)
	xp = []
	for j in xrange(steps):
		v = (j / maxv) * maxi
		if v > iv + segment:
			iv += segment
			prevpow = nextpow
			nextpow = colormath.specialpow(iv + segment, gamma)
		prevs = 1.0 - (v - iv) / segment
		nexts = (v - iv) / segment
		vv = (prevs * prevpow + nexts * nextpow)
		out = colormath.specialpow(vv, 1.0 / gamma)
		xp.append(out)
	interp = colormath.Interp(xp, range(steps), use_numpy=True)
	
	# Create input and output curves
	for i in xrange(3):
		itable.input.append([])
		itable.output.append([0, 65535])
		otable.input.append([])
		otable.output.append([0, 65535])
		for j in xrange(4096):
			otable.input[i].append(colormath.specialpow(j / 4095.0 * white_Y,
														1.0 / gamma) * 65535)
	
	# Fill input curves from interpolated values
	entries = 2049
	for j in xrange(entries):
		v = j / (entries - 1.0)
		for i in xrange(3):
			itable.input[i].append(interp(v) / maxv * 65535)
	
	# Create and fill cLUT
	itable.clut = []
	step = 1.0 / (clutres - 1.0)
	for R in xrange(clutres):
		for G in xrange(clutres):
			itable.clut.append([])
			for B in xrange(clutres):
				X, Y, Z = colormath.adapt(*colormath.RGB2XYZ(*[v * step * maxi
															   for v in (R, G, B)],
															 rgb_space=rgb_space),
										  whitepoint_source=rgb_space[1])
				X, Y, Z = colormath.blend_blackpoint(X, Y, Z, None, XYZbp)
				itable.clut[-1].append([max(v / white_Y * 32768, 0)
										for v in (X, Y, Z)])
	
	otable.clut = []
	for R in xrange(2):
		for G in xrange(2):
			otable.clut.append([])
			for B in xrange(2):
				otable.clut[-1].append([v * 65535 for v in (R , G, B)])
	
	return profile


def create_synthetic_smpte2084_clut_profile(rgb_space, description,
											black_cdm2=0, white_cdm2=400,
											master_black_cdm2=0,
											master_white_cdm2=10000,
											content_rgb_space="DCI P3",
											rolloff=True,
											clutres=33, mode="ICtCp",
											forward_xicclu=None,
											backward_xicclu=None,
											generate_B2A=False,
											worker=None,
											logfile=None):
	"""
	Create a synthetic cLUT profile with the SMPTE 2084 TRC from a colorspace
	definition
	
	mode:  The gamut mapping mode when rolling off. Valid values:
	       "ICtCp" (default), "XYZ", "HSV" (inaccurate),
	       "RGB" (not recommended, saturation loss)
	
	"""

	if not rolloff:
		raise NotImplementedError("rolloff needs to be True")

	return create_synthetic_hdr_clut_profile("PQ", rgb_space, description,
											 black_cdm2, white_cdm2,
											 master_black_cdm2,
											 master_white_cdm2,
											 1.2,  # Not used for PQ
											 5.0,  # Not used for PQ
											 1.0,  # Not used for PQ
											 content_rgb_space,
											 clutres, mode,
											 forward_xicclu,
											 backward_xicclu,
											 generate_B2A,
											 worker,
											 logfile)


def create_synthetic_hdr_clut_profile(hdr_format, rgb_space, description,
									  black_cdm2=0, white_cdm2=400,
									  master_black_cdm2=0,  # Not used for HLG
									  master_white_cdm2=10000,  # Not used for HLG
									  system_gamma=1.2,  # Not used for PQ
									  ambient_cdm2=5,  # Not used for PQ
									  maxsignal=1.0,  # Not used for PQ
									  content_rgb_space="DCI P3",
									  clutres=33,
									  mode="ICtCp",  # Not used for HLG
									  forward_xicclu=None,
									  backward_xicclu=None,
									  generate_B2A=False,
									  worker=None,
									  logfile=None):
	"""
	Create a synthetic HDR cLUT profile from a colorspace definition
	
	"""

	rgb_space = colormath.get_rgb_space(rgb_space)
	content_rgb_space = colormath.get_rgb_space(content_rgb_space)

	if hdr_format == "PQ":
		bt2390 = colormath.BT2390(black_cdm2, white_cdm2, master_black_cdm2,
								  master_white_cdm2)

		maxv = white_cdm2 / 10000.0
		eotf = lambda v: colormath.specialpow(v, -2084)
		oetf = eotf_inverse = lambda v: colormath.specialpow(v, 1.0 / -2084)
		eetf = bt2390.apply
	elif hdr_format == "HLG":
		# Note: Unlike the PQ black level lift, we apply HLG black offset as
		# separate final step, not as part of the HLG EOTF
		hlg = colormath.HLG(0, white_cdm2, system_gamma, ambient_cdm2, rgb_space)

		if maxsignal < 1:
			# Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
			while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
				hlg.white_cdm2 += 1

		lscale = 1.0 / hlg.oetf(1.0, True)
		hlg.white_cdm2 *= lscale
		if lscale < 1 and logfile:
			logfile.write("Nominal peak luminance after scaling = %.2f\n" %
						  hlg.white_cdm2)

		Ymax = hlg.eotf(maxsignal)

		maxv = 1.0
		eotf = hlg.eotf
		eotf_inverse = lambda v: hlg.eotf(v, True)
		oetf = hlg.oetf
		eetf = lambda v: v
	else:
		raise NotImplementedError("Unknown HDR format %r" % hdr_format)

	profile = ICCProfile()
	
	profile.tags.desc = TextDescriptionType("", "desc")
	profile.tags.desc.ASCII = description
	profile.tags.cprt = TextType("text\0\0\0\0Public domain\0", "cprt")
	
	profile.tags.wtpt = XYZType(profile=profile)
	(profile.tags.wtpt.X,
	 profile.tags.wtpt.Y,
	 profile.tags.wtpt.Z) = colormath.get_whitepoint(rgb_space[1])
	
	itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
	itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	# HDR RGB
	debugtable0 = profile.tags.DBG0 = LUT16Type(None, "DBG0", profile)
	debugtable0.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	# Display RGB
	debugtable1 = profile.tags.DBG1 = LUT16Type(None, "DBG1", profile)
	debugtable1.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	# Display XYZ
	debugtable2 = profile.tags.DBG2 = LUT16Type(None, "DBG2", profile)
	debugtable2.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
	
	if generate_B2A:
		otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
		Xr, Yr, Zr = colormath.adapt(*colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
									 whitepoint_source=rgb_space[1])
		Xg, Yg, Zg = colormath.adapt(*colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
									 whitepoint_source=rgb_space[1])
		Xb, Yb, Zb = colormath.adapt(*colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
									 whitepoint_source=rgb_space[1])
		m1 = colormath.Matrix3x3(((Xr, Xg, Xb),
								  (Yr, Yg, Yb),
								  (Zr, Zg, Zb)))
		m2 = m1.inverted()
		scale = 1 + (32767 / 32768.0)
		m3 = colormath.Matrix3x3(((scale, 0, 0),
								  (0, scale, 0),
								  (0, 0, scale)))
		otable.matrix = m2 * m3
	
	# Input curve interpolation
	# Normlly the input curves would either be linear (= 1:1 mapping to
	# cLUT) or the respective tone response curve.
	# We use a overall linear curve that is 'bent' in <clutres> intervals
	# to accomodate the non-linear TRC. Thus, we can get away with much
	# fewer cLUT grid points.
	
	# Use higher interpolation size than actual number of curve entries
	steps = 2 ** 15 + 1
	maxstep = steps - 1.0
	segment = 1.0 / (clutres - 1.0)
	iv = 0.0
	prevpow = eotf(eetf(0))
	nextpow = eotf(eetf(segment))
	xp = []
	if generate_B2A:
		oxp = []
	for j in xrange(steps):
		v = (j / maxstep)
		if v > iv + segment:
			iv += segment
			prevpow = nextpow
			nextpow = eotf(eetf(iv + segment))
		prevs = 1.0 - (v - iv) / segment
		nexts = (v - iv) / segment
		vv = (prevs * prevpow + nexts * nextpow)
		out = eotf_inverse(vv)
		xp.append(out)
		if generate_B2A:
			oxp.append(eotf(eetf(v)) / maxv)
	interp = colormath.Interp(xp, range(steps), use_numpy=True)
	if generate_B2A:
		ointerp = colormath.Interp(oxp, range(steps), use_numpy=True)

	# Save interpolation input values for diagnostic purposes
	profile.tags.kTRC = CurveType()
	interp_inverse = colormath.Interp(range(steps), xp, use_numpy=True)
	profile.tags.kTRC[:] = [interp_inverse(colormath.convert_range(v, 0, 2048,
																   0, maxstep)) *
							65535
							for v in xrange(2049)]
	
	# Create input and output curves
	for i in xrange(3):
		itable.input.append([])
		itable.output.append([0, 65535])
		debugtable0.input.append([0, 65535])
		debugtable0.output.append([0, 65535])
		debugtable1.input.append([0, 65535])
		debugtable1.output.append([0, 65535])
		debugtable2.input.append([0, 65535])
		debugtable2.output.append([0, 65535])
		if generate_B2A:
			otable.input.append([])
			otable.output.append([0, 65535])
	
	# Generate device-to-PCS shaper curves from interpolated values
	if logfile:
		logfile.write("Generating device-to-PCS shaper curves...\n")
	entries = 2049
	prevperc = 0
	if generate_B2A:
		endperc = 1
	else:
		endperc = 2
	k = None
	for j in xrange(entries):
		if worker and worker.thread_abort:
			if forward_xicclu:
				forward_xicclu.exit()
			if backward_xicclu:
				backward_xicclu.exit()
			raise Exception("aborted")
		n = j / (entries - 1.0)
		v = interp(eetf(n)) / maxstep
		if hdr_format == "PQ":
			threshold = 1.0 - segment * math.ceil((1.0 - bt2390.mmaxi) *
												  (clutres - 1.0) + 1)
			check = n >= threshold
			start = n
		elif hdr_format == "HLG":
			check = maxsignal < 1 and n >= maxsignal
			start = v
		if check:
			# Linear interpolate shaper for last n cLUT steps to prevent
			# clipping in shaper
			if k is None:
				k = j
				ov = start
			v = min(ov + (1.0 - ov) * ((j - k) / (entries - k - 1.0)), 1.0)
		for i in xrange(3):
			itable.input[i].append(v * 65535)
		perc = math.floor(n * endperc)
		if logfile and perc > prevperc:
			logfile.write("\r%i%%" % perc)
			prevperc = perc
	startperc = perc

	if generate_B2A:
		# Generate PCS-to-device shaper curves from interpolated values
		if logfile:
			logfile.write("\rGenerating PCS-to-device shaper curves...\n")
			logfile.write("\r%i%%" % perc)
		for j in xrange(4096):
			if worker and worker.thread_abort:
				if forward_xicclu:
					forward_xicclu.exit()
				if backward_xicclu:
					backward_xicclu.exit()
				raise Exception("aborted")
			n = j / 4095.0
			v = ointerp(n) / maxstep * 65535
			for i in xrange(3):
				otable.input[i].append(v)
			perc = startperc + math.floor(n * 20)
			if logfile and perc > prevperc:
				logfile.write("\r%i%%" % perc)
				prevperc = perc
		startperc = perc

	# Scene RGB -> HDR tone mapping -> HDR XYZ -> backward lookup -> display RGB
	if logfile:
		logfile.write("\rApplying HDR tone mapping...\n")
		logfile.write("\r%i%%" % perc)
	itable.clut = []
	debugtable0.clut = []
	debugtable1.clut = []
	debugtable2.clut = []
	clutmax = clutres - 1.0
	step = 1.0 / clutmax
	count = 0
	# Lpt is the preferred mode for chroma blending. Some preliminary visual
	# comparison has shown it does overall the best job preserving hue and
	# saturation (blue hues superior to IPT). DIN99d is the second best,
	# but vibrant red turns slightly orange when desaturated (DIN99d has best
	# blue saturation preservation though). ICtCp should NOT be used as it has
	# a tendency to blow out highlights (maybe this is not due to ICtCp itself
	# and more the way it is used here, because it works just fine for the
	# initial roll-off saturation adjustment where it is the preferred mode).
	blendmode = "Lpt"
	IPT_white_XYZ = colormath.get_cat_matrix("IPT").inverted() * (1, 1, 1)
	Cmode = ("all", "primaries_secondaries")[0]
	RGB_in = []
	HDR_ICtCp = []
	HDR_RGB = []
	HDR_XYZ = []
	HDR_min_I = []
	for R in xrange(clutres):
		for G in xrange(clutres):
			for B in xrange(clutres):
				if worker and worker.thread_abort:
					if forward_xicclu:
						forward_xicclu.exit()
					if backward_xicclu:
						backward_xicclu.exit()
					raise Exception("aborted")
				RGB = [v * step for v in (R, G, B)]
				RGB_in.append(RGB)
				if debug and R == G == B:
					safe_print("RGB %5.3f %5.3f %5.3f" % tuple(RGB), end=" ")
				if hdr_format == "HLG":
					X, Y, Z = hlg.RGB2XYZ(*RGB)
					if Y:
						Y1 = Y
						I1 = hlg.eotf(Y, True)
						I2 = min(I1, maxsignal)
						Y2 = hlg.eotf(I2)
						Y3 = Y2 / Ymax
						X, Y, Z = (v / Y * Y3 if Y else v for v in (X, Y, Z))
						if R == G == B and logfile and debug:
							logfile.write("\rE %.4f -> E' %.4f -> roll-off -> %.4f -> E %.4f -> scale (%i%%) -> %.4f\n" % (Y1, I1, I2, Y2, Y3 / Y2 * 100, Y3))
				elif mode == "XYZ":
					X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space,
												eotf=eotf)
					if Y:
						I1 = colormath.specialpow(Y, 1.0 / -2084)
						I2 = eetf(I1)
						Y2 = colormath.specialpow(I2, -2084)
						X, Y, Z = (v / Y * Y2 for v in (X, Y, Z))
					else:
						I1 = I2 = 0
				elif mode == "HSV":
					HSV = list(colormath.RGB2HSV(*RGB))
					I1 = HSV[2]
					HSV[2] = eetf(I1)
					I2 = HSV[2]
				elif mode == "ICtCp":
					LinearRGB = [eotf(v) for v in RGB]
					I1, Ct1, Cp1 = colormath.LinearRGB2ICtCp(*LinearRGB,
															 oetf=eotf_inverse)
					if debug and R == G == B:
						safe_print("-> ICtCp % 5.3f % 5.3f % 5.3f" %
								   (I1, Ct1, Cp1,), end=" ")
					I2 = eetf(I1)
				elif mode == "RGB":
					I1 = colormath.RGB2HSV(*RGB)[2]
					for i, v in enumerate(RGB):
						RGB[i] = eetf(v)
					I2 = colormath.RGB2HSV(*RGB)[2]
				if hdr_format == "PQ" and I1 and I2:
					if forward_xicclu and backward_xicclu:
						# Only desaturate light colors (dark colors will be
						# desaturated according to display max chroma)
						dsat = 1.0
					else:
						# Desaturate dark and light colors
						dsat = I1 / I2
					min_I = min(dsat, I2 / I1)
				else:
					min_I = 1
				if hdr_format == "HLG":
					pass
				elif mode == "XYZ":
					X, Y, Z = colormath.XYZsaturation(X, Y, Z,
													  min_I,
													  rgb_space[1])[0]
					RGB = colormath.XYZ2RGB(X, Y, Z, rgb_space,
											oetf=eotf_inverse)
				elif mode == "HSV":
					if debug and R == G == B:
						safe_print("* %5.3f" % min_I, "->", end=" ")
					HSV[1] *= min_I
					RGB = colormath.HSV2RGB(*HSV)
				elif mode == "ICtCp":
					if debug and R == G == B:
						safe_print("* %5.3f" % min_I, "->", end=" ")
					Ct2, Cp2 = (min_I * v for v in (Ct1, Cp1))
					if debug and R == G == B:
						safe_print("% 5.3f % 5.3f % 5.3f" % (I2, Ct2, Cp2),
								   "->", end=" ")
					LinearRGB = colormath.ICtCp2LinearRGB(I2, Ct2, Cp2, eotf=eotf)
					##if min(LinearRGB) < 0 or max(LinearRGB) > 1:
						##print 'WARNING:', LinearRGB
						##LinearRGB = [max(min(v, 1), 0) for v in LinearRGB]
					RGB = [eotf_inverse(v) for v in LinearRGB]
					I, Ct, Cp = I2, Ct2, Cp2
					X, Y, Z = colormath.ICtCp2XYZ(I2, Ct2, Cp2, rgb_space,
												  eotf=eotf)
				if debug and R == G == B:
					safe_print("RGB %5.3f %5.3f %5.3f" % tuple(RGB))
				if hdr_format != "PQ" or mode != "ICtCp":
					I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z, oetf=eotf_inverse)
				HDR_ICtCp.append((I, Ct, Cp))
				HDR_RGB.append(RGB)
				if mode not in ("XYZ", "ICtCp"):
					X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space,
												eotf=eotf)
				X, Y, Z = (v / maxv for v in (X, Y, Z))
				# Clip to XYZ encoding range of 0..65535 by going through
				# RGB, clamping to 1, and back to XYZ. Does a pretty good job
				# at preserving hue.
				XR, XG, XB = colormath.XYZ2RGB(X, Y, Z, rgb_space=rgb_space,
											   oetf=eotf_inverse)
				X, Y, Z = colormath.RGB2XYZ(XR, XG, XB, rgb_space=rgb_space,
											eotf=eotf)
				# Adapt to D50
				X, Y, Z = colormath.adapt(X, Y, Z,
										  whitepoint_source=rgb_space[1])
				if max(X, Y, Z) * 32768 > 65535:
					# This should not happen
					safe_print("#%i" % row, X, Y, Z)
				HDR_XYZ.append((X, Y, Z))
				HDR_min_I.append(min_I)
				count += 1
				perc = startperc + math.floor(count / clutres ** 3.0 *
											  (100 - startperc))
				if logfile and perc > prevperc:
					logfile.write("\r%i%%" % perc)
					prevperc = perc
	prevperc = startperc = perc = 0

	if forward_xicclu and backward_xicclu and logfile:
		logfile.write("\rDoing backward lookup...\n")
		logfile.write("\r%i%%" % perc)
	count = 0
	for i, (X, Y, Z) in enumerate(HDR_XYZ):
		if worker and worker.thread_abort:
			if forward_xicclu:
				forward_xicclu.exit()
			if backward_xicclu:
				backward_xicclu.exit()
			raise Exception("aborted")
		if (forward_xicclu and backward_xicclu and 
			Cmode != "primaries_secondaries"):
			# HDR XYZ -> backward lookup -> display RGB
			backward_xicclu((X, Y, Z))
			count += 1
			perc = startperc + math.floor(count / clutres ** 3.0 *
										  (100 - startperc))
			if (logfile and perc > prevperc and
				backward_xicclu.__class__.__name__ == "Xicclu"):
				logfile.write("\r%i%%" % perc)
				prevperc = perc
	prevperc = startperc = perc = 0

	Cdiff = []
	Cmax = {}
	Cdmax = {}
	if forward_xicclu and backward_xicclu:
		# Display RGB -> backward lookup -> display XYZ
		backward_xicclu.close()
		display_RGB = backward_xicclu.get()
		if logfile:
			logfile.write("\rDoing forward lookup...\n")
			logfile.write("\r%i%%" % perc)

		# Smooth
		row = 0
		for col_0 in xrange(clutres):
			for col_1 in xrange(clutres):
				debugtable1.clut.append([])
				for col_2 in xrange(clutres):
					RGBdisp = display_RGB[row]
					debugtable1.clut[-1].append([min(max(v * 65535, 0), 65535)
												for v in RGBdisp])
					row += 1
		debugtable1.smooth()
		display_RGB = []
		for block in debugtable1.clut:
			for row in block:
				display_RGB.append([v / 65535.0 for v in row])

		for i, (R, G, B) in enumerate(display_RGB):
			if worker and worker.thread_abort:
				if forward_xicclu:
					forward_xicclu.exit()
				if backward_xicclu:
					backward_xicclu.exit()
				raise Exception("aborted")
			forward_xicclu((R, G, B))
			perc = startperc + math.floor((i + 1) / clutres ** 3.0 *
										  (100 - startperc))
			if (logfile and perc > prevperc and
				forward_xicclu.__class__.__name__ == "Xicclu"):
				logfile.write("\r%i%%" % perc)
				prevperc = perc
		prevperc = startperc = perc = 0

		if Cmode == "primaries_secondaries":
			# Compare to chroma of content primaries/secondaries to determine
			# general chroma compression factor
			forward_xicclu((0, 0, 1))
			forward_xicclu((0, 1, 0))
			forward_xicclu((1, 0, 0))
			forward_xicclu((0, 1, 1))
			forward_xicclu((1, 0, 1))
			forward_xicclu((1, 1, 0))
		forward_xicclu.close()
		display_XYZ = forward_xicclu.get()
		if Cmode == "primaries_secondaries":
			for i in xrange(6):
				if i == 0:
					# Blue
					j = clutres - 1
				elif i == 1:
					# Green
					j = clutres ** 2 - clutres
				elif i == 2:
					# Red
					j = clutres ** 3 - clutres ** 2
				elif i == 3:
					# Cyan
					j = clutres ** 2 - 1
				elif i == 4:
					# Magenta
					j = clutres ** 3 - clutres ** 2 + clutres - 1
				elif i == 5:
					# Yellow
					j = clutres ** 3 - clutres
				R, G, B = RGB_in[j]
				XYZsrc = HDR_XYZ[j]
				XYZdisp = display_XYZ[-(6 - i)]
				XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space,
										 eotf=eotf)
				XYZc = colormath.adapt(*XYZc,
										whitepoint_source=content_rgb_space[1])
				L, C, H = colormath.XYZ2DIN99dLCH(*(v * 100
													for v in XYZc))
				Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))
				Cdmaxk = tuple(map(round, (Ld, Hd)))
				if C > Cmax.get(Cdmaxk, -1):
					Cmax[Cdmaxk] = C
				Cdiff.append(min(Cd / C, 1.0))
				if Cd > Cdmax.get(Cdmaxk, -1):
					Cdmax[Cdmaxk] = Cd
				safe_print("RGB in %5.2f %5.2f %5.2f" % (R, G, B))
				safe_print("Content BT2020 XYZ (DIN99d) %5.2f %5.2f %5.2f" %
						   tuple(v * 100 for v in XYZc))
				safe_print("Content BT2020 LCH (DIN99d) %5.2f %5.2f %5.2f" %
						   (L, C, H))
				safe_print("Display XYZ %5.2f %5.2f %5.2f" %
						   tuple(v * 100 for v in XYZdisp))
				safe_print("Display LCH (DIN99d) %5.2f %5.2f %5.2f" %
						   (Ld, Cd, Hd))
				if logfile:
					logfile.write("\r%s chroma compression factor: %6.4f\n" %
								  ({0: "B", 1: "G", 2: "R",
									3: "C", 4: "M", 5: "Y"}[i], Cdiff[-1]))
			# Tweak so that it gives roughly 0.91 for a Rec. 709 target
			general_compression_factor = (sum(Cdiff) / len(Cdiff)) * 0.99
	else:
		display_RGB = False
		display_XYZ = False

	display_LCH = []
	if Cmode != "primaries_secondaries" and display_XYZ:
		# Determine compression factor by comparing display to content
		# colorspace in BT.2020
		if logfile:
			logfile.write("\rDetermining chroma compression factors...\n")
			logfile.write("\r%i%%" % perc)
		for i, (R, G, B) in enumerate(HDR_RGB):
			if worker and worker.thread_abort:
				if forward_xicclu:
					forward_xicclu.exit()
				if backward_xicclu:
					backward_xicclu.exit()
				raise Exception("aborted")
			XYZsrc = HDR_XYZ[i]
			if display_XYZ:
				XYZdisp = display_XYZ[i]
				### Adjust luminance from destination to source
				##Ydisp = XYZdisp[1]
				##if Ydisp:
					##XYZdisp = [v / Ydisp * XYZsrc[1] for v in XYZdisp]
			else:
				XYZdisp = XYZsrc
			X, Y, Z = (v * maxv for v in XYZsrc)
			X, Y, Z = colormath.adapt(X, Y, Z,
									  whitepoint_destination=content_rgb_space[1])
			R, G, B = colormath.XYZ2RGB(X, Y, Z, content_rgb_space,
										oetf=eotf_inverse)
			XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space, eotf=eotf)
			XYZc = colormath.adapt(*XYZc,
									whitepoint_source=content_rgb_space[1],
									whitepoint_destination=rgb_space[1])
			RGBc_r2020 = colormath.XYZ2RGB(*XYZc, rgb_space=rgb_space,
										   oetf=eotf_inverse)
			XYZc_r2020 = colormath.RGB2XYZ(*RGBc_r2020, rgb_space=rgb_space,
										   eotf=eotf)
			if blendmode == "ICtCp":
				I, Ct, Cp = colormath.XYZ2ICtCp(*XYZc_r2020,
												rgb_space=rgb_space,
												oetf=eotf_inverse)
				L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)
				XYZdispa = colormath.adapt(*XYZdisp,
										   whitepoint_destination=rgb_space[1])
				Id, Ctd, Cpd = colormath.XYZ2ICtCp(*(v * maxv for v in XYZdispa),
												   rgb_space=rgb_space,
												   oetf=eotf_inverse)
				Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Cpd * 100, Ctd * 100)
			elif blendmode == "IPT":
				XYZc_r2020 = colormath.adapt(*XYZc_r2020,
											 whitepoint_source=rgb_space[1],
											 whitepoint_destination=IPT_white_XYZ)
				I, CP, CT = colormath.XYZ2IPT(*XYZc_r2020)
				L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)
				XYZdispa = colormath.adapt(*XYZdisp,
										   whitepoint_destination=IPT_white_XYZ)
				Id, Pd, Td = colormath.XYZ2IPT(*XYZdispa)
				Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Pd * 100, Td * 100)
			elif blendmode == "Lpt":
				XYZc_r2020 = colormath.adapt(*XYZc_r2020,
											 whitepoint_source=rgb_space[1])
				L, p, t = colormath.XYZ2Lpt(*(v / maxv * 100
											  for v in XYZc_r2020))
				L, C, H = colormath.Lab2LCHab(L, p, t)
				Ld, pd, td = colormath.XYZ2Lpt(*(v * 100 for v in XYZdisp))
				Ld, Cd, Hd = colormath.Lab2LCHab(Ld, pd, td)
			elif blendmode == "XYZ":
				XYZc_r2020 = colormath.adapt(*XYZc_r2020,
											 whitepoint_source=rgb_space[1])
				wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
				x, y, Y = colormath.XYZ2xyY(*XYZc_r2020)
				x -= wx
				y -= wy
				L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
				x, y, Y = colormath.XYZ2xyY(*XYZdisp)
				x -= wx
				y -= wy
				Ld, Cd, Hd = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
			else:
				# DIN99d
				XYZc_r202099 = colormath.adapt(*XYZc_r2020,
											   whitepoint_source=rgb_space[1])
				L, C, H = colormath.XYZ2DIN99dLCH(*(v / maxv * 100
													for v in XYZc_r202099))
				Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))
			Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))
			if C > Cmax.get(Cdmaxk, -1):
				Cmax[Cdmaxk] = C
			if C:
				##print '%6.3f %6.3f' % (Cd, C)
				Cdiff.append(min(Cd / C, 1.0))
				##if Cdiff[-1] < 0.0001:
					##raise RuntimeError("#%i RGB % 5.3f % 5.3f % 5.3f Cdiff %5.3f" % (i, R, G, B, Cdiff[-1]))
			else:
				Cdiff.append(1.0)
			display_LCH.append((Ld, Cd, Hd))
			if Cd > Cdmax.get(Cdmaxk, -1):
				Cdmax[Cdmaxk] = Cd
			if debug:
				safe_print("RGB in %5.2f %5.2f %5.2f" % tuple(RGB_in[i]))
				safe_print("RGB out %5.2f %5.2f %5.2f" % (R, G, B))
				safe_print("Content BT2020 XYZ %5.2f %5.2f %5.2f" %
						   tuple(v / maxv * 100 for v in XYZc_r2020))
				safe_print("Content BT2020 LCH %5.2f %5.2f %5.2f" % (L, C, H))
				safe_print("Display XYZ %5.2f %5.2f %5.2f" %
						   tuple(v * 100 for v in XYZdisp))
				safe_print("Display LCH %5.2f %5.2f %5.2f" % (Ld, Cd, Hd))
			perc = startperc + math.floor(i / clutres ** 3.0 *
										  (80 - startperc))
			if logfile and perc > prevperc:
				logfile.write("\r%i%%" % perc)
				prevperc = perc
		startperc = perc

		general_compression_factor = (sum(Cdiff) / len(Cdiff))

	if display_XYZ:
		Cmaxv = max(Cmax.values())
		Cdmaxv = max(Cdmax.values())

	if logfile and display_LCH and Cmode == "primaries_secondaries":
		logfile.write("\rChroma compression factor: %6.4f\n" %
					  general_compression_factor)

	# Chroma compress to display XYZ
	if logfile:
		if display_XYZ:
			logfile.write("\rApplying chroma compression and filling cLUT...\n")
		else:
			logfile.write("\rFilling cLUT...\n")
		logfile.write("\r%i%%" % perc)
	row = 0
	oog_count = 0
	##if forward_xicclu:
		##forward_xicclu.spawn()
	##if backward_xicclu:
		##backward_xicclu.spawn()
	for col_0 in xrange(clutres):
		for col_1 in xrange(clutres):
			itable.clut.append([])
			debugtable0.clut.append([])
			if not display_RGB:
				debugtable1.clut.append([])
			debugtable2.clut.append([])
			for col_2 in xrange(clutres):
				if worker and worker.thread_abort:
					if forward_xicclu:
						forward_xicclu.exit()
					if backward_xicclu:
						backward_xicclu.exit()
					raise Exception("aborted")
				R, G, B = HDR_RGB[row]
				I, Ct, Cp = HDR_ICtCp[row]
				X, Y, Z = HDR_XYZ[row]
				min_I = HDR_min_I[row]
				if not (col_0 == col_1 == col_2) and display_XYZ:
					# Desaturate based on compression factor
					if display_LCH:
						blend = 1
					else:
						# Blending threshold: Don't desaturate dark colors
						# (< 26 cd/m2). Preserves more "pop"
						thresh_I = .381
						blend = min_I * min(max((I - thresh_I) / (.5081 - thresh_I), 0), 1)
					if blend:
						if blendmode == "XYZ":
							wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
							x, y, Y = colormath.XYZ2xyY(X, Y, Z)
							x -= wx
							y -= wy
							L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
						elif blendmode == "ICtCp":
							L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)
						elif blendmode == "DIN99d":
							XYZ = X, Y, Z
							L, C, H = colormath.XYZ2DIN99dLCH(*[v * 100
																for v in XYZ])
						elif blendmode == "IPT":
							XYZ = colormath.adapt(X, Y, Z,
												  whitepoint_destination=IPT_white_XYZ)
							I, CP, CT = colormath.XYZ2IPT(*XYZ)
							L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)
						elif blendmode == "Lpt":
							XYZ = X, Y, Z
							L, p, t = colormath.XYZ2Lpt(*[v * 100 for v in XYZ])
							L, C, H = colormath.Lab2LCHab(L, p, t)
						if blendmode:
							if display_LCH:
								Ld, Cd, Hd = display_LCH[row]
								##Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))
								### Lookup HDR max chroma for given display 
								### luminance and hue
								##HCmax = Cmax[Cdmaxk]
								##if C and HCmax:
									### Lookup display max chroma for given display 
									### luminance and hue
									##HCdmax = Cdmax[Cdmaxk]
									### Display max chroma in 0..1 range
									##maxCc = min(HCdmax / HCmax, 1.0)
									##KSCc = 1.5 * maxCc - 0.5
									### HDR chroma in 0..1 range
									##Cc1 = min(C / HCmax, 1.0)
									##if Cc1 >= KSCc <= 1 and maxCc > KSCc >= 0:
										### Roll-off chroma
										##Cc2 = bt2390.apply(Cc1, KSCc,
														   ##maxCc, 1.0, 0,
														   ##normalize=False)
										##C = HCmax * Cc2
									##else:
										### Use display chroma as-is (clip)
										##if debug:
											##safe_print("CLUT grid point %i %i %i: "
													   ##"C %6.4f Cd %6.4f HCmax %6.4f maxCc "
													   ##"%6.4f KSCc %6.4f Cc1 %6.4f" %
													   ##(col_0, col_1, col_2, C, Cd,
														##HCmax, maxCc, KSCc, Cc1))
										##C = Cd
								if C:
									C *= min(Cd / C, 1.0)
								if L and blendmode == "ICtCp":
									C *= min(Ld / L, 1.0)
									L *= min(Ld / L, 1.0) ** min(Ld / L, L / Ld)
							else:
								Cc = general_compression_factor
								Cc **= (C / Cmaxv)
								C = C * (1 - blend) + (C * Cc) * blend
						if blendmode == "ICtCp":
							I, Cp, Ct = [v / 100.0 for v in
										 colormath.LCHab2Lab(L, C, H)]
							XYZ = colormath.ICtCp2XYZ(I, Ct, Cp,
													  rgb_space=rgb_space,
													  eotf=eotf)
							X, Y, Z = (v / maxv for v in XYZ)
							# Adapt to D50
							X, Y, Z = colormath.adapt(X, Y, Z,
													  whitepoint_source=rgb_space[1])
						elif blendmode == "DIN99d":
							L, a, b = colormath.DIN99dLCH2Lab(L, C, H)
							X, Y, Z = colormath.Lab2XYZ(L, a, b)
						elif blendmode == "IPT":
							I, CP, CT = [v / 100.0 for v in
										 colormath.LCHab2Lab(L, C, H)]
							X, Y, Z = colormath.IPT2XYZ(I, CP, CT)
							# Adapt to D50
							X, Y, Z = colormath.adapt(X, Y, Z,
													  whitepoint_source=IPT_white_XYZ)
						elif blendmode == "Lpt":
							L, p, t = colormath.LCHab2Lab(L, C, H)
							X, Y, Z = colormath.Lpt2XYZ(L, p, t)
						elif blendmode == "XYZ":
							Y, x, y = [v / 100.0 for v in
									   colormath.LCHab2Lab(L, C, H)]
							x += wx
							y += wy
							X, Y, Z = colormath.xyY2XYZ(x, y, Y)
					else:
						safe_print("CLUT grid point %i %i %i: blend = 0" %
								   (col_0, col_1, col_2))
				##if backward_xicclu and forward_xicclu:
					##backward_xicclu((X, Y, Z))
				##else:
					##HDR_XYZ[row] = (X, Y, Z)
				##row += 1
				##perc = startperc + math.floor(row / clutres ** 3.0 *
											  ##(90 - startperc))
				##if logfile and perc > prevperc:
					##logfile.write("\r%i%%" % perc)
					##prevperc = perc
	##startperc = perc

	##if backward_xicclu and forward_xicclu:
		### Get XYZ clipped to display RGB
		##backward_xicclu.exit()
		##for R, G, B in backward_xicclu.get():
			##forward_xicclu((R, G, B))
		##forward_xicclu.exit()
		##display_XYZ = forward_xicclu.get()
	##else:
		##display_XYZ = HDR_XYZ
	##row = 0
	##for a in xrange(clutres):
		##for b in xrange(clutres):
			##itable.clut.append([])
			##debugtable0.clut.append([])
			##for c in xrange(clutres):
				##if worker and worker.thread_abort:
					##if forward_xicclu:
						##forward_xicclu.exit()
					##if backward_xicclu:
						##backward_xicclu.exit()
					##raise Exception("aborted")
				##X, Y, Z = display_XYZ[row]
				itable.clut[-1].append([min(max(v * 32768, 0), 65535)
										for v in (X, Y, Z)])
				debugtable0.clut[-1].append([min(max(v * 65535, 0), 65535)
											for v in (R, G, B)])
				if not display_RGB:
					debugtable1.clut[-1].append([0, 0, 0])
				if display_XYZ:
					XYZdisp = display_XYZ[row]
				else:
					XYZdisp = [0, 0, 0]
				debugtable2.clut[-1].append([min(max(v * 65535, 0), 65535)
											for v in XYZdisp])
				row += 1
				perc = startperc + math.floor(row / clutres ** 3.0 *
											  (100 - startperc))
				if logfile and perc > prevperc:
					logfile.write("\r%i%%" % perc)
					prevperc = perc
	startperc = perc

	if debug:
		safe_print("Num OOG:", oog_count)
		
	if generate_B2A:
		##if logfile:
			##logfile.write("\rGenerating PCS-to-device table...\n")
			##logfile.write("\r%i%%" % perc)
		
		otable.clut = []
		##rgb_space_out = list(rgb_space)
		##rgb_space_out[0] = [[v / 65535.0 for v in otable.input[0]]] * 3
		##count = 0
		##for R in xrange(clutres):
			##for G in xrange(clutres):
				##otable.clut.append([])
				##for B in xrange(clutres):
					##RGB = [v * step for v in (R, G, B)]
					##R_G_B_ = [ointerp(v) / maxstep for v in RGB]
					##X, Y, Z = m1 * R_G_B_
					##X, Y, Z = colormath.adapt(X, Y, Z, "D50", rgb_space[1])
					##RGB = colormath.XYZ2RGB(X, Y, Z, rgb_space_out)
					##otable.clut[-1].append([v * 65535 for v in RGB])
					##count += 1
					##perc = 35 + round(count / clutres ** 3.0 * 65)
					##if logfile and perc > prevperc:
						##logfile.write("\r%i%%" % perc)
						##prevperc = perc
		for R in xrange(2):
			for G in xrange(2):
				otable.clut.append([])
				for B in xrange(2):
					otable.clut[-1].append([v * 65535 for v in (R , G, B)])

	if logfile:
		logfile.write("\n")

	if forward_xicclu:
		forward_xicclu.exit()
	if backward_xicclu:
		backward_xicclu.exit()

	if hdr_format == "HLG" and black_cdm2:
		# Apply black offset
		XYZbp = colormath.get_whitepoint(scale=black_cdm2 / float(white_cdm2))
		if logfile:
			logfile.write("Applying black offset...\n")
		profile.tags.A2B0.apply_black_offset(XYZbp, logfile=logfile,
											 thread_abort=worker and
														  worker.thread_abort)
	
	return profile


def create_synthetic_hlg_clut_profile(rgb_space, description,
											black_cdm2=0, white_cdm2=400,
											system_gamma=1.2,
											ambient_cdm2=5,
											maxsignal=1.0,
											content_rgb_space="DCI P3",
											rolloff=True,
											clutres=33, mode="ICtCp",
											forward_xicclu=None,
											backward_xicclu=None,
											generate_B2A=False,
											worker=None,
											logfile=None):
	"""
	Create a synthetic cLUT profile with the HLG TRC from a colorspace
	definition
	
	mode:  The gamut mapping mode when rolling off. Valid values:
	       "ICtCp" (default), "XYZ", "HSV" (inaccurate),
	       "RGB" (not recommended, saturation loss)
	
	"""

	if not rolloff:
		raise NotImplementedError("rolloff needs to be True")

	return create_synthetic_hdr_clut_profile("HLG", rgb_space, description,
											 black_cdm2, white_cdm2,
											 0,  # Not used for HLG
											 10000,  # Not used for HLG
											 system_gamma,
											 ambient_cdm2,
											 maxsignal,
											 content_rgb_space,
											 clutres,
											 mode,  # Not used for HLG
											 forward_xicclu,
											 backward_xicclu,
											 generate_B2A,
											 worker,
											 logfile)


def _colord_get_display_profile(display_no=0, path_only=False):
	edid = get_edid(display_no)
	if edid:
		# Try a range of possible device IDs
		device_ids = [colord.device_id_from_edid(edid, quirk=True, query=True),
					  colord.device_id_from_edid(edid, quirk=True,
												 truncate_edid_strings=True),
					  colord.device_id_from_edid(edid, quirk=True,
												 use_serial_32=False),
					  colord.device_id_from_edid(edid, quirk=True,
												 use_serial_32=False,
												 truncate_edid_strings=True),
					  colord.device_id_from_edid(edid, quirk=False),
					  colord.device_id_from_edid(edid, quirk=False,
												 truncate_edid_strings=True),
					  colord.device_id_from_edid(edid, quirk=False,
												 use_serial_32=False),
					  colord.device_id_from_edid(edid, quirk=False,
												 use_serial_32=False,
												 truncate_edid_strings=True),
					  # Try with manufacturer omitted
					  colord.device_id_from_edid(edid, omit_manufacturer=True),
					  colord.device_id_from_edid(edid,
												 truncate_edid_strings=True,
												 omit_manufacturer=True),
					  colord.device_id_from_edid(edid, use_serial_32=False,
												 omit_manufacturer=True),
					  colord.device_id_from_edid(edid, use_serial_32=False,
												 truncate_edid_strings=True,
												 omit_manufacturer=True)]
	else:
		# Fall back to XrandR name
		try:
			device_ids = colord.get_display_device_ids()
		except colord.CDError, exception:
			warnings.warn(safe_str(exception, enc), Warning)
			return
		if device_ids and len(device_ids) > display_no:
			edid = {"monitor_name": device_ids[display_no].split("-", 1)[-1]}
			device_ids = [device_ids[display_no]]
	if edid:
		for device_id in OrderedDict.fromkeys(device_ids).iterkeys():
			if device_id:
				try:
					profile_path = colord.get_default_profile(device_id)
				except colord.CDObjectQueryError:
					# Device ID was not found, try next one
					continue
				except colord.CDError, exception:
					warnings.warn(safe_str(exception, enc), Warning)
				else:
					if profile_path:
						if "hash" in edid:
							colord.device_ids[edid["hash"]] = device_id
						if path_only:
							safe_print("Got profile from colord for display %i "
									   "(%s):" % (display_no, device_id),
									   profile_path)
							return profile_path
						return ICCProfile(profile_path)
				break


def _ucmm_get_display_profile(display_no, x_hostname, x_display, x_screen,
							  path_only=False):
	""" Argyll UCMM """
	search = []
	edid = get_edid(display_no)
	if edid:
		# Look for matching EDID entry first
		search.append(("EDID", "0x" + binascii.hexlify(edid["edid"]).upper()))
	# Fallback to X11 name
	search.append(("NAME", "%s:%s.%s" % (x_hostname, x_display, x_screen)))
	for path in [xdg_config_home] + xdg_config_dirs:
		color_jcnf = os.path.join(path, "color.jcnf")
		if os.path.isfile(color_jcnf):
			import json
			with open(color_jcnf) as f:
				data = json.load(f)
			displays = data.get("devices", {}).get("display")
			if isinstance(displays, dict):
				# Look for matching entry
				for key, value in search:
					for item in displays.itervalues():
						if isinstance(item, dict):
							if item.get(key) == value:
								profile_path = item.get("ICC_PROFILE")
								if path_only:
									safe_print("Got profile from Argyll UCMM "
											   "for display %i (%s %s):" %
											   (display_no, key, value),
											   profile_path)
									return profile_path
								return ICCProfile(profile_path)


def _wcs_get_display_profile(devicekey,
							 scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
							 profile_type=COLORPROFILETYPE["ICC"],
							 profile_subtype=COLORPROFILESUBTYPE["NONE"],
							 profile_id=0, path_only=False):
	buf = ctypes.create_unicode_buffer(256)
	if not mscms.WcsGetDefaultColorProfile(scope, devicekey,
										   profile_type,
										   profile_subtype,
										   profile_id,
										   ctypes.sizeof(buf),  # Bytes
										   ctypes.byref(buf)):
		raise util_win.get_windows_error(ctypes.windll.kernel32.GetLastError())
	if buf.value:
		if path_only:
			return os.path.join(iccprofiles[0], buf.value)
		return ICCProfile(buf.value)


def _winreg_get_display_profile(monkey, current_user=False, path_only=False):
	filename = None
	filenames = _winreg_get_display_profiles(monkey, current_user)
	if filenames:
		# last existing file in the list is active
		filename = filenames.pop()
	if not filename and not current_user:
		# fall back to sRGB
		filename = os.path.join(iccprofiles[0], 
								"sRGB Color Space Profile.icm")
	if filename:
		if path_only:
			return os.path.join(iccprofiles[0], filename)
		return ICCProfile(filename)
	return None


def _winreg_get_display_profiles(monkey, current_user=False):
	filenames = []
	try:
		if current_user and sys.getwindowsversion() >= (6, ):
			# Vista / Windows 7 ONLY
			# User has to place a check in 'use my settings for this device'
			# in the color management control panel at least once to cause
			# this key to be created, otherwise it won't exist
			subkey = "\\".join(["Software", "Microsoft", "Windows NT", 
								"CurrentVersion", "ICM", "ProfileAssociations", 
								"Display"] + monkey)
			key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, subkey)
		else:
			subkey = "\\".join(["SYSTEM", "CurrentControlSet", "Control", 
								"Class"] + monkey)
			key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, subkey)
		numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
		for i in range(numvalues):
			name, value, type_ = _winreg.EnumValue(key, i)
			if name == "ICMProfile" and value:
				if type_ == _winreg.REG_BINARY:
					# Win2k/XP
					# convert to list of strings
					value = value.decode('utf-16').split("\0")
				elif type_ == _winreg.REG_MULTI_SZ:
					# Vista / Windows 7
					# nothing to be done, _winreg returns a list of strings
					pass
				if not isinstance(value, list):
					value = [value]
				while "" in value:
					value.remove("")
				filenames.extend(value)
		_winreg.CloseKey(key)
	except WindowsError, exception:
		if exception.args[0] == 2:
			# Key does not exist
			pass
		else:
			raise
	return filter(lambda filename: os.path.isfile(os.path.join(iccprofiles[0], 
															   filename)),
				  filenames)


def _xrandr_get_display_profile(display_no=0, x_hostname="", x_display=0, 
								x_screen=0):
	try:
		property = xrandr.get_output_property(display_no, "_ICC_PROFILE", 
											  xrandr.XA_CARDINAL, x_hostname, 
											  x_display, x_screen)
	except ValueError, exception:
		warnings.warn(safe_str(exception, enc), Warning)
	else:
		if property:
			return ICCProfile("".join(chr(i) for i in property))
	return None


def _x11_get_display_profile(display_no=0, x_hostname="", x_display=0, 
							 x_screen=0):
	try:
		atom = xrandr.get_atom("_ICC_PROFILE" + ("" if display_no == 0 else 
													 "_%s" % display_no), 
							   xrandr.XA_CARDINAL, x_hostname, x_display, 
							   x_screen)
	except ValueError, exception:
		warnings.warn(safe_str(exception, enc), Warning)
	else:
		if atom:
			return ICCProfile("".join(chr(i) for i in atom))
	return None


def get_display_profile(display_no=0, x_hostname="", x_display=0, 
						x_screen=0, win_get_correct_profile=False,
						path_only=False, devicekey=None):
	""" Return ICC Profile for display n or None """
	profile = None
	if sys.platform == "win32":
		if not "win32api" in sys.modules:
			raise ImportError("pywin32 not available")
		if not devicekey:
			# The ordering will work as long as Argyll continues using
			# EnumDisplayMonitors
			monitors = util_win.get_real_display_devices_info()
			moninfo = monitors[display_no]
		if not mscms and not devicekey:
			# Via GetICMProfile. Sucks royally in a multi-monitor setup
			# where one monitor is disabled, because it'll always get
			# the profile of the first monitor regardless if that is the active
			# one or not. Yuck. Also, in this case it does not reflect runtime
			# changes to profile assignments. Double yuck.
			buflen = ctypes.c_ulong(260)
			dc = win32gui.CreateDC(moninfo["Device"], None, None)
			try:
				buf = ctypes.create_unicode_buffer(buflen.value)
				if ctypes.windll.gdi32.GetICMProfileW(dc,
													  ctypes.byref(buflen),  # WCHARs
													  ctypes.byref(buf)):
					if path_only:
						profile = buf.value
					else:
						profile = ICCProfile(buf.value)
			finally:
				win32gui.DeleteDC(dc)
		else:
			if devicekey:
				device = None
			elif win_get_correct_profile:
				# This would be the correct way. Unfortunately that is not
				# what other apps (or Windows itself) do.
				device = util_win.get_active_display_device(moninfo["Device"])
			else:
				# This is wrong, but it's what other apps use. Matches
				# GetICMProfile sucky behavior i.e. should return the same
				# profile, but atleast reflects runtime changes to profile
				# assignments.
				device = win32api.EnumDisplayDevices(moninfo["Device"], 0)
			if device:
				devicekey = device.DeviceKey
		if devicekey:
			if mscms:
				# Via WCS
				if util_win.per_user_profiles_isenabled(devicekey=devicekey):
					scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
				else:
					scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
				return _wcs_get_display_profile(unicode(devicekey), scope,
												path_only=path_only)
			# Via registry - NEVER
			monkey = devicekey.split("\\")[-2:]  # pun totally intended
			# current user
			profile = _winreg_get_display_profile(monkey, True,
												  path_only=path_only)
			if not profile:
				# system
				profile = _winreg_get_display_profile(monkey,
													  path_only=path_only)
	else:
		if sys.platform == "darwin":
			if intlist(mac_ver()[0].split(".")) >= [10, 6]:
				options = ["Image Events"]
			else:
				options = ["ColorSyncScripting"]
		else:
			options = ["_ICC_PROFILE"]
			display = get_display()
			if not x_hostname:
				x_hostname = display[0]
			if not x_display:
				x_display = display[1]
			if not x_screen:
				x_screen = display[2]
		for option in options:
			if sys.platform == "darwin":
				# applescript: one-based index
				applescript = ['tell app "%s"' % option,
								   'set displayProfile to location of display profile of display %i' % (display_no + 1),
								   'return POSIX path of displayProfile',
							   'end tell']
				retcode, output, errors = osascript(applescript)
				if retcode == 0 and output.strip():
					filename = output.strip("\n").decode(fs_enc)
					if path_only:
						profile = filename
					else:
						profile = ICCProfile(filename)
				elif errors.strip():
					raise IOError(errors.strip())
			else:
				# Linux
				# Try colord
				if colord.which("colormgr"):
					profile = _colord_get_display_profile(display_no,
														  path_only=path_only)
					if profile:
						return profile
				if path_only:
					# No way to figure out the profile path from X atom, so use
					# Argyll's UCMM if libcolordcompat.so is not present
					if dlopen("libcolordcompat.so"):
						# UCMM configuration might be stale, ignore
						return
					profile = _ucmm_get_display_profile(display_no,
														x_hostname,
														x_display, x_screen,
														path_only)
					return profile
				# Try XrandR
				if xrandr and option == "_ICC_PROFILE":
					if debug:
						safe_print("Using XrandR")
					profile = _xrandr_get_display_profile(display_no, 
														  x_hostname, 
														  x_display, x_screen)
					if profile:
						return profile
					if debug:
						safe_print("Couldn't get _ICC_PROFILE XrandR output property")
						safe_print("Using X11")
					# Try X11
					profile = _x11_get_display_profile(display_no, 
													   x_hostname, 
													   x_display, x_screen)
					if profile:
						return profile
					if debug:
						safe_print("Couldn't get _ICC_PROFILE X atom")
				# Read up to 8 MB of any X properties
				if debug:
					safe_print("Using xprop")
				xprop = which("xprop")
				if not xprop:
					return
				atom = "%s%s" % (option, "" if display_no == 0 else 
									   "_%s" % display_no)
				tgt_proc = sp.Popen([xprop, "-display", "%s:%s.%s" % 
														  (x_hostname, 
														   x_display, 
														   x_screen), 
									 "-len", "8388608", "-root", "-notype", 
									 atom], stdin=sp.PIPE, stdout=sp.PIPE, 
									stderr=sp.PIPE)
				stdout, stderr = [data.strip("\n") for data in tgt_proc.communicate()]
				if stdout:
					if sys.platform == "darwin":
						filename = unicode(stdout, "UTF-8")
						if path_only:
							profile = filename
						else:
							profile = ICCProfile(filename)
					else:
						raw = [item.strip() for item in stdout.split("=")]
						if raw[0] == atom and len(raw) == 2:
							bin = "".join([chr(int(part)) for part in raw[1].split(", ")])
							profile = ICCProfile(bin)
				elif stderr and tgt_proc.wait() != 0:
					raise IOError(stderr)
			if profile:
				break
	return profile


def _wcs_set_display_profile(devicekey, profile_name,
							 scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]):
	mscms.WcsDisassociateColorProfileFromDevice(scope, profile_name, devicekey)
	if not mscms.WcsAssociateColorProfileWithDevice(scope, profile_name,
													devicekey):
		raise util_win.get_windows_error(ctypes.windll.kernel32.GetLastError())
	return True


def _wcs_unset_display_profile(devicekey, profile_name,
							   scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]):
	if not mscms.WcsDisassociateColorProfileFromDevice(scope, profile_name,
													   devicekey):
		raise util_win.get_windows_error(ctypes.windll.kernel32.GetLastError())
	return True


def set_display_profile(profile_name, display_no=0,
						use_active_display_device=False, devicekey=None):
	# Currently only implemented for Windows.
	# The profile to be assigned has to be already installed!
	if not devicekey:
		device = util_win.get_display_device(display_no,
											 use_active_display_device)
		if not device:
			return False
		devicekey = device.DeviceKey
	if mscms:
		if util_win.per_user_profiles_isenabled(devicekey=devicekey):
			scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
		else:
			scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
		return _wcs_set_display_profile(unicode(devicekey),
										profile_name, scope)
	else:
		# TODO: Implement for XP
		return False


def unset_display_profile(profile_name, display_no=0,
						  use_active_display_device=False, devicekey=None):
	# Currently only implemented for Windows.
	# The profile to be unassigned has to be already installed!
	if not devicekey:
		device = util_win.get_display_device(display_no,
											 use_active_display_device)
		if not device:
			return False
		devicekey = device.DeviceKey
	if mscms:
		if util_win.per_user_profiles_isenabled(devicekey=devicekey):
			scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
		else:
			scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
		return _wcs_unset_display_profile(unicode(devicekey),
										  profile_name, scope)
	else:
		# TODO: Implement for XP
		return False


def _blend_blackpoint(pcs, row, bp_in, bp_out, wp=None, use_bpc=False,
					  weight=False, D50="D50"):
	if pcs == "Lab":
		L, a, b = PCSLab_uInt16_to_dec(*row)
		X, Y, Z = colormath.Lab2XYZ(L, a, b, D50)
	else:
		X, Y, Z = [v / 32768.0 for v in row]
	if use_bpc:
		X, Y, Z = colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp,
									  weight=weight)
	else:
		if wp:
			X, Y, Z = colormath.adapt(X, Y, Z, wp, D50)
			if bp_in:
				bp_in = colormath.adapt(*bp_in,
										whitepoint_source=wp,
										whitepoint_destination=D50)
			if bp_out:
				bp_out = colormath.adapt(*bp_out,
										whitepoint_source=wp,
										whitepoint_destination=D50)
		X, Y, Z = colormath.blend_blackpoint(X, Y, Z, bp_in,
											 bp_out)
		if wp:
			X, Y, Z = colormath.adapt(X, Y, Z, D50, wp)
	if pcs == "Lab":
		L, a, b = colormath.XYZ2Lab(X, Y, Z, D50)
		row = [min(max(0, v), 65535) for v in
			   PCSLab_dec_to_uInt16(L, a, b)]
	else:
		row = [min(max(0, v) * 32768.0, 65535) for v in (X, Y, Z)]
	return row


def _mp_apply_black(blocks, thread_abort_event, progress_queue, pcs, bp, bp_out,
					wp, nonzero_bp, use_bpc, weight, D50, interp, rinterp,
					abortmessage="Aborted"):
	"""
	Worker for applying black point compensation or offset
	
	This should be spawned as a multiprocessing process
	
	"""
	from debughelpers import Info
	for interp_tuple in (interp, rinterp):
		if interp_tuple:
			# Use numpy for speed
			interp_list = list(interp_tuple)
			for i, ointerp in enumerate(interp_list):
				interp_list[i] = colormath.Interp(ointerp.xp, ointerp.fp,
												  use_numpy=True)
				interp_list[i].lookup = ointerp.lookup
			if interp_tuple is interp:
				interp = interp_list
			else:
				rinterp = interp_list
	prevperc = 0
	count = 0
	numblocks = len(blocks)
	for block in blocks:
		if thread_abort_event and thread_abort_event.is_set():
			return Info(abortmessage)
		for i, row in enumerate(block):
			if not use_bpc or nonzero_bp:
				for column, value in enumerate(row):
					row[column] = interp[column](value)
			row = _blend_blackpoint(pcs, row, bp,
									bp_out,
									wp if use_bpc else None,
									use_bpc, weight, D50)
			if not use_bpc or nonzero_bp:
				for column, value in enumerate(row):
					row[column] = rinterp[column](value)
			block[i] = row
		count += 1.0
		perc = round(count / numblocks * 100)
		if progress_queue and perc > prevperc:
			progress_queue.put(perc - prevperc)
			prevperc = perc
	return blocks


def hexrepr(bytestring, mapping=None):
	hexrepr = "0x%s" % binascii.hexlify(bytestring).upper()
	ascii = safe_unicode(re.sub("[^\x20-\x7e]", "", bytestring)).encode("ASCII",
																	    "replace")
	if ascii == bytestring:
		hexrepr += " '%s'" % ascii
		if mapping:
			value = mapping.get(ascii)
			if value:
				hexrepr += " " + value
	return hexrepr


def dateTimeNumber(binaryString):
	"""
	Byte
	Offset Content                                     Encoded as...
	0..1   number of the year (actual year, e.g. 1994) uInt16Number
	2..3   number of the month (1-12)                  uInt16Number
	4..5   number of the day of the month (1-31)       uInt16Number
	6..7   number of hours (0-23)                      uInt16Number
	8..9   number of minutes (0-59)                    uInt16Number
	10..11 number of seconds (0-59)                    uInt16Number
	"""
	Y, m, d, H, M, S = [uInt16Number(chunk) for chunk in (binaryString[:2], 
														  binaryString[2:4], 
														  binaryString[4:6], 
														  binaryString[6:8], 
														  binaryString[8:10], 
														  binaryString[10:12])]
	return datetime.datetime(*(Y, m, d, H, M, S))


def dateTimeNumber_tohex(dt):
	data = [uInt16Number_tohex(n) for n in dt.timetuple()[:6]]
	return "".join(data)


def s15Fixed16Number(binaryString):
	return struct.unpack(">i", binaryString)[0] / 65536.0


def s15Fixed16Number_tohex(num):
	return struct.pack(">i", int(round(num * 65536)))


def u16Fixed16Number(binaryString):
	return struct.unpack(">I", binaryString)[0] / 65536.0


def u16Fixed16Number_tohex(num):
	return struct.pack(">I", int(round(num * 65536)) & 0xFFFFFFFF)


def u8Fixed8Number(binaryString):
	return struct.unpack(">H", binaryString)[0] / 256.0


def u8Fixed8Number_tohex(num):
	return struct.pack(">H", int(round(num * 256)))


def uInt16Number(binaryString):
	return struct.unpack(">H", binaryString)[0]


def uInt16Number_tohex(num):
	return struct.pack(">H", int(round(num)))


def uInt32Number(binaryString):
	return struct.unpack(">I", binaryString)[0]


def uInt32Number_tohex(num):
	return struct.pack(">I", int(round(num)))


def uInt64Number(binaryString):
	return struct.unpack(">Q", binaryString)[0]


def uInt64Number_tohex(num):
	return struct.pack(">Q", int(round(num)))


def uInt8Number(binaryString):
	return struct.unpack(">H", "\0" + binaryString)[0]


def uInt8Number_tohex(num):
	return struct.pack(">H", int(round(num)))[1]


def videoCardGamma(tagData, tagSignature):
	reserved = uInt32Number(tagData[4:8])
	tagType = uInt32Number(tagData[8:12])
	if tagType == 0: # table
		return VideoCardGammaTableType(tagData, tagSignature)
	elif tagType == 1: # formula
		return VideoCardGammaFormulaType(tagData, tagSignature)




class CRInterpolation(object):

	"""
	Catmull-Rom interpolation.
	Curve passes through the points exactly, with neighbouring points influencing curvature.
	points[] should be at least 3 points long.
	"""

	def __init__(self, points):
		self.points = points

	def __call__(self, pos):
		lbound = int(math.floor(pos) - 1)
		ubound = int(math.ceil(pos) + 1)
		t = pos % 1.0
		if abs((lbound + 1) - pos) < 0.0001:
			# sitting on a datapoint, so just return that
			return self.points[lbound + 1]
		if lbound < 0:
			p = self.points[:ubound + 1]
			# extend to the left linearly
			while len(p) < 4:
				p.insert(0, p[0] - (p[1] - p[0]))
		else:
			p = self.points[lbound:ubound + 1]
			# extend to the right linearly
			while len(p) < 4:
				p.append(p[-1] - (p[-2] - p[-1]))
		t2 = t * t
		return 0.5 * ((2 * p[1]) + (-p[0] + p[2]) * t + 
					  ((2 * p[0]) - (5 * p[1]) + (4 * p[2]) - p[3]) * t2 +
					  (-p[0] + (3 * p[1]) - (3 * p[2]) + p[3]) * (t2 * t))


class ADict(dict):

	"""
	Convenience class for dictionary key access via attributes.
	
	Instead of writing aodict[key], you can also write aodict.key
	
	"""

	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)

	def __getattr__(self, name):
		if name in self:
			return self[name]
		else:
			return self.__getattribute__(name)

	def __setattr__(self, name, value):
		self[name] = value


class AODict(ADict, OrderedDict):

	def __init__(self, *args, **kwargs):
		OrderedDict.__init__(self, *args, **kwargs)

	def __setattr__(self, name, value):
		if name == "_keys":
			object.__setattr__(self, name, value)
		else:
			self[name] = value


class LazyLoadTagAODict(AODict):

	"""
	Lazy-load (and parse) tag data on access
	
	"""

	def __init__(self, profile, *args, **kwargs):
		self.profile = profile
		AODict.__init__(self)

	def __getitem__(self, key):
		tag = AODict.__getitem__(self, key)
		if isinstance(tag, ICCProfileTag):
			# Return already parsed tag
			return tag
		# Load and parse tag data
		tagSignature = key
		typeSignature, tagDataOffset, tagDataSize, tagData = tag
		try:
			if tagSignature in tagSignature2Tag:
				tag = tagSignature2Tag[tagSignature](tagData, tagSignature)
			elif typeSignature in typeSignature2Type:
				args = tagData, tagSignature
				if typeSignature in ("clrt", "ncl2"):
					args += (self.profile.connectionColorSpace, )
					if typeSignature == "ncl2":
						args += (self.profile.colorSpace, )
				elif typeSignature in ("XYZ ", "mft2", "curv", "MS10"):
					args += (self.profile, )
				tag = typeSignature2Type[typeSignature](*args)
			else:
				tag = ICCProfileTag(tagData, tagSignature)
		except Exception, exception:
			raise ICCProfileInvalidError("Couldn't parse tag %r (type %r, offet %i, size %i): %r" % (tagSignature,
																									 typeSignature,
																									 tagDataOffset,
																									 tagDataSize,
																									 exception))
		self[key] = tag
		return tag

	def __setattr__(self, name, value):
		if name == "profile":
			object.__setattr__(self, name, value)
		else:
			AODict.__setattr__(self, name, value)

	def get(self, key, default=None):
		if key in self:
			return self[key]
		return default


class ICCProfileTag(object):

	def __init__(self, tagData, tagSignature):
		self.tagData = tagData
		self.tagSignature = tagSignature

	def __setattr__(self, name, value):
		if not isinstance(self, dict) or name in ("_keys", "tagData", 
												  "tagSignature"):
			object.__setattr__(self, name, value)
		else:
			self[name] = value
	
	def __repr__(self):
		"""
		t.__repr__() <==> repr(t)
		"""
		if isinstance(self, OrderedDict):
			return OrderedDict.__repr__(self)
		elif isinstance(self, dict):
			return dict.__repr__(self)
		elif isinstance(self, UserString):
			return UserString.__repr__(self)
		elif isinstance(self, list):
			return list.__repr__(self)
		else:
			if not self:
				return "%s.%s()" % (self.__class__.__module__, self.__class__.__name__)
			return "%s.%s(%r)" % (self.__class__.__module__, self.__class__.__name__, self.tagData)


class Text(ICCProfileTag, UserString, str):

	def __init__(self, seq):
		UserString.__init__(self, seq)

	def __unicode__(self):
		return unicode(self.data, fs_enc, errors="replace")


class Colorant(object):

	def __init__(self, binaryString="\0" * 4):
		self._type = uInt32Number(binaryString)
		self._channels = []
	
	def __getitem__(self, key):
		return self.__getattribute__(key)
	
	def __iter__(self):
		return iter(self.keys())
	
	def __repr__(self):
		items = []
		for key, value in (("type", self.type),
						   ("description", self.description)):
			items.append("%s: %s" % (repr(key), repr(value)))
		channels = []
		for xy in self.channels:
			channels.append("[%s]" % ", ".join([str(v) for v in xy]))
		items.append("'channels': [%s]" % ", ".join(channels))
		return "{%s}" % ", ".join(items)
	
	def __setitem__(self, key, value):
		object.__setattr__(self, key, value)
	
	@Property
	def channels():
		def fget(self):
			if not self._channels and self._type and self._type in colorants:
				return [list(xy) for xy in colorants[self._type]["channels"]]
			return self._channels
		
		def fset(self, channels):
			self._channels = channels
		
		return locals()
	
	@Property
	def description():
		def fget(self):
			return colorants.get(self._type, colorants[0])["description"]
		
		def fset(self, value):
			pass
		
		return locals()
	
	def get(self, key, default=None):
		return getattr(self, key, default)
	
	def items(self):
		return zip(self.keys(), self.values())
	
	def iteritems(self):
		return izip(self.keys(), self.itervalues())
	
	iterkeys = __iter__
	
	def itervalues(self):
		return imap(self.get, self.keys())
	
	def keys(self):
		return ["type", "description", "channels"]
	
	def round(self, digits=4):
		colorant = self.__class__()
		colorant.type = self.type
		for xy in self.channels:
			colorant._channels.append([round(value, digits) for value in xy])
		return colorant
	
	@Property
	def type():
		def fget(self):
			return self._type
		
		def fset(self, value):
			if value and value != self._type and value in colorants:
				self._channels = []
			self._type = value
		
		return locals()
	
	def update(self, *args, **kwargs):
		if len(args) > 1:
			raise TypeError("update expected at most 1 arguments, got %i" % len(args))
		for iterable in args + tuple(kwargs.items()):
			if hasattr(iterable, "iteritems"):
				self.update(iterable.iteritems())
			elif hasattr(iterable, "keys"):
				for key in iterable.keys():
					self[key] = iterable[key]
			else:
				for key, val in iterable:
					self[key] = val
	
	def values(self):
		return map(self.get, self.keys())


class Geometry(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = geometry[self.type]


class Illuminant(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = illuminants[self.type]


class LUT16Type(ICCProfileTag):

	def __init__(self, tagData=None, tagSignature=None, profile=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.profile = profile
		self._matrix = None
		self._input = None
		self._clut = None
		self._output = None
		self._i = (tagData and uInt8Number(tagData[8])) or 0  # Input channel count
		self._o = (tagData and uInt8Number(tagData[9])) or 0  # Output channel count
		self._g = (tagData and uInt8Number(tagData[10])) or 0  # cLUT grid res
		self._n = (tagData and uInt16Number(tagData[48:50])) or 0  # Input channel entries count
		self._m = (tagData and uInt16Number(tagData[50:52])) or 0  # Output channel entries count

	def apply_black_offset(self, XYZbp, logfile=None, thread_abort=None,
						   abortmessage="Aborted"):
		# Apply only the black point blending portion of BT.1886 mapping
		self._apply_black(XYZbp, False, False, logfile, thread_abort,
						  abortmessage)

	def apply_bpc(self, bp_out=(0, 0, 0), weight=False, logfile=None,
				  thread_abort=None, abortmessage="Aborted"):
		return self._apply_black(bp_out, True, weight, logfile,
								 thread_abort, abortmessage)

	def _apply_black(self, bp_out, use_bpc=False, weight=False, logfile=None,
					 thread_abort=None, abortmessage="Aborted"):
		pcs = self.profile and self.profile.connectionColorSpace
		bp_row = list(self.clut[0][0])
		wp_row = list(self.clut[-1][-1])
		nonzero_bp = tuple(bp_out) != (0, 0, 0)
		interp = []
		rinterp = []
		if not use_bpc or nonzero_bp:
			osize = len(self.output[0])
			omaxv = osize - 1.0
			orange = [i / omaxv * 65535 for i in xrange(osize)]
			for i in xrange(3):
				interp.append(colormath.Interp(orange, self.output[i]))
				rinterp.append(colormath.Interp(self.output[i], orange))
			for row in (bp_row, wp_row):
				for column, value in enumerate(row):
					row[column] = interp[column](value)
		if use_bpc:
			method = "apply_bpc"
		else:
			method = "apply_black_offset"
		if pcs == "Lab":
			bp = colormath.Lab2XYZ(*PCSLab_uInt16_to_dec(*bp_row))
			wp = colormath.Lab2XYZ(*PCSLab_uInt16_to_dec(*wp_row))
		elif not pcs or pcs == "XYZ":
			if not pcs:
				warnings.warn("LUT16Type.%s: PCS not specified, "
							  "assuming XYZ" % method, Warning)
			bp = [v / 32768.0 for v in bp_row]
			wp = [v / 32768.0 for v in wp_row]
		else:
			raise ValueError("LUT16Type.%s: Unsupported PCS %r" % (method, pcs))
		if [round(v * 32768) for v in bp] != [round(v * 32768) for v in bp_out]:
			D50 = colormath.get_whitepoint("D50")

			from multiprocess import pool_slice

			if len(self.clut[0]) < 33:
				num_workers = 1
			else:
				num_workers = None

			##if pcs != "Lab" and nonzero_bp:
				##bp_out_offset = bp_out
				##bp_out = (0, 0, 0)

			if bp != bp_out:
				self.clut = sum(pool_slice(_mp_apply_black, self.clut,
										   (pcs, bp, bp_out, wp, nonzero_bp,
										    use_bpc, weight, D50, interp,
										    rinterp, abortmessage), {},
										   num_workers, thread_abort, logfile),
										   [])

			##if pcs != "Lab" and nonzero_bp:
				### Apply black offset to output curves
				##out = [[], [], []]
				##for i in xrange(2049):
					##v = i / 2048.0
					##X, Y, Z = colormath.blend_blackpoint(v, v, v, (0, 0, 0),
														 ##bp_out_offset)
					##out[0].append(X * 2048 / 4095.0 * 65535)
					##out[1].append(Y * 2048 / 4095.0 * 65535)
					##out[2].append(Z * 2048 / 4095.0 * 65535)
				##for i in xrange(2049, 4096):
					##v = i / 4095.0
					##out[0].append(v * 65535)
					##out[1].append(v * 65535)
					##out[2].append(v * 65535)
				##self.output = out

	@Property
	def clut():
		def fget(self):
			if self._clut is None:
				i, o, g, n = self._i, self._o, self._g, self._n
				tagData = self._tagData
				self._clut = [[[uInt16Number(tagData[52 + n * i * 2 + o * 2 * (g * x + y) + z * 2:
													 54 + n * i * 2 + o * 2 * (g * x + y) + z * 2])
								for z in xrange(o)]
							   for y in xrange(g)] for x in xrange(g ** i / g)]
			return self._clut
		
		def fset(self, value):
			self._clut = value
		
		return locals()

	def clut_writepng(self, stream_or_filename):
		""" Write the cLUT as PNG image organized in <grid steps> * <grid steps>
		sized squares, ordered vertically """
		if len(self.clut[0][0]) != 3:
			raise NotImplementedError("clut_writepng: output channels != 3")
		imfile.write(self.clut, stream_or_filename)
	
	@property
	def clut_grid_steps(self):
		""" Return number of grid points per dimension. """
		return self._g
	
	@Property
	def input():
		def fget(self):
			if self._input is None:
				i, n = self._i, self._n
				tagData = self._tagData
				self._input = [[uInt16Number(tagData[52 + n * 2 * z + y * 2:
													 54 + n * 2 * z + y * 2])
								for y in xrange(n)]
							   for z in xrange(i)]
			return self._input
		
		def fset(self, value):
			self._input = value
		
		return locals()
	
	@property
	def input_channels_count(self):
		""" Return number of input channels. """
		return self._i
	
	@property
	def input_entries_count(self):
		""" Return number of entries per input channel. """
		return self._n
	
	def invert(self):
		"""
		Invert input and output tables.
		
		"""
		# Invert input/output 1d LUTs
		for channel in (self.input, self.output):
			for e, entries in enumerate(channel):
				lut = OrderedDict()
				maxv = len(entries) - 1.0
				for i, entry in enumerate(entries):
					lut[entry / 65535.0 * maxv] = i / maxv * 65535
				xp = lut.keys()
				fp = lut.values()
				for i in xrange(len(entries)):
					if not i in lut:
						lut[i] = colormath.interp(i, xp, fp)
				lut.sort()
				channel[e] = lut.values()
	
	@Property
	def matrix():
		def fget(self):
			if self._matrix is None:
				tagData = self._tagData
				return colormath.Matrix3x3([(s15Fixed16Number(tagData[12:16]),
											 s15Fixed16Number(tagData[16:20]),
											 s15Fixed16Number(tagData[20:24])),
											(s15Fixed16Number(tagData[24:28]),
											 s15Fixed16Number(tagData[28:32]),
											 s15Fixed16Number(tagData[32:36])),
											(s15Fixed16Number(tagData[36:40]),
											 s15Fixed16Number(tagData[40:44]),
											 s15Fixed16Number(tagData[44:48]))])
			return self._matrix
		
		def fset(self, value):
			self._matrix = value
		
		return locals()
	
	@Property
	def output():
		def fget(self):
			if self._output is None:
				i, o, g, n, m = self._i, self._o,self._g,  self._n, self._m
				tagData = self._tagData
				self._output = [[uInt16Number(tagData[52 + n * i * 2 + m * 2 * z + y * 2 +
													  g ** i * o * 2:
													  54 + n * i * 2 + m * 2 * z + y * 2 +
													  g ** i * o * 2])
								 for y in xrange(m)]
								for z in xrange(o)]
			return self._output
		
		def fset(self, value):
			self._output = value
		
		return locals()
	
	@property
	def output_channels_count(self):
		""" Return number of output channels. """
		return self._o
	
	@property
	def output_entries_count(self):
		""" Return number of entries per output channel. """
		return self._m

	def smooth(self, diagpng=2, pcs=None, filename=None, logfile=None):
		""" Apply extra smoothing to the cLUT """
		if not pcs:
			if self.profile:
				pcs = self.profile.connectionColorSpace
			else:
				raise TypeError("PCS not specified")

		if not filename and self.profile:
			filename = self.profile.fileName

		clutres = len(self.clut[0])

		sig = self.tagSignature or id(self)

		if diagpng and filename:
			# Generate diagnostic images
			fname, ext = os.path.splitext(filename)
			if diagpng == 2:
				self.clut_writepng(fname + ".%s.pre-smoothing.CLUT.png" %
								   sig)

		if logfile:
			logfile.write("Smoothing %s...\n" % sig)
		# Create a list of <clutres> number of 2D grids, each one with a
		# size of (width x height) <clutres> x <clutres>
		grids = []
		for i, block in enumerate(self.clut):
			if i % clutres == 0:
				grids.append([])
			grids[-1].append([])
			for RGB in block:
				grids[-1][-1].append(RGB)
		for i, grid in enumerate(grids):
			for y in xrange(clutres):
				for x in xrange(clutres):
					is_dark = sum(grid[y][x]) < 65535 * .03125 * 3
					if pcs == "XYZ":
						is_gray = x == y == i
					elif clutres // 2 != clutres / 2.0:
						# For CIELab cLUT, gray will only
						# fall on a cLUT point if uneven cLUT res
						is_gray = x == y == clutres // 2
					else:
						is_gray = False
					##print i, y, x, "%i %i %i" % tuple(v / 655.35 * 2.55 for v in grid[y][x]), is_dark, raw_input(is_gray) if is_gray else ''
					if is_dark or is_gray:
						# Don't smooth dark colors and gray axis
						continue
					RGB = [[v] for v in grid[y][x]]
					# Use either "plus"-shaped or box filter depending if one
					# channel is fully saturated
					if clutres - 1 in (i, y, x):
						# Filter with a "plus" (+) shape
						if (pcs == "Lab" and
							i > clutres / 2.0):
							# Smoothing factor for L*a*b* -> RGB cLUT above 50%
							smooth = 0.25
						else:
							smooth = 1.0
						for j, c in enumerate((x, y)):
							if c > 0 and c < clutres - 1 and y < clutres - 1:
								for n in (-1, 1):
									RGBn = grid[(y, y + n)[j]][(x + n, x)[j]]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * smooth +
													  RGB[k][0] * (1 - smooth))
					else:
						# Box filter, 3x3
						# Center pixel weight = 1.0, surround = 0.5
						for j in (0, 1):
							for n in (-1, 1):
								yi, xi = (y, y + n)[j], (x + n, x)[j]
								if (xi > -1 and yi > -1 and
									xi < clutres and yi < clutres):
									RGBn = grid[yi][xi]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * 0.5 +
													  RGB[k][0] * 0.5)
								yi, xi = y - n, (x + n, x - n)[j]
								if (xi > -1 and yi > -1 and
									xi < clutres and yi < clutres):
									RGBn = grid[yi][xi]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * 0.5 +
													  RGB[k][0] * 0.5)
					grid[y][x] = [sum(v) / float(len(v)) for v in RGB]
			for j, row in enumerate(grid):
				self.clut[i * clutres + j] = [[v for v in RGB]
											   for RGB in row]

		if diagpng and filename:
			self.clut_writepng(fname + ".%s.post.CLUT.extrasmooth.png" %
							   sig)
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			if (self._matrix, self._input, self._clut, self._output) == (None, ) * 4:
				return self._tagData
			tagData = ["mft2", "\0" * 4,
					   uInt8Number_tohex(len(self.input)),
					   uInt8Number_tohex(len(self.output)),
					   uInt8Number_tohex(len(self.clut and self.clut[0])),
					   "\0",
					   s15Fixed16Number_tohex(self.matrix[0][0]),
					   s15Fixed16Number_tohex(self.matrix[0][1]),
					   s15Fixed16Number_tohex(self.matrix[0][2]),
					   s15Fixed16Number_tohex(self.matrix[1][0]),
					   s15Fixed16Number_tohex(self.matrix[1][1]),
					   s15Fixed16Number_tohex(self.matrix[1][2]),
					   s15Fixed16Number_tohex(self.matrix[2][0]),
					   s15Fixed16Number_tohex(self.matrix[2][1]),
					   s15Fixed16Number_tohex(self.matrix[2][2]),
					   uInt16Number_tohex(len(self.input and self.input[0])),
					   uInt16Number_tohex(len(self.output and self.output[0]))]
			for entries in self.input:
				tagData.extend(uInt16Number_tohex(v) for v in entries)
			for block in self.clut:
				for entries in block:
					tagData.extend(uInt16Number_tohex(v) for v in entries)
			for entries in self.output:
				tagData.extend(uInt16Number_tohex(v) for v in entries)
			return "".join(tagData)
		
		def fset(self, tagData):
			self._tagData = tagData
		
		return locals()


class Observer(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = observers[self.type]


class ChromaticityType(ICCProfileTag, Colorant):

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if not tagData:
			Colorant.__init__(self, uInt32Number_tohex(1))
			return
		deviceChannelsCount = uInt16Number(tagData[8:10])
		Colorant.__init__(self,
						  uInt32Number_tohex(uInt16Number(tagData[10:12])))
		channels = tagData[12:]
		for count in xrange(deviceChannelsCount):
			self._channels.append([u16Fixed16Number(channels[:4]), 
								   u16Fixed16Number(channels[4:8])])
			channels = channels[8:]
	
	__repr__ = Colorant.__repr__
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["chrm", "\0" * 4, uInt16Number_tohex(len(self.channels))]
			tagData.append(uInt16Number_tohex(self.type))
			for channel in self.channels:
				for xy in channel:
					tagData.append(u16Fixed16Number_tohex(xy))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class ColorantTableType(ICCProfileTag, AODict):

	def __init__(self, tagData=None, tagSignature=None, pcs=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		if not tagData:
			return
		colorantCount = uInt32Number(tagData[8:12])
		data = tagData[12:]
		for count in xrange(colorantCount):
			pcsvalues = [uInt16Number(data[32:34]),
						 uInt16Number(data[34:36]),
						 uInt16Number(data[36:38])]
			for i, pcsvalue in enumerate(pcsvalues):
				if pcs in ("Lab", "RGB", "CMYK", "YCbr"):
					keys = ["L", "a", "b"]
					if i == 0:
						# L* range 0..100 + (25500 / 65280.0)
						pcsvalues[i] = pcsvalue / 65536.0 * 256 / 255.0 * 100
					else:
						# a, b range -128..127 + (255 / 256.0)
						pcsvalues[i] = -128 + (pcsvalue / 65536.0 * 256)
				elif pcs == "XYZ":
					# X, Y, Z range 0..100 + (32767 / 32768.0)
					keys = ["X", "Y", "Z"]
					pcsvalues[i] = pcsvalue / 32768.0 * 100
				else:
					safe_print("Warning: Non-standard profile connection "
							   "space '%s'" % pcs)
					return
			end = data[:32].find("\0")
			if end < 0:
				end = 32
			name = data[:end]
			self[name] = AODict(zip(keys, pcsvalues))
			data = data[38:]


class CurveType(ICCProfileTag, list):

	def __init__(self, tagData=None, tagSignature=None, profile=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.profile = profile
		self._reset()
		if not tagData:
			return
		curveEntriesCount = uInt32Number(tagData[8:12])
		curveEntries = tagData[12:]
		if curveEntriesCount == 1:
			# Gamma
			self.append(u8Fixed8Number(curveEntries[:2]))
		elif curveEntriesCount:
			# Curve
			for count in xrange(curveEntriesCount):
				self.append(uInt16Number(curveEntries[:2]))
				curveEntries = curveEntries[2:]
		else:
			# Identity
			self.append(1.0)
	
	def __delitem__(self, y):
		list.__delitem__(self, y)
		self._reset()
	
	def __delslice__(self, i, j):
		list.__delslice__(self, i, j)
		self._reset()
	
	def __iadd__(self, y):
		list.__iadd__(self, y)
		self._reset()
	
	def __imul__(self, y):
		list.__imul__(self, y)
		self._reset()
	
	def __setitem__(self, i, y):
		list.__setitem__(self, i, y)
		self._reset()
	
	def __setslice__(self, i, j, y):
		list.__setslice__(self, i, j, y)
		self._reset()

	def _reset(self):
		self._transfer_function = {}
		self._bt1886 = {}
	
	def append(self, object):
		list.append(self, object)
		self._reset()
	
	def apply_bpc(self, black_Y_out=0, weight=False):
		if len(self) < 2:
			return
		D50_xyY = colormath.XYZ2xyY(*colormath.get_whitepoint("D50"))
		bp_in = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[0] / 65535.0)
		bp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], black_Y_out)
		wp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[-1] / 65535.0)
		for i, v in enumerate(self):
			X, Y, Z = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], v / 65535.0)
			self[i] = colormath.apply_bpc(X, Y, Z, bp_in, bp_out,
										  wp_out, weight)[1] * 65535.0
	
	def extend(self, iterable):
		list.extend(self, iterable)
		self._reset()
	
	def get_gamma(self, use_vmin_vmax=False, average=True, least_squares=False,
				  slice=(0.01, 0.99), lstar_slice=True):
		""" Return average or least squares gamma or a list of gamma values """
		if len(self) <= 1:
			if len(self):
				values = self
			else:
				# Identity
				values = [1.0]
			if average or least_squares:
				return values[0]
			return [values[0]]
		if lstar_slice:
			start = slice[0] * 100
			end = slice[1] * 100
			values = []
			for i, y in enumerate(self):
				n = colormath.XYZ2Lab(0, y / 65535.0 * 100, 0)[0]
				if n >= start and n <= end:
					values.append((i / (len(self) - 1.0) * 65535.0, y))
		else:
			maxv = len(self) - 1.0
			maxi = int(maxv)
			starti = int(round(slice[0] * maxi))
			endi = int(round(slice[1] * maxi)) + 1
			values = zip([(v / maxv) * 65535 for v in xrange(starti, endi)],
						 self[starti:endi])
		vmin = 0
		vmax = 65535.0
		if use_vmin_vmax:
			if len(self) > 2:
				vmin = self[0]
				vmax = self[-1]
		return colormath.get_gamma(values, 65535.0, vmin, vmax, average, least_squares)
	
	def get_transfer_function(self, best=True, slice=(0.05, 0.95), black_Y=None,
							  outoffset=None):
		"""
		Return transfer function name, exponent and match percentage
		
		"""
		if len(self) == 1:
			# Gamma
			return ("Gamma %.2f" % round(self[0], 2), self[0], 1.0), 1.0
		if not len(self):
			# Identity
			return ("Gamma 1.0", 1.0, 1.0), 1.0
		transfer_function = self._transfer_function.get((best, slice))
		if transfer_function:
			return transfer_function
		trc = CurveType()
		match = {}
		otrc = CurveType()
		otrc[:] = self
		if otrc[0]:
			otrc.apply_bpc()
		vmin = otrc[0]
		vmax = otrc[-1]
		if self.profile and isinstance(self.profile.tags.get("lumi"),
									   XYZType):
			white_cdm2 = self.profile.tags.lumi.Y
		else:
			white_cdm2 = 100.0
		if black_Y is None:
			black_Y = self[0] / 65535.0
		black_cdm2 = black_Y * white_cdm2
		maxv = len(otrc) - 1.0
		maxi = int(maxv)
		starti = int(round(0.4 * maxi))
		endi = int(round(0.6 * maxi))
		gamma = otrc.get_gamma(True, slice=(0.4, 0.6), lstar_slice=False)
		egamma = colormath.get_gamma([(0.5, 0.5 ** gamma)], vmin=-black_Y)
		outoffset_unspecified = outoffset is None
		if outoffset_unspecified:
			outoffset = 1.0
		tfs = [("Rec. 709", -709, outoffset),
			   ("Rec. 1886", -1886, 0),
			   ("SMPTE 240M", -240, outoffset),
			   ("SMPTE 2084", -2084, outoffset),
			   ("DICOM", -1023, outoffset),
			   ("L*", -3.0, outoffset),
			   ("sRGB", -2.4, outoffset),
			   ("Gamma %.2f %i%%" % (round(gamma, 2), round(outoffset * 100)),
									gamma, outoffset)]
		if outoffset_unspecified and black_Y:
			for i in xrange(100):
				tfs.append(("Gamma %.2f %i%%" % (round(gamma, 2), i),
							gamma, i / 100.0))
		for name, exp, outoffset in tfs:
			if name in ("DICOM", "Rec. 1886", "SMPTE 2084"):
				try:
					if name == "DICOM":
						trc.set_dicom_trc(black_cdm2, white_cdm2, size=len(self))
					elif name == "Rec. 1886":
						trc.set_bt1886_trc(black_Y, size=len(self))
					elif name == "SMPTE 2084":
						trc.set_smpte2084_trc(black_cdm2, white_cdm2, size=len(self))
				except ValueError:
					continue
			elif exp > 0 and black_Y:
				trc.set_bt1886_trc(black_Y, outoffset, egamma, "b")
			else:
				trc.set_trc(exp, len(self), vmin, vmax)
			if trc[0]:
				trc.apply_bpc()
			if otrc == trc:
				match[(name, exp, outoffset)] = 1.0
			else:
				match[(name, exp, outoffset)] = 0.0
				count = 0
				start = slice[0] * len(self)
				end = slice[1] * len(self)
				for i, n in enumerate(otrc):
					##n = colormath.XYZ2Lab(0, n / 65535.0 * 100, 0)[0]
					if i >= start and i <= end:
						n = colormath.get_gamma([(i / (len(self) - 1.0) * 65535.0, n)], 65535.0, vmin, vmax, False)
						if n:
							n = n[0]
							##n2 = colormath.XYZ2Lab(0, trc[i] / 65535.0 * 100, 0)[0]
							n2 = colormath.get_gamma([(i / (len(self) - 1.0) * 65535.0, trc[i])], 65535.0, vmin, vmax, False)
							if n2 and n2[0]:
								n2 = n2[0]
								match[(name, exp, outoffset)] += 1 - (max(n, n2) - min(n, n2)) / ((n + n2) / 2.0)
								count += 1
				if count:
					match[(name, exp, outoffset)] /= count
		if not best:
			self._transfer_function[(best, slice)] = match
			return match
		match, (name, exp, outoffset) = sorted(zip(match.values(), match.keys()))[-1]
		self._transfer_function[(best, slice)] = (name, exp, outoffset), match
		return (name, exp, outoffset), match
	
	def insert(self, object):
		list.insert(self, object)
		self._reset()
	
	def pop(self, index):
		list.pop(self, index)
		self._reset()
	
	def remove(self, value):
		list.remove(self, value)
		self._reset()
	
	def reverse(self):
		list.reverse(self)
		self._reset()
	
	def set_bt1886_trc(self, black_Y=0, outoffset=0.0, gamma=2.4,
					   gamma_type="B", size=None):
		"""
		Set the response to the BT. 1886 curve
		
		This response is special in that it depends on the actual black
		level of the display.
		
		"""
		bt1886 = self._bt1886.get((gamma, black_Y, outoffset))
		if bt1886:
			return bt1886
		if gamma_type in ("b", "g"):
			# Get technical gamma needed to achieve effective gamma
			gamma = colormath.xicc_tech_gamma(gamma, black_Y, outoffset)
		rXYZ = colormath.RGB2XYZ(1.0, 0, 0)
		gXYZ = colormath.RGB2XYZ(0, 1.0, 0)
		bXYZ = colormath.RGB2XYZ(0, 0, 1.0)
		mtx = colormath.Matrix3x3([[rXYZ[0], gXYZ[0], bXYZ[0]],
								   [rXYZ[1], gXYZ[1], bXYZ[1]],
								   [rXYZ[2], gXYZ[2], bXYZ[2]]])
		wXYZ = colormath.RGB2XYZ(1.0, 1.0, 1.0)
		x, y = colormath.XYZ2xyY(*wXYZ)[:2]
		XYZbp = colormath.xyY2XYZ(x, y, black_Y)
		bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
		self._bt1886[(gamma, black_Y, outoffset)] = bt1886
		self.set_trc(-709, size)
		for i, v in enumerate(self):
			X, Y, Z = colormath.xyY2XYZ(x, y, v / 65535.0)
			self[i] = bt1886.apply(X, Y, Z)[1] * 65535.0
	
	def set_dicom_trc(self, black_cdm2=.05, white_cdm2=100, size=None):
		"""
		Set the response to the DICOM Grayscale Standard Display Function
		
		This response is special in that it depends on the actual black
		and white level of the display.
		
		"""
		# See http://medical.nema.org/Dicom/2011/11_14pu.pdf
		# Luminance levels depend on the start level of 0.05 cd/m2
		# and end level of 4000 cd/m2
		if black_cdm2 < .05 or black_cdm2 >= white_cdm2:
			raise ValueError("The black level of %f cd/m2 is out of range "
							 "for DICOM. Valid range begins at 0.05 cd/m2." %
							 black_cdm2)
		if white_cdm2 > 4000 or white_cdm2 <= black_cdm2:
			raise ValueError("The white level of %f cd/m2 is out of range "
							 "for DICOM. Valid range is up to 4000 cd/m2." %
							 white_cdm2)
		black_jndi = colormath.DICOM(black_cdm2, True)
		white_jndi = colormath.DICOM(white_cdm2, True)
		white_dicomY = math.pow(10, colormath.DICOM(white_jndi))
		if not size:
			size = len(self)
		if size < 2:
			size = 1024
		self[:] = []
		for i in xrange(size):
			v = math.pow(10, colormath.DICOM(black_jndi +
											 (float(i) / (size - 1)) *
											 (white_jndi -
											  black_jndi))) / white_dicomY
			self.append(v * 65535)
	
	def set_hlg_trc(self, black_cdm2=0, white_cdm2=100, system_gamma=1.2,
					ambient_cdm2=5, maxsignal=1.0, size=None):
		"""
		Set the response to the Hybrid Log-Gamma (HLG) function
		
		This response is special in that it depends on the actual black
		and white level of the display, system gamma and ambient.
		
		XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
		maxsignal       Set clipping point (optional)
		size            Number of steps. Recommended >= 1024
		
		"""
		if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
			raise ValueError("The black level of %f cd/m2 is out of range "
							 "for HLG. Valid range begins at 0 cd/m2." %
							 black_cdm2)
		values = []

		hlg = colormath.HLG(black_cdm2, white_cdm2, system_gamma, ambient_cdm2)

		if maxsignal < 1:
			# Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
			while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
				hlg.white_cdm2 += 1

		lscale = 1.0 / hlg.oetf(1.0, True)
		hlg.white_cdm2 *= lscale
		if lscale < 1 and logfile:
			logfile.write("Nominal peak luminance after scaling = %.2f\n" %
						  hlg.white_cdm2)

		maxv = hlg.eotf(maxsignal)
		if not size:
			size = len(self)
		if size < 2:
			size = 1024
		for i in xrange(size):
			n = i / (size - 1.0)
			v = hlg.eotf(min(n, maxsignal))
			values.append(min(v / maxv, 1.0))
		self[:] = [min(v * 65535, 65535) for v in values]
	
	def set_smpte2084_trc(self, black_cdm2=0, white_cdm2=100,
						  master_black_cdm2=0, master_white_cdm2=None,
						  rolloff=False, size=None):
		"""
		Set the response to the SMPTE 2084 perceptual quantizer (PQ) function
		
		This response is special in that it depends on the actual black
		and white level of the display.
		
		black_cdm2      Black point in absolute Y, range 0..white_cdm2
		master_black_cdm2  (Optional) Used to normalize PQ values
		master_white_cdm2  (Optional) Used to normalize PQ values
		rolloff         BT.2390
		size            Number of steps. Recommended >= 1024
		
		"""
		# See https://www.smpte.org/sites/default/files/2014-05-06-EOTF-Miller-1-2-handout.pdf
		# Luminance levels depend on the end level of 10000 cd/m2
		if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
			raise ValueError("The black level of %f cd/m2 is out of range "
							 "for SMPTE 2084. Valid range begins at 0 cd/m2." %
							 black_cdm2)
		if max(white_cdm2, master_white_cdm2) > 10000:
			raise ValueError("The white level of %f cd/m2 is out of range "
							 "for SMPTE 2084. Valid range is up to 10000 cd/m2." %
							 max(white_cdm2, master_white_cdm2))
		values = []
		maxv = white_cdm2 / 10000.0
		maxi = colormath.specialpow(maxv, 1.0 / -2084)
		if rolloff:
			# Rolloff as defined in ITU-R BT.2390
			if not master_white_cdm2:
				master_white_cdm2 = 10000
			bt2390 = colormath.BT2390(black_cdm2, white_cdm2, master_black_cdm2,
									  master_white_cdm2)
			maxi_out = maxi
		else:
			if not master_white_cdm2:
				master_white_cdm2 = white_cdm2
			maxi_out = colormath.specialpow(master_white_cdm2 / 10000.0,
											1.0 / -2084)
		if not size:
			size = len(self)
		if size < 2:
			size = 1024
		for i in xrange(size):
			n = i / (size - 1.0)
			if rolloff:
				n = bt2390.apply(n)
			v = colormath.specialpow(n * (maxi / maxi_out), -2084)
			values.append(min(v / maxv, 1.0))
		self[:] = [min(v * 65535, 65535) for v in values]
		if black_cdm2 and not rolloff:
			self.apply_bpc(black_cdm2 / white_cdm2)
	
	def set_trc(self, power=2.2, size=None, vmin=0, vmax=65535):
		"""
		Set the response to a certain function.
		
		Positive power, or -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
		-601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
		identical)
		
		"""
		if not size:
			size = len(self) or 1024
		if size == 1:
			if power >= 0.0 and not vmin:
				self[:] = [power]
				return
			else:
				size = 1024
		self[:] = []
		for i in xrange(0, size):
			self.append(vmin + colormath.specialpow(float(i) / (size - 1), power) * (vmax - vmin))
	
	def smooth_cr(self, length=64):
		"""
		Smooth curves (Catmull-Rom).
		"""
		raise NotImplementedError()
	
	def smooth_avg(self, passes=1, window=None):
		"""
		Smooth curves (moving average).
		
		passses   Number of passes
		window    Tuple or list containing weighting factors. Its length
		          determines the size of the window to use.
		          Defaults to (1.0, 1.0, 1.0)
		
		"""
		self[:] = colormath.smooth_avg(self, passes, window)
	
	def sort(self, cmp=None, key=None, reverse=False):
		list.sort(self, cmp, key, reverse)
		self._reset()
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			if len(self) == 1 and self[0] == 1.0:
				# Identity
				curveEntriesCount = 0
			else:
				curveEntriesCount = len(self)
			tagData = ["curv", "\0" * 4, uInt32Number_tohex(curveEntriesCount)]
			if curveEntriesCount == 1:
				# Gamma
				tagData.append(u8Fixed8Number_tohex(self[0]))
			elif curveEntriesCount:
				# Curve
				for curveEntry in self:
					tagData.append(uInt16Number_tohex(curveEntry))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class DateTimeType(ICCProfileTag, datetime.datetime):
	
	def __new__(cls, tagData, tagSignature):
		dt = dateTimeNumber(tagData[8:20])
		return datetime.datetime.__new__(cls, dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


class DictList(list):
	
	def __getitem__(self, key):
		for item in self:
			if item[0] == key:
				return item
		raise KeyError(key)

	def __setitem__(self, key, value):
		if not isinstance(value, DictListItem):
			self.append(DictListItem((key, value)))


class DictListItem(list):
	
	def __iadd__(self, value):
		self[-1] += value
		return self


class DictType(ICCProfileTag, AODict):
	""" ICC dictType Tag
	
	Implements all features of 'Dictionary Type and Metadata TAG Definition'
	(ICC spec revision 2010-02-25), including shared data (the latter will
	only be effective for mutable types, ie. MultiLocalizedUnicodeType)
	
	Examples:
	
	tag[key]   Returns the (non-localized) value
	tag.getname(key, locale='en_US') Returns the localized name if present
	tag.getvalue(key, locale='en_US') Returns the localized value if present
	tag[key] = value   Sets the (non-localized) value
	
	"""

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		if not tagData:
			return
		numrecords = uInt32Number(tagData[8:12])
		recordlen = uInt32Number(tagData[12:16])
		if recordlen not in (16, 24, 32):
			safe_print("Error (non-critical): '%s' invalid record length "
					   "(expected 16, 24 or 32, got %s)" % (tagData[:4],
															recordlen))
			return
		elements = {}
		for n in range(0, numrecords):
			record = tagData[16 + n * recordlen:16 + (n + 1) * recordlen]
			if len(record) < recordlen:
				safe_print("Error (non-critical): '%s' record %s too short "
						   "(expected %s bytes, got %s bytes)" % (tagData[:4],
																  n,
																  recordlen,
																  len(record)))
				break
			for key, offsetpos in (("name", 0), ("value", 8),
								   ("display_name", 16), ("display_value", 24)):
				if (offsetpos in (0, 8) or recordlen == offsetpos + 8 or
					recordlen == offsetpos + 16):
					# Required:
					# Bytes 0..3, 4..7: Name offset and size
					# Bytes 8..11, 12..15: Value offset and size
					# Optional:
					# Bytes 16..23, 24..23: Display name offset and size
					# Bytes 24..27, 28..31: Display value offset and size
					offset = uInt32Number(record[offsetpos:offsetpos + 4])
					size = uInt32Number(record[offsetpos + 4:offsetpos + 8])
					if offset > 0:
						if (offset, size) in elements:
							# Use existing element if same offset and size
							# This will really only make a difference for
							# mutable types ie. MultiLocalizedUnicodeType
							data = elements[(offset, size)]
						else:
							data = tagData[offset:offset + size]
							try:
								if key.startswith("display_"):
									data = MultiLocalizedUnicodeType(data,
																	 "mluc")
								else:
									data = data.decode("UTF-16-BE",
													   "replace").rstrip("\0")
							except Exception, exception:
								safe_print("Error (non-critical): could not "
										   "decode '%s', offset %s, length %s" %
										   (tagData[:4], offset, size))
							# Remember element by offset and size
							elements[(offset, size)] = data
						if key == "name":
							name = data
							self[name] = ""
						else:
							self.get(name)[key] = data

	def __getitem__(self, name):
		return self.get(name).value

	def __setitem__(self, name, value):
		AODict.__setitem__(self, name, ADict(value=value))

	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""

		def fget(self):
			numrecords = len(self)
			recordlen = 16
			keys = ("name", "value")
			for value in self.itervalues():
				if "display_value" in value:
					recordlen = 32
					break
				elif "display_name" in value:
					recordlen = 24
			if recordlen > 16:
				keys += ("display_name", )
			if recordlen > 24:
				keys += ("display_value", )
			tagData = ["dict", "\0" * 4, uInt32Number_tohex(numrecords),
					   uInt32Number_tohex(recordlen)]
			storage_offset = 16 + numrecords * recordlen
			storage = []
			elements = []
			offsets = []
			for item in self.iteritems():
				for key in keys:
					if key == "name":
						element = item[0]
					else:
						element = item[1].get(key)
					if element is None:
						offset = 0
						size = 0
					else:
						if element in elements:
							# Use existing offset and size if same element
							offset, size = offsets[elements.index(element)]
						else:
							offset = storage_offset + len("".join(storage))
							if isinstance(element, MultiLocalizedUnicodeType):
								data = element.tagData
							else:
								data = unicode(element).encode("UTF-16-BE")
							size = len(data)
							if isinstance(element, MultiLocalizedUnicodeType):
								# Remember element, offset and size
								elements.append(element)
								offsets.append((offset, size))
							# Pad all data with binary zeros so it lies on 
							# 4-byte boundaries
							padding = int(math.ceil(size / 4.0)) * 4 - size
							data += "\0" * padding
							storage.append(data)
					tagData.append(uInt32Number_tohex(offset))
					tagData.append(uInt32Number_tohex(size))
			tagData.extend(storage)
			return "".join(tagData)

		def fset(self, tagData):
			pass

		return locals()

	def getname(self, name, default=None, locale="en_US"):
		""" Convenience function to get (localized) names
		
		"""
		item = self.get(name, default)
		if item is default:
			return default
		if locale and "display_name" in item:
			return item.display_name.get_localized_string(*locale.split("_"))
		else:
			return name

	def getvalue(self, name, default=None, locale="en_US"):
		""" Convenience function to get (localized) values
		
		"""
		item = self.get(name, default)
		if item is default:
			return default
		if locale and "display_value" in item:
			return item.display_value.get_localized_string(*locale.split("_"))
		else:
			return item.value

	def setitem(self, name, value, display_name=None, display_value=None):
		""" Convenience function to set items
		
		display_name and display_value (if given) should be dict types with
		country -> language -> string mappings, e.g.:
		
		{"en": {"US": u"localized string"},
		 "de": {"DE": u"localized string", "CH": u"localized string"}}
		
		"""
		self[name] = value
		item = self.get(name)
		if display_name:
			item.display_name = MultiLocalizedUnicodeType()
			item.display_name.update(display_name)
		if display_value:
			item.display_value = MultiLocalizedUnicodeType()
			item.display_value.update(display_value)

	def to_json(self, encoding="UTF-8", errors="replace", locale="en_US"):
		""" Return a JSON representation
		
		Display names/values are used if present.
		
		"""
		json = []
		for name in self:
			value = self.getvalue(name, None, locale)
			name = self.getname(name, None, locale)
			#try:
				#value = str(int(value))
			#except ValueError:
				#try:
					#value = str(float(value))
				#except ValueError:
			value = '"%s"' % repr(unicode(value))[2:-1].replace('"', '\\"')
			json.append('"%s": %s' % tuple([re.sub(r"\\x([0-9a-f]{2})",
												   "\\u00\\1", item)
											for item in [repr(unicode(name))[2:-1],
														 value]]))
		return "{%s}" % ",\n".join(json)


class MakeAndModelType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.update({"manufacturer": tagData[10:12],
					 "model": tagData[14:16]})



class MeasurementType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.update({
			"observer": Observer(tagData[8:12]),
			"backing": XYZNumber(tagData[12:24]),
			"geometry": Geometry(tagData[24:28]),
			"flare": u16Fixed16Number(tagData[28:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class MultiLocalizedUnicodeType(ICCProfileTag, AODict): # ICC v4

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		if not tagData:
			return
		recordsCount = uInt32Number(tagData[8:12])
		recordSize = uInt32Number(tagData[12:16]) # 12
		if recordSize != 12:
			safe_print("Warning (non-critical): '%s' invalid record length "
					   "(expected 12, got %s)" % (tagData[:4], recordSize))
			if recordSize < 12:
				recordSize = 12
		records = tagData[16:16 + recordSize * recordsCount]
		for count in xrange(recordsCount):
			record = records[:recordSize]
			if len(record) < 12:
				continue
			recordLanguageCode = record[:2]
			recordCountryCode = record[2:4]
			recordLength = uInt32Number(record[4:8])
			recordOffset = uInt32Number(record[8:12])
			self.add_localized_string(recordLanguageCode, recordCountryCode,
				unicode(tagData[recordOffset:recordOffset + recordLength], 
						"utf-16-be", "replace"))
			records = records[recordSize:]

	def __str__(self):
		return unicode(self).encode(sys.getdefaultencoding())

	def __unicode__(self):
		"""
		Return tag as string.
		"""
		# TODO: Needs some work re locales
		# (currently if en-UK or en-US is not found, simply the first entry 
		# is returned)
		if "en" in self:
			for countryCode in ("UK", "US"):
				if countryCode in self["en"]:
					return self["en"][countryCode]
		elif len(self):
			return self.values()[0].values()[0]
		else:
			return u""

	def add_localized_string(self, languagecode, countrycode, localized_string):
		""" Convenience function for adding localized strings """
		if languagecode not in self:
			self[languagecode] = AODict()
		self[languagecode][countrycode] = localized_string.strip("\0")

	def get_localized_string(self, languagecode="en", countrycode="US"):
		""" Convenience function for retrieving localized strings
		
		Falls back to first locale available if the requested one isn't
		
		"""
		try:
			return self[languagecode][countrycode]
		except KeyError:
			return unicode(self)


	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""

		def fget(self):
			tagData = ["mluc", "\0" * 4]
			recordsCount = 0
			for languageCode in self:
				for countryCode in self[languageCode]:
					recordsCount += 1
			tagData.append(uInt32Number_tohex(recordsCount))
			recordSize = 12
			tagData.append(uInt32Number_tohex(recordSize))
			storage_offset = 16 + recordSize * recordsCount
			storage = []
			offsets = []
			for languageCode in self:
				for countryCode in self[languageCode]:
					tagData.append(languageCode + countryCode)
					data = self[languageCode][countryCode].encode("UTF-16-BE")
					if data in storage:
						offset, recordLength = offsets[storage.index(data)]
					else:
						recordLength = len(data)
						offset = len("".join(storage))
						offsets.append((offset, recordLength))
						storage.append(data)
					tagData.append(uInt32Number_tohex(recordLength))
					tagData.append(uInt32Number_tohex(storage_offset + offset))
			tagData.append("".join(storage))
			return "".join(tagData)

		def fset(self, tagData):
			pass

		return locals()


class s15Fixed16ArrayType(ICCProfileTag, list):

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if tagData:
			data = tagData[8:]
			while data:
				self.append(s15Fixed16Number(data[0:4]))
				data = data[4:]
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["sf32", "\0" * 4]
			for value in self:
				tagData.append(s15Fixed16Number_tohex(value))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


def SignatureType(tagData, tagSignature):
	tag = Text(tagData[8:12].rstrip("\0"))
	tag.tagData = tagData
	tag.tagSignature = tagSignature
	return tag


class TextDescriptionType(ICCProfileTag, ADict): # ICC v2

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.ASCII = ""
		if not tagData:
			return
		ASCIIDescriptionLength = uInt32Number(tagData[8:12])
		if ASCIIDescriptionLength:
			ASCIIDescription = tagData[12:12 + 
									   ASCIIDescriptionLength].strip("\0\n\r ")
			if ASCIIDescription:
				self.ASCII = ASCIIDescription
		unicodeOffset = 12 + ASCIIDescriptionLength
		self.unicodeLanguageCode = uInt32Number(
									tagData[unicodeOffset:unicodeOffset + 4])
		unicodeDescriptionLength = uInt32Number(tagData[unicodeOffset + 
														4:unicodeOffset + 8])
		if unicodeDescriptionLength:
			if unicodeOffset + 8 + unicodeDescriptionLength * 2 > len(tagData):
				# Damn you MS. The Unicode character count should be the number of 
				# double-byte characters (including trailing unicode NUL), not the
				# number of bytes as in the profiles created by Vista and later
				safe_print("Warning (non-critical): '%s' Unicode part end points "
						   "past the tag data, assuming number of bytes instead "
						   "of number of characters for length" % tagData[:4])
				unicodeDescriptionLength /= 2
			if tagData[unicodeOffset + 8 + 
					   unicodeDescriptionLength:unicodeOffset + 8 + 
					   unicodeDescriptionLength + 2] == "\0\0":
				safe_print("Warning (non-critical): '%s' Unicode part "
						   "seems to be a single-byte string (double-byte "
						   "string expected)" % tagData[:4])
				charBytes = 1 # fix for fubar'd desc
			else:
				charBytes = 2
			unicodeDescription = tagData[unicodeOffset + 8:unicodeOffset + 8 + 
										 (unicodeDescriptionLength) * charBytes]
			try:
				if charBytes == 1:
					unicodeDescription = unicode(unicodeDescription, 
												 errors="replace")
				else:
					if unicodeDescription[:2] == "\xfe\xff":
						# UTF-16 Big Endian
						if debug: safe_print("UTF-16 Big endian")
						unicodeDescription = unicodeDescription[2:]
						if len(unicodeDescription.split(" ")) == \
						   unicodeDescriptionLength - 1:
							safe_print("Warning (non-critical): '%s' "
									   "Unicode part starts with UTF-16 big "
									   "endian BOM, but actual contents seem "
									   "to be UTF-16 little endian" % 
									   tagData[:4])
							# fix fubar'd desc
							unicodeDescription = unicode(
								"\0".join(unicodeDescription.split(" ")), 
								"utf-16-le", errors="replace")
						else:
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-be", 
														 errors="replace")
					elif unicodeDescription[:2] == "\xff\xfe":
						# UTF-16 Little Endian
						if debug: safe_print("UTF-16 Little endian")
						unicodeDescription = unicodeDescription[2:]
						if unicodeDescription[0] == "\0":
							safe_print("Warning (non-critical): '%s' "
									   "Unicode part starts with UTF-16 "
									   "little endian BOM, but actual "
									   "contents seem to be UTF-16 big "
									   "endian" % tagData[:4])
							# fix fubar'd desc
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-be", 
														 errors="replace")
						else:
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-le", 
														 errors="replace")
					else:
						if debug: safe_print("ASSUMED UTF-16 Big Endian")
						unicodeDescription = unicode(unicodeDescription, 
													 "utf-16-be", 
													 errors="replace")
				unicodeDescription = unicodeDescription.strip("\0\n\r ")
				if unicodeDescription:
					if unicodeDescription.find("\0") < 0:
						self.Unicode = unicodeDescription
					else:
						safe_print("Error (non-critical): could not decode "
								   "'%s' Unicode part - null byte(s) "
								   "encountered" % tagData[:4])
			except UnicodeDecodeError:
				safe_print("UnicodeDecodeError (non-critical): could not "
						   "decode '%s' Unicode part" % tagData[:4])
		else:
			charBytes = 1
		macOffset = unicodeOffset + 8 + unicodeDescriptionLength * charBytes
		self.macScriptCode = 0
		if len(tagData) > macOffset + 2:
			self.macScriptCode = uInt16Number(tagData[macOffset:macOffset + 2])
			macDescriptionLength = ord(tagData[macOffset + 2])
			if macDescriptionLength:
				try:
					macDescription = unicode(tagData[macOffset + 3:macOffset + 
											 3 + macDescriptionLength], 
											 "mac-" + 
											 encodings["mac"][self.macScriptCode], 
											 errors="replace").strip("\0\n\r ")
					if macDescription:
						self.Macintosh = macDescription
				except KeyError:
					safe_print("KeyError (non-critical): could not "
							   "decode '%s' Macintosh part (unsupported "
							   "encoding %s)" % (tagData[:4],
												 self.macScriptCode))
				except LookupError:
					safe_print("LookupError (non-critical): could not "
							   "decode '%s' Macintosh part (unsupported "
							   "encoding '%s')" %
							   (tagData[:4],
							    encodings["mac"][self.macScriptCode]))
				except UnicodeDecodeError:
					safe_print("UnicodeDecodeError (non-critical): could not "
							   "decode '%s' Macintosh part" % tagData[:4])
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["desc", "\0" * 4,
					   uInt32Number_tohex(len(self.ASCII) + 1),  # count of ASCII chars + 1
					   safe_unicode(self.ASCII).encode("ASCII", "replace") + "\0",  # ASCII desc, \0 terminated
					   uInt32Number_tohex(self.get("unicodeLanguageCode", 0))]
			if "Unicode" in self:
				tagData.extend([uInt32Number_tohex(len(self.Unicode) + 2),  # count of Unicode chars + 2 (UTF-16-BE BOM + trailing UTF-16 NUL, 1 char = 2 byte)
								"\xfe\xff" + self.Unicode.encode("utf-16-be", "replace") + 
								"\0\0"])  # Unicode desc, \0\0 terminated
			else:
				tagData.append(uInt32Number_tohex(0))  # Unicode desc length = 0
			tagData.append(uInt16Number_tohex(self.get("macScriptCode", 0)))
			if "Macintosh" in self:
				macDescription = self.Macintosh[:66]
				tagData.extend([uInt8Number_tohex(len(macDescription) + 1),  # count of Macintosh chars + 1
								macDescription.encode("mac-" + 
													  encodings["mac"][self.get("macScriptCode", 0)], 
													  "replace") + ("\0" * (67 - len(macDescription)))])
			else:
				tagData.extend(["\0",  # Mac desc length = 0
								"\0" * 67])
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()

	def __str__(self):
		return unicode(self).encode(sys.getdefaultencoding())

	def __unicode__(self):
		if not "Unicode" in self and len(safe_unicode(self.ASCII)) < 67:
			# Do not use Macintosh description if ASCII length >= 67
			localizedTypes = ("Macintosh", "ASCII")
		else:
			localizedTypes = ("Unicode", "ASCII")
		for localizedType in localizedTypes:
			if localizedType in self:
				value = self[localizedType]
				if not isinstance(value, unicode):
					# Even ASCII description may contain non-ASCII chars, so 
					# assume system encoding and convert to unicode, replacing 
					# unknown chars
					value = safe_unicode(value)
				return value


def TextType(tagData, tagSignature):
	tag = Text(tagData[8:].rstrip("\0"))
	tag.tagData = tagData
	tag.tagSignature = tagSignature
	return tag


class VideoCardGammaType(ICCProfileTag, ADict):

	# Private tag
	# http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
	
	def is_linear(self, r=True, g=True, b=True):
		r_points, g_points, b_points, linear_points = self.get_values()
		if ((r and g and b and r_points == g_points == b_points) or
			(r and g and r_points == g_points) or not (g or b)):
			points = r_points
		elif ((r and b and r_points == b_points) or
			  (g and b and g_points == b_points) or not (r or g)):
			points = b_points
		elif g:
			points = g_points
		return points == linear_points
	
	def get_unique_values(self, r=True, g=True, b=True):
		r_points, g_points, b_points, linear_points = self.get_values()
		r_unique = set(round(y) for x, y in r_points)
		g_unique = set(round(y) for x, y in g_points)
		b_unique = set(round(y) for x, y in b_points)
		return r_unique, g_unique, b_unique
	
	def get_values(self, r=True, g=True, b=True):
		r_points = []
		g_points = []
		b_points = []
		linear_points = []
		vcgt = self
		if "data" in vcgt: # table
			data = list(vcgt['data'])
			while len(data) < 3:
				data.append(data[0])
			irange = range(0, vcgt['entryCount'])
			vmax = math.pow(256, vcgt['entrySize']) - 1
			for i in irange:
				j = i * (255.0 / (vcgt['entryCount'] - 1))
				linear_points.append([j, int(round(i / float(vcgt['entryCount'] - 1) * 65535))])
				if r:
					n = int(round(float(data[0][i]) / vmax * 65535))
					r_points.append([j, n])
				if g:
					n = int(round(float(data[1][i]) / vmax * 65535))
					g_points.append([j, n])
				if b:
					n = int(round(float(data[2][i]) / vmax * 65535))
					b_points.append([j, n])
		else: # formula
			irange = range(0, 256)
			step = 100.0 / 255.0
			for i in irange:
				linear_points.append([i, i / 255.0 * 65535])
				if r:
					vmin = vcgt["redMin"] * 65535
					v = math.pow(step * i / 100.0, vcgt["redGamma"])
					vmax = vcgt["redMax"] * 65535
					r_points.append([i, int(round(vmin + v * (vmax - vmin)))])
				if g:
					vmin = vcgt["greenMin"] * 65535
					v = math.pow(step * i / 100.0, vcgt["greenGamma"])
					vmax = vcgt["greenMax"] * 65535
					g_points.append([i, int(round(vmin + v * (vmax - vmin)))])
				if b:
					vmin = vcgt["blueMin"] * 65535
					v = math.pow(step * i / 100.0, vcgt["blueGamma"])
					vmax = vcgt["blueMax"] * 65535
					b_points.append([i, int(round(vmin + v * (vmax - vmin)))])
		return r_points, g_points, b_points, linear_points

	def printNormalizedValues(self, amount=None, digits=12):
		"""
		Normalizes and prints all values in the vcgt (range of 0.0...1.0).
		
		For a 256-entry table with linear values from 0 to 65535:
		#   REF            C1             C2             C3
		001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
		002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
		003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
		...
		You can also specify the amount of values to print (where a value 
		lesser than the entry count will leave out intermediate values) 
		and the number of digits.
		
		"""
		if amount is None:
			if hasattr(self, 'entryCount'):
				amount = self.entryCount
			else:
				amount = 256  # common value
		values = self.getNormalizedValues(amount)
		entryCount = len(values)
		channels = len(values[0])
		header = ['REF']
		for k in xrange(channels):
			header.append('C' + str(k + 1))
		header = [title.ljust(digits + 2) for title in header]
		safe_print("#".ljust(len(str(amount)) + 1) + " ".join(header))
		for i, value in enumerate(values):
			formatted_values = [str(round(channel, 
								digits)).ljust(digits + 2, '0') for 
					  channel in value]
			safe_print(str(i + 1).rjust(len(str(amount)), '0'), 
					   str(round(i / float(entryCount - 1), 
								 digits)).ljust(digits + 2, '0'), 
					   " ".join(formatted_values))


class VideoCardGammaFormulaType(VideoCardGammaType):

	def __init__(self, tagData, tagSignature):
		VideoCardGammaType.__init__(self, tagData, tagSignature)
		data = tagData[12:]
		self.update({
			"redGamma": u16Fixed16Number(data[0:4]),
			"redMin": u16Fixed16Number(data[4:8]),
			"redMax": u16Fixed16Number(data[8:12]),
			"greenGamma": u16Fixed16Number(data[12:16]),
			"greenMin": u16Fixed16Number(data[16:20]),
			"greenMax": u16Fixed16Number(data[20:24]),
			"blueGamma": u16Fixed16Number(data[24:28]),
			"blueMin": u16Fixed16Number(data[28:32]),
			"blueMax": u16Fixed16Number(data[32:36])
		})
	
	def getNormalizedValues(self, amount=None):
		if amount is None:
			amount = 256  # common value
		step = 1.0 / float(amount - 1)
		rgb = AODict([("red", []), ("green", []), ("blue", [])])
		for i in xrange(0, amount):
			for key in rgb:
				rgb[key].append(float(self[key + "Min"]) +
								math.pow(step * i / 1.0,
										 float(self[key + "Gamma"])) * 
								float(self[key + "Max"] - self[key + "Min"]))
		return zip(*rgb.values())
	
	def getTableType(self, entryCount=256, entrySize=2, quantizer=round):
		"""
		Return gamma as table type.
		"""
		maxValue = math.pow(256, entrySize) - 1
		tagData = [self.tagData[:8], 
				   uInt32Number_tohex(0),  # type 0 = table
				   uInt16Number_tohex(3),  # channels
				   uInt16Number_tohex(entryCount),
				   uInt16Number_tohex(entrySize)]
		int2hex = {
			1: uInt8Number_tohex,
			2: uInt16Number_tohex,
			4: uInt32Number_tohex,
			8: uInt64Number_tohex
		}
		for key in ("red", "green", "blue"):
			for i in xrange(0, entryCount):
				vmin = float(self[key + "Min"])
				vmax = float(self[key + "Max"])
				gamma = float(self[key + "Gamma"])
				v = (vmin + 
					 math.pow(1.0 / (entryCount - 1) * i, gamma) * 
					 float(vmax - vmin))
				tagData.append(int2hex[entrySize](quantizer(v * maxValue)))
		return VideoCardGammaTableType("".join(tagData), self.tagSignature)


class VideoCardGammaTableType(VideoCardGammaType):

	def __init__(self, tagData, tagSignature):
		VideoCardGammaType.__init__(self, tagData, tagSignature)
		if not tagData:
			self.update({"channels": 0,
						 "entryCount": 0,
						 "entrySize": 0,
						 "data": []})
			return
		data = tagData[12:]
		channels   = uInt16Number(data[0:2])
		entryCount = uInt16Number(data[2:4])
		entrySize  = uInt16Number(data[4:6])
		self.update({
			"channels": channels,
			"entryCount": entryCount,
			"entrySize": entrySize,
			"data": []
		})
		hex2int = {
			1: uInt8Number,
			2: uInt16Number,
			4: uInt32Number,
			8: uInt64Number
		}
		if entrySize not in hex2int:
			raise ValueError("Invalid VideoCardGammaTableType entry size %i" %
							 entrySize)
		i = 0
		while i < channels:
			self.data.append([])
			j = 0
			while j < entryCount:
				index = 6 + i * entryCount * entrySize + j * entrySize
				self.data[i].append(hex2int[entrySize](data[index:index + 
															entrySize]))
				j = j + 1
			i = i + 1
	
	def getNormalizedValues(self, amount=None):
		if amount is None:
			amount = self.entryCount
		maxValue = math.pow(256, self.entrySize) - 1
		values = zip(*[[entry / maxValue for entry in channel] for channel in self.data])
		if amount <= self.entryCount:
			step = self.entryCount / float(amount - 1)
			all = values
			values = []
			for i, value in enumerate(all):
				if i == 0 or (i + 1) % step < 1 or i + 1 == self.entryCount:
					values.append(value)
		return values
	
	def getFormulaType(self):
		"""
		Return formula representing gamma value at 50% input.
		"""
		maxValue = math.pow(256, self.entrySize) - 1
		tagData = [self.tagData[:8], 
				   uInt32Number_tohex(1)]  # type 1 = formula
		data = list(self.data)
		while len(data) < 3:
			data.append(data[0])
		for channel in data:
			l = (len(channel) - 1) / 2.0
			floor = float(channel[int(math.floor(l))])
			ceil = float(channel[int(math.ceil(l))])
			vmin = channel[0] / maxValue
			vmax = channel[-1] / maxValue
			v = (vmin + ((floor + ceil) / 2.0) * (vmax - vmin)) / maxValue
			gamma = (math.log(v) / math.log(.5))
			print vmin, gamma, vmax
			tagData.append(u16Fixed16Number_tohex(gamma))
			tagData.append(u16Fixed16Number_tohex(vmin))
			tagData.append(u16Fixed16Number_tohex(vmax))
		return VideoCardGammaFormulaType("".join(tagData), self.tagSignature)

	def quantize(self, bits=16, quantizer=round):
		"""
		Quantize to n bits of precision.
		
		Note that when the quantize bits are not 8, 16, 32 or 64, double
		quantization will occur: First from the table precision bits according
		to entrySize to the chosen quantization bits, and then back to the
		table precision bits.
		
		"""
		oldmax = math.pow(256, self.entrySize) - 1
		if bits in (8, 16, 32, 64):
			self.entrySize = bits / 8
		bitv = 2.0 ** bits
		newmax = math.pow(256, self.entrySize) - 1
		for i, channel in enumerate(self.data):
			for j, value in enumerate(channel):
				channel[j] = int(quantizer(value / oldmax * bitv) / bitv * newmax)
	
	def resize(self, length=128):
		data = [[], [], []]
		for i, channel in enumerate(self.data):
			for j in xrange(0, length):
				j *= (len(channel) - 1) / float(length - 1)
				if int(j) != j:
					floor = channel[int(math.floor(j))]
					ceil = channel[min(int(math.ceil(j)), len(channel) - 1)]
					interpolated = xrange(floor, ceil + 1)
					fraction = j - int(j)
					index = int(round(fraction * (ceil - floor)))
					v = interpolated[index]
				else:
					v = channel[int(j)]
				data[i].append(v)
		self.data = data
		self.entryCount = len(data[0])
	
	def resized(self, length=128):
		resized = self.__class__(self.tagData, self.tagSignature)
		resized.resize(length)
		return resized
	
	def smooth_cr(self, length=64):
		"""
		Smooth video LUT curves (Catmull-Rom).
		"""
		resized = self.resized(length)
		for i in xrange(0, len(self.data)):
			step = float(length - 1) / (len(self.data[i]) - 1)
			interpolation = CRInterpolation(resized.data[i])
			for j in xrange(0, len(self.data[i])):
				self.data[i][j] = interpolation(j * step)
	
	def smooth_avg(self, passes=1, window=None):
		"""
		Smooth video LUT curves (moving average).
		
		passses   Number of passes
		window    Tuple or list containing weighting factors. Its length
		          determines the size of the window to use.
		          Defaults to (1.0, 1.0, 1.0)
		
		"""
		for i, channel in enumerate(self.data):
			self.data[i] = colormath.smooth_avg(channel, passes, window)
		self.entryCount = len(self.data[0])
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["vcgt", "\0" * 4,
					   uInt32Number_tohex(0),  # type 0 = table
					   uInt16Number_tohex(len(self.data)),  # channels
					   uInt16Number_tohex(self.entryCount),
					   uInt16Number_tohex(self.entrySize)]
			int2hex = {
				1: uInt8Number_tohex,
				2: uInt16Number_tohex,
				4: uInt32Number_tohex,
				8: uInt64Number_tohex
			}
			for channel in self.data:
				for i in xrange(0, self.entryCount):
					tagData.append(int2hex[self.entrySize](channel[i]))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class ViewingConditionsType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.update({
			"illuminant": XYZNumber(tagData[8:20]),
			"surround": XYZNumber(tagData[20:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class TagData(object):

	def __init__(self, tagData, offset, size):
		self.tagData = tagData
		self.offset = offset
		self.size = size

	def __contains__(self, item):
		return item in str(self)

	def __str__(self):
		return self.tagData[self.offset:self.offset + self.size]


class WcsProfilesTagType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature, profile):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.profile = profile
		for i, modelname in enumerate(["ColorDeviceModel",
									   "ColorAppearanceModel", "GamutMapModel"]):
			j = i * 8
			offset = uInt32Number(tagData[8 + j:12 + j])
			size = uInt32Number(tagData[12 + j:16 + j])
			if offset and size:
				from StringIO import StringIO
				from xml.etree import ElementTree
				it = ElementTree.iterparse(StringIO(tagData[offset:offset + size]))
				for event, elem in it:
					elem.tag = elem.tag.split('}', 1)[-1]  # Strip all namespaces
				self[modelname] = it.root

	def get_vcgt(self, quantize=False, quantizer=round):
		"""
		Return calibration information (if present) as VideoCardGammaType
		
		If quantize is set, a table quantized to <quantize> bits is returned.
		
		Note that when the quantize bits are not 8, 16, 32 or 64, multiple
		quantizations will occur: For quantization bits below 32, first to 32
		bits, then to the chosen quantization bits, then back to 32 bits (which
		will be the final table precision bits).

		"""
		if quantize and not isinstance(quantize, int):
			raise ValueError("Invalid quantization bits: %r" % quantize)
		if "ColorDeviceModel" in self:
			# Parse calibration information to VCGT
			cal = self.ColorDeviceModel.find("Calibration")
			if cal is None:
				return
			agammaconf = cal.find("AdapterGammaConfiguration")
			if agammaconf is None:
				return
			pcurves = agammaconf.find("ParameterizedCurves")
			if pcurves is None:
				return
			vcgtData = "vcgt"
			vcgtData += "\0" * 4
			vcgtData += uInt32Number_tohex(1)  # Type 1 = formula
			for color in ("Red", "Green", "Blue"):
				trc = pcurves.find(color + "TRC")
				if trc is None:
					trc = {}
				vcgtData += u16Fixed16Number_tohex(float(trc.get("Gamma", 1)))
				vcgtData += u16Fixed16Number_tohex(float(trc.get("Offset1", 0)))
				vcgtData += u16Fixed16Number_tohex(float(trc.get("Gain", 1)))
			vcgt = VideoCardGammaFormulaType(vcgtData, "vcgt")
			if quantize:
				if quantize in (8, 16, 32, 64):
					entrySize = quantize / 8
				elif quantize < 32:
					entrySize = 4
				else:
					entrySize = 8
				vcgt = vcgt.getTableType(entrySize=entrySize,
										 quantizer=quantizer)
				if quantize not in (8, 16, 32, 64):
					vcgt.quantize(quantize, quantizer)
			return vcgt


class XYZNumber(AODict):

	"""
	Byte
	Offset Content Encoded as...
	0..3   CIE X   s15Fixed16Number
	4..7   CIE Y   s15Fixed16Number
	8..11  CIE Z   s15Fixed16Number
	"""

	def __init__(self, binaryString="\0" * 12):
		AODict.__init__(self)
		self.X, self.Y, self.Z = [s15Fixed16Number(chunk) for chunk in 
								  (binaryString[:4], binaryString[4:8], 
								   binaryString[8:12])]
	
	def __repr__(self):
		XYZ = []
		for key, value in self.iteritems():
			XYZ.append("(%s, %s)" % (repr(key), str(value)))
		return "%s.%s([%s])" % (self.__class__.__module__,
								self.__class__.__name__,
								", ".join(XYZ))
	
	def adapt(self, whitepoint_source=None, whitepoint_destination=None, cat="Bradford"):
		XYZ = self.__class__()
		XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(self.X, self.Y, self.Z,
											  whitepoint_source,
											  whitepoint_destination, cat)
		return XYZ
	
	def round(self, digits=4):
		XYZ = self.__class__()
		for key in self:
			XYZ[key] = round(self[key], digits)
		return XYZ
	
	def tohex(self):
		data = [s15Fixed16Number_tohex(n) for n in self.values()]
		return "".join(data)
	
	@property
	def hex(self):
		return self.tohex()
	
	@property
	def Lab(self):
		return colormath.XYZ2Lab(*[v * 100 for v in self.values()])
	
	@property
	def xyY(self):
		return NumberTuple(colormath.XYZ2xyY(self.X, self.Y, self.Z))


class XYZType(ICCProfileTag, XYZNumber):

	def __init__(self, tagData="\0" * 20, tagSignature=None, profile=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		XYZNumber.__init__(self, tagData[8:20])
		self.profile = profile
	
	__repr__ = XYZNumber.__repr__

	def __setattr__(self, name, value):
		if name in ("_keys", "profile", "tagData", "tagSignature"):
			object.__setattr__(self, name, value)
		else:
			self[name] = value
	
	def adapt(self, whitepoint_source=None, whitepoint_destination=None,
			  cat=None):
		if self.profile and isinstance(self.profile.tags.get("arts"),
									   chromaticAdaptionTag):
			cat = self.profile.tags.arts
		else:
			cat = "Bradford"
		XYZ = self.__class__(profile=self.profile)
		XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(self.X, self.Y, self.Z,
											  whitepoint_source,
											  whitepoint_destination, cat)
		return XYZ
	
	@property
	def ir(self):
		""" Get illuminant-relative values """
		pcs_illuminant = self.profile.illuminant.values()
		if "chad" in self.profile.tags and self.profile.creator != "appl":
			# Apple profiles have a bug where they contain a 'chad' tag, 
			# but the media white is not under PCS illuminant
			if self is self.profile.tags.wtpt:
				XYZ = self.__class__(profile=self.profile)
				XYZ.X, XYZ.Y, XYZ.Z = self.values()
			else:
				# Go from XYZ mediawhite-relative under PCS illuminant to XYZ
				# under PCS illuminant
				if isinstance(self.profile.tags.get("arts"),
							  chromaticAdaptionTag):
					cat = self.profile.tags.arts
				else:
					cat = "XYZ scaling"
				XYZ = self.adapt(pcs_illuminant, self.profile.tags.wtpt.values(),
								 cat=cat)
			# Go from XYZ under PCS illuminant to XYZ illuminant-relative
			XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * XYZ.values()
			return XYZ
		else:
			if self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")):
				# For profiles without 'chad' tag, the white/black point should
				# already be illuminant-relative
				return self
			elif "chad" in self.profile.tags:
				XYZ = self.__class__(profile=self.profile)
				# Go from XYZ under PCS illuminant to XYZ illuminant-relative
				XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * self.values()
				return XYZ
			else:
				# Go from XYZ under PCS illuminant to XYZ illuminant-relative
				return self.adapt(pcs_illuminant, self.profile.tags.wtpt.values())
	
	@property
	def pcs(self):
		""" Get PCS-relative values """
		if (self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")) and
			(not "chad" in self.profile.tags or self.profile.creator == "appl")):
			# Apple profiles have a bug where they contain a 'chad' tag, 
			# but the media white is not under PCS illuminant
			if "chad" in self.profile.tags:
				XYZ = self.__class__(profile=self.profile)
				XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad * self.values()
				return XYZ
			pcs_illuminant = self.profile.illuminant.values()
			return self.adapt(self.profile.tags.wtpt.values(), pcs_illuminant)
		else:
			# Values should already be under PCS illuminant
			return self
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["XYZ ", "\0" * 4]
			tagData.append(self.tohex())
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()
	
	@property
	def xyY(self):
		if self is self.profile.tags.get("bkpt"):
			ref = self.profile.tags.bkpt
		else:
			ref = self.profile.tags.wtpt
		return NumberTuple(colormath.XYZ2xyY(self.X, self.Y, self.Z,
											 (ref.X, 1.0, ref.Z)))


class chromaticAdaptionTag(colormath.Matrix3x3, s15Fixed16ArrayType):
	
	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if tagData:
			data = tagData[8:]
			if data:
				matrix = []
				while data:
					if len(matrix) == 0 or len(matrix[-1]) == 3:
						matrix.append([])
					matrix[-1].append(s15Fixed16Number(data[0:4]))
					data = data[4:]
				self.update(matrix)
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["sf32", "\0" * 4]
			for row in self:
				for column in row:
					tagData.append(s15Fixed16Number_tohex(column))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()
	
	def get_cat(self):
		""" Compare to known CAT matrices and return matching name (if any) """
		for cat_name, cat_matrix in colormath.cat_matrices.iteritems():
			if colormath.is_similar_matrix(self, cat_matrix, 4):
				return cat_name


class NamedColor2Value(object):

	def __init__(self, valueData="\0" * 38, deviceCoordCount=0, pcs="XYZ",
				 device="RGB"):
		self._pcsname = pcs
		self._devicename = device
		end = valueData[0:32].find("\0")
		if end < 0:
			end = 32
		self.rootName = valueData[0:end]
		self.pcsvalues = [
			uInt16Number(valueData[32:34]),
			uInt16Number(valueData[34:36]),
			uInt16Number(valueData[36:38])]
		
		self.pcs = AODict()
		for i, pcsvalue in enumerate(self.pcsvalues):
			if pcs == "Lab":
				if i == 0:
					# L* range 0..100 + (25500 / 65280.0)
					self.pcs[pcs[i]] = pcsvalue / 65536.0 * 256 / 255.0 * 100
				else:
					# a, b range -128..127 + (255/256.0)
					self.pcs[pcs[i]] = -128 + (pcsvalue / 65536.0 * 256)
			elif pcs == "XYZ":
				# X, Y, Z range 0..100 + (32767 / 32768.0)
				self.pcs[pcs[i]] = pcsvalue / 32768.0 * 100
		
		deviceCoords = []
		if deviceCoordCount > 0:
			for i in xrange(38, 38+deviceCoordCount*2, 2):
				deviceCoords.append(
					uInt16Number(
						valueData[i:i+2]))
		self.devicevalues = deviceCoords
		if device == "Lab":
			# L* range 0..100 + (25500 / 65280.0)
			# a, b range range -128..127 + (255 / 256.0)
			self.device = tuple(v / 65536.0 * 256 / 255.0 * 100 if i == 0
								else -128 + (v / 65536.0 * 256)
								for i, v in enumerate(deviceCoords))
		elif device == "XYZ":
			# X, Y, Z range 0..100 + (32767 / 32768.0)
			self.device = tuple(v / 32768.0 * 100 for v in deviceCoords)
		else:
			# Device range 0..100
			self.device = tuple(v / 65535.0 * 100 for v in deviceCoords)
	
	@property
	def name(self):
		return unicode(Text(self.rootName.strip('\0')), 'latin-1')
	
	def __repr__(self):
		pcs = []
		dev = []
		for key, value in self.pcs.iteritems():
			pcs.append("%s=%s" % (str(key), str(value)))
		for value in self.device:
			dev.append("%s" % value)
		return "%s(%s, {%s}, [%s])" % (
								self.__class__.__name__,
								self.name,
								", ".join(pcs),
								", ".join(dev))
	
	@Property
	def tagData():
		doc = """ Return raw tag data. """
		
		def fget(self):
			valueData = []
			valueData.append(self.rootName.ljust(32, "\0"))
			valueData.extend(
				[uInt16Number_tohex(pcsval) for pcsval in self.pcsvalues])
			valueData.extend(
				[uInt16Number_tohex(deviceval) for deviceval in self.devicevalues])
			return "".join(valueData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class NamedColor2ValueTuple(tuple):
	
	__slots__ = ()
	REPR_OUTPUT_SIZE = 10
	
	def __repr__(self):
		data = list(self[:self.REPR_OUTPUT_SIZE + 1])
		if len(data) > self.REPR_OUTPUT_SIZE:
			data[-1] = "...(remaining elements truncated)..."
		return repr(data)
	
	@Property
	def tagData():
		doc = """ Return raw tag data. """
		
		def fget(self):
			return "".join([val.tagData for val in self])
		
		def fset(self, tagData):
			pass
		
		return locals()


class NamedColor2Type(ICCProfileTag, AODict):
	
	REPR_OUTPUT_SIZE = 10
	
	def __init__(self, tagData="\0" * 84, tagSignature=None, pcs=None,
				 device=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		
		colorCount = uInt32Number(tagData[12:16])
		deviceCoordCount = uInt32Number(tagData[16:20])
		stride = 38 + 2*deviceCoordCount
		
		self.vendorData = tagData[8:12]
		self.colorCount = colorCount
		self.deviceCoordCount = deviceCoordCount
		self._prefix = Text(tagData[20:52])
		self._suffix = Text(tagData[52:84])
		self._pcsname = pcs
		self._devicename = device
		
		keys = []
		values = []
		if colorCount > 0:
			start = 84
			end = start + (stride*colorCount)
			for i in xrange(start, end, stride):
				nc2 = NamedColor2Value(
					tagData[i:i+stride],
					deviceCoordCount, pcs=pcs, device=device)
				keys.append(nc2.name)
				values.append(nc2)
		self.update(OrderedDict(zip(keys, values)))
	
	def __setattr__(self, name, value):
		object.__setattr__(self, name, value)
	
	@property
	def prefix(self):
		return unicode(self._prefix.strip('\0'), 'latin-1')
	
	@property
	def suffix(self):
		return unicode(self._suffix.strip('\0'), 'latin-1')
	
	@property
	def colorValues(self):
		return NamedColor2ValueTuple(self.values())
	
	def add_color(self, rootName, *deviceCoordinates, **pcsCoordinates):
		if self._pcsname == "Lab":
			keys = ["L", "a", "b"]
		elif self._pcsname == "XYZ":
			keys = ["X", "Y", "Z"]
		else:
			keys = ["X", "Y", "Z"]
		
		if not set(pcsCoordinates.keys()).issuperset(set(keys)):
			raise ICCProfileInvalidError("Can't add namedColor2 without all 3 PCS coordinates: '%s'" %
				set(keys) - set(pcsCoordinates.keys()))
		
		if len(deviceCoordinates) != self.deviceCoordCount:
			raise ICCProfileInvalidError("Can't add namedColor2 without all %s device coordinates (called with %s)" % (
				self.deviceCoordCount, len(deviceCoordinates)))
		
		nc2value = NamedColor2Value()
		nc2value._pcsname = self._pcsname
		nc2value._devicename = self._devicename
		nc2value.rootName = rootName
		
		if rootName in self.keys():
			raise ICCProfileInvalidError("Can't add namedColor2 with existant name: '%s'" % rootName)
		
		nc2value.devicevalues = []
		nc2value.device = tuple(deviceCoordinates)
		nc2value.pcs = AODict(copy(pcsCoordinates))
		
		for idx, key in enumerate(keys):
			val = nc2value.pcs[key]
			if key == "L":
				nc2value.pcsvalues[idx] = val * 65536 / (256 / 255.0) / 100.0
			elif key in ("a", "b"):
				nc2value.pcsvalues[idx] = (val + 128) * 65536 / 256.0
			elif key in ("X", "Y", "Z"):
				nc2value.pcsvalues[idx] = val * 32768 / 100.0
		
		for idx, val in enumerate(nc2value.device):
			if self._devicename == "Lab":
				if idx == 0:
					# L* range 0..100 + (25500 / 65280.0)
					nc2value.devicevalues[idx] = val * 65536 / (256 / 255.0) / 100.0
				else:
					# a, b range -128..127 + (255/256.0)
					nc2value.devicevalues[idx] = (val + 128) * 65536 / 256.0
			elif self._devicename == "XYZ":
				# X, Y. Z range 0..100 + (32767 / 32768.0)
				nc2value.devicevalues[idx] = val * 32768 / 100.0
			else:
				# Device range 0..100
				nc2value.devicevalues[idx] = val * 65535 / 100.0
		
		self[nc2value.name] = nc2value
	
	def __repr__(self):
		data = self.items()[:self.REPR_OUTPUT_SIZE + 1]
		if len(data) > self.REPR_OUTPUT_SIZE:
			data[-1] = ('...', "(remaining elements truncated)")
		return repr(OrderedDict(data))
	
	@Property
	def tagData():
		doc = """ Return raw tag data. """
		
		def fget(self):
			tagData = ["ncl2", "\0" * 4,
				self.vendorData,
				uInt32Number_tohex(len(self.items())),
				uInt32Number_tohex(self.deviceCoordCount),
				self._prefix.ljust(32), self._suffix.ljust(32)]
			tagData.append(self.colorValues.tagData)
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()



tagSignature2Tag = {
	"arts": chromaticAdaptionTag,
	"chad": chromaticAdaptionTag
}

typeSignature2Type = {
	"chrm": ChromaticityType,
	"clrt": ColorantTableType,
	"curv": CurveType,
	"desc": TextDescriptionType,  # ICC v2
	"dict": DictType,  # ICC v2 + v4
	"dtim": DateTimeType,
	"meas": MeasurementType,
	"mluc": MultiLocalizedUnicodeType,  # ICC v4
	"mft2": LUT16Type,
	"mmod": MakeAndModelType,  # Apple private tag
	"ncl2": NamedColor2Type,
	"sf32": s15Fixed16ArrayType,
	"sig ": SignatureType,
	"text": TextType,
	"vcgt": videoCardGamma,
	"view": ViewingConditionsType,
	"MS10": WcsProfilesTagType,
	"XYZ ": XYZType
}


class ICCProfileInvalidError(IOError):
	pass


class ICCProfile:

	"""
	Returns a new ICCProfile object. 
	
	Optionally initialized with a string containing binary profile data or 
	a filename, or a file-like object. Also if the 'load' keyword argument
	is False (default True), only the header will be read initially and
	loading of the tags will be deferred to when they are accessed the
	first time.
	
	"""

	def __init__(self, profile=None, load=True):
		self.ID = "\0" * 16
		self._data = ""
		self._file = None
		self._tags = LazyLoadTagAODict(self)
		self.fileName = None
		self.is_loaded = False
		self.size = 0
		
		if profile is not None:
		
			data = None
			
			if type(profile) in (str, unicode):
				if profile.find("\0") < 0:
					# filename
					if (not os.path.isfile(profile) and
						not os.path.sep in profile and
						(not isinstance(os.path.altsep, basestring) or
						 not os.path.altsep in profile)):
						for path in iccprofiles_home + filter(lambda x: 
							x not in iccprofiles_home, iccprofiles):
							if os.path.isdir(path):
								for path, dirs, files in os.walk(path):
									path = os.path.join(path, profile)
									if os.path.isfile(path):
										profile = path
										break
								if os.path.isfile(path):
									break
					profile = open(profile, "rb")
				else: # binary string
					data = profile
					self.is_loaded = True
			if not data: # file object
				self._file = profile
				self.fileName = self._file.name
				self._file.seek(0)
				data = self._file.read(128)
				self.close()
			
			if not data or len(data) < 128:
				raise ICCProfileInvalidError("Not enough data")
			
			if data[36:40] != "acsp":
				raise ICCProfileInvalidError("Profile signature mismatch - "
											 "expected 'acsp', found '" + 
											 data[36:40] + "'")
			
			header = data[:128]
			self.size = uInt32Number(header[0:4])
			self.preferredCMM = header[4:8]
			minorrev_bugfixrev = binascii.hexlify(header[8:12][1])
			self.version = float(str(ord(header[8:12][0])) + "." + 
								 str(int("0x0" + minorrev_bugfixrev[0], 16)) + 
								 str(int("0x0" + minorrev_bugfixrev[1], 16)))
			self.profileClass = header[12:16]
			self.colorSpace = header[16:20].strip()
			self.connectionColorSpace = header[20:24].strip()
			try:
				self.dateTime = dateTimeNumber(header[24:36])
			except ValueError:
				raise ICCProfileInvalidError("Profile creation date/time invalid")
			self.platform = header[40:44]
			flags = uInt32Number(header[44:48])
			self.embedded = flags & 1 != 0
			self.independent = flags & 2 == 0
			deviceAttributes = uInt64Number(header[56:64])
			self.device = {
				"manufacturer": header[48:52],
				"model": header[52:56],
				"attributes": {
					"reflective":   deviceAttributes & 1 == 0,
					"glossy":       deviceAttributes & 2 == 0,
					"positive":     deviceAttributes & 4 == 0,
					"color":        deviceAttributes & 8 == 0
				}
			}
			self.intent = uInt32Number(header[64:68])
			self.illuminant = XYZNumber(header[68:80])
			self.creator = header[80:84]
			if header[84:100] != "\0" * 16:
				self.ID = header[84:100]
			
			self._data = data[:self.size]
			
			if load:
				self.tags
		else:
			# Default to RGB display device profile
			self.preferredCMM = ""
			self.version = 2.4
			self.profileClass = "mntr"
			self.colorSpace = "RGB"
			self.connectionColorSpace = "XYZ"
			self.dateTime = datetime.datetime.now()
			self.platform = ""
			self.embedded = False
			self.independent = True
			self.device = {
				"manufacturer": "",
				"model": "",
				"attributes": {
					"reflective":   True,
					"glossy":       True,
					"positive":     True,
					"color":        True
				}
			}
			self.intent = 0
			self.illuminant = XYZNumber("\0\0\xf6\xd6\0\x01\0\0\0\0\xd3-")  # D50
			self.creator = ""
	
	def __len__(self):
		"""
		Return the number of tags. 
		
		Can also be used in boolean comparisons (profiles with no tags
		evaluate to false)
		
		"""
		return len(self.tags)
	
	@property
	def data(self):
		"""
		Get raw binary profile data.
		
		This will re-assemble the various profile parts (header, 
		tag table and data) on-the-fly.
		
		"""
		# Assemble tag table and tag data
		tagCount = len(self.tags)
		tagTable = []
		tagTableSize = tagCount * 12
		tagsData = []
		tagsDataOffset = []
		tagDataOffset = 128 + 4 + tagTableSize
		for tagSignature in self.tags:
			tag = AODict.__getitem__(self.tags, tagSignature)
			if isinstance(tag, ICCProfileTag):
				tagData = self.tags[tagSignature].tagData
			else:
				tagData = tag[3]
			tagDataSize = len(tagData)
			# Pad all data with binary zeros so it lies on 4-byte boundaries
			padding = int(math.ceil(tagDataSize / 4.0)) * 4 - tagDataSize
			tagData += "\0" * padding
			tagTable.append(tagSignature)
			if tagData in tagsData:
				tagTable.append(uInt32Number_tohex(tagsDataOffset[tagsData.index(tagData)]))
			else:
				tagTable.append(uInt32Number_tohex(tagDataOffset))
			tagTable.append(uInt32Number_tohex(tagDataSize))
			if not tagData in tagsData:
				tagsData.append(tagData)
				tagsDataOffset.append(tagDataOffset)
				tagDataOffset += tagDataSize + padding
		header = self.header(tagTableSize, len("".join(tagsData)))
		data = "".join([header, uInt32Number_tohex(tagCount), 
						"".join(tagTable), "".join(tagsData)])
		return data
	
	def header(self, tagTableSize, tagDataSize):
		"Profile Header"
		# Profile size: 128 bytes header + 4 bytes tag count + tag table + data
		header = [uInt32Number_tohex(128 + 4 + tagTableSize + tagDataSize),
				  self.preferredCMM[:4].ljust(4, " ") if self.preferredCMM else "\0" * 4,
				  # Next three lines are ICC version
				  chr(int(str(self.version).split(".")[0])),
				  binascii.unhexlify(("%.2f" % self.version).split(".")[1]),
				  "\0" * 2,
				  self.profileClass[:4].ljust(4, " "),
				  self.colorSpace[:4].ljust(4, " "),
				  self.connectionColorSpace[:4].ljust(4, " "),
				  dateTimeNumber_tohex(self.dateTime),
				  "acsp",
				  self.platform[:4].ljust(4, " ") if self.platform else "\0" * 4,]
		flags = 0
		if self.embedded:
			flags += 1
		if not self.independent:
			flags += 2
		header.extend([uInt32Number_tohex(flags),
					   self.device["manufacturer"][:4].rjust(4, "\0") if self.device["manufacturer"] else "\0" * 4,
					   self.device["model"][:4].rjust(4, "\0") if self.device["model"] else "\0" * 4])
		deviceAttributes = 0
		for name, bit in {"reflective": 1,
						  "glossy": 2,
						  "positive": 4,
						  "color": 8}.iteritems():
			if not self.device["attributes"][name]:
				deviceAttributes += bit
		if sys.platform == "darwin" and self.version < 4:
			# Dont't include ID under Mac OS X unless v4 profile
			# to stop pedantic ColorSync utility from complaining
			# about header padding not being null
			id = ""
		else:
			id = self.ID[:16]
		header.extend([uInt64Number_tohex(deviceAttributes),
					   uInt32Number_tohex(self.intent),
					   self.illuminant.tohex(),
					   self.creator[:4].ljust(4, " ") if self.creator else "\0" * 4,
					   id.ljust(16, "\0"),
					   self._data[100:128] if len(self._data[100:128]) == 28 else "\0" * 28])
		return "".join(header)
	
	@property
	def tags(self):
		"Profile Tag Table"
		if not self._tags:
			self.load()
			if self._data and len(self._data) > 131:
				# tag table and tagged element data
				tagCount = uInt32Number(self._data[128:132])
				if debug: print "tagCount:", tagCount
				tagTable = self._data[132:132 + tagCount * 12]
				discard_len = 0
				tags = {}
				while tagTable:
					tag = tagTable[:12]
					if len(tag) < 12:
						raise ICCProfileInvalidError("Tag table is truncated")
					tagSignature = tag[:4]
					if debug: print "tagSignature:", tagSignature
					tagDataOffset = uInt32Number(tag[4:8])
					if debug: print "    tagDataOffset:", tagDataOffset
					tagDataSize = uInt32Number(tag[8:12])
					if debug: print "    tagDataSize:", tagDataSize
					if tagSignature in self._tags:
						safe_print("Error (non-critical): Tag '%s' already "
								   "encountered. Skipping..." % tagSignature)
					else:
						if (tagDataOffset, tagDataSize) in tags:
							if debug: print "    tagDataOffset and tagDataSize indicate shared tag"
						else:
							start = tagDataOffset - discard_len
							if debug: print "    tagData start:", start
							end = tagDataOffset - discard_len + tagDataSize
							if debug: print "    tagData end:", end
							tagData = self._data[start:end]
							if len(tagData) < tagDataSize:
								raise ICCProfileInvalidError("Tag data for tag %r (offet %i, size %i) is truncated" % (tagSignature,
																													   tagDataOffset,
																													   tagDataSize))
							typeSignature = tagData[:4]
							if len(typeSignature) < 4:
								raise ICCProfileInvalidError("Tag type signature for tag %r (offet %i, size %i) is truncated" % (tagSignature,
																																 tagDataOffset,
																																 tagDataSize))
							if debug: print "    typeSignature:", typeSignature
							tags[(tagDataOffset, tagDataSize)] = (typeSignature,
																  tagDataOffset,
																  tagDataSize,
																  tagData)
						self._tags[tagSignature] = tags[(tagDataOffset,
														 tagDataSize)]
					tagTable = tagTable[12:]
				self._data = self._data[:128]
		return self._tags
	
	def calculateID(self, setID=True):
		"""
		Calculates, sets, and returns the profile's ID (checksum).
		
		Calling this function always recalculates the checksum on-the-fly, 
		in contrast to just accessing the ID property.
		
		The entire profile, based on the size field in the header, is used 
		to calculate the ID after the values in the Profile Flags field 
		(bytes 44 to 47), Rendering Intent field (bytes 64 to 67) and 
		Profile ID field (bytes 84 to 99) in the profile header have been 
		temporarily replaced with zeros.
		
		"""
		data = self.data[:44] + "\0\0\0\0" + self.data[48:64] + "\0\0\0\0" + \
			   self.data[68:84] + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0" + \
			   self.data[100:]
		ID = md5(data).digest()
		if setID:
			self.ID = ID
		return ID
	
	def close(self):
		"""
		Closes the associated file object (if any).
		"""
		if self._file and not self._file.closed:
			self._file.close()

	@staticmethod
	def from_named_rgb_space(rgb_space_name, iccv4=False, cat="Bradford"):
		rgb_space = colormath.get_rgb_space(rgb_space_name)
		return ICCProfile.from_rgb_space(rgb_space, rgb_space_name, iccv4, cat)

	@staticmethod
	def from_rgb_space(rgb_space, description, iccv4=False, cat="Bradford"):
		rx, ry = rgb_space[2:][0][:2]
		gx, gy = rgb_space[2:][1][:2]
		bx, by = rgb_space[2:][2][:2]
		wx, wy = colormath.XYZ2xyY(*rgb_space[1])[:2]
		return ICCProfile.from_chromaticities(rx, ry, gx, gy,  bx, by, wx, wy,
											  rgb_space[0], description,
											  "No copyright")
		
	
	@staticmethod
	def from_edid(edid, iccv4=False, cat="Bradford"):
		""" Create an ICC Profile from EDID data and return it
		
		You may override the gamma from EDID by setting it to a list of curve
		values.
		
		"""
		description = edid.get("monitor_name",
								edid.get("ascii", str(edid["product_id"] or
													  edid["hash"])))
		manufacturer = edid.get("manufacturer", "")
		manufacturer_id = edid["edid"][8:10]
		model_name = description
		model_id = edid["edid"][10:12]
		copyright = "Created from EDID"
		# Get chromaticities of primaries
		xy = {}
		for color in ("red", "green", "blue", "white"):
			x, y = edid.get(color + "_x", 0.0), edid.get(color + "_y", 0.0)
			xy[color[0] + "x"] = x
			xy[color[0] + "y"] = y
		gamma = edid.get("gamma", 2.2)
		profile = ICCProfile.from_chromaticities(xy["rx"], xy["ry"],
												 xy["gx"], xy["gy"],
												 xy["bx"], xy["by"],
												 xy["wx"], xy["wy"], gamma,
												 description, copyright,
												 manufacturer, model_name,
												 manufacturer_id, model_id,
												 iccv4, cat)
		profile.set_edid_metadata(edid)
		spec_prefixes = "DATA_,OPENICC_"
		prefixes = (profile.tags.meta.getvalue("prefix", "", None) or spec_prefixes).split(",")
		for prefix in spec_prefixes.split(","):
			if not prefix in prefixes:
				prefixes.append(prefix)
		profile.tags.meta["prefix"] = ",".join(prefixes)
		profile.tags.meta["OPENICC_automatic_generated"] = "1"
		profile.tags.meta["DATA_source"] = "edid"
		profile.calculateID()
		return profile

	@staticmethod
	def from_chromaticities(rx, ry, gx, gy, bx, by, wx, wy, gamma, description,
							copyright, manufacturer=None, model_name=None,
							manufacturer_id="\0\0", model_id="\0\0",
							iccv4=False, cat="Bradford"):
		""" Create an ICC Profile from chromaticities and return it
		
		"""
		wXYZ = colormath.xyY2XYZ(wx, wy, 1.0)
		# Calculate RGB to XYZ matrix from chromaticities and white
		mtx = colormath.rgb_to_xyz_matrix(rx, ry,
										  gx, gy,
										  bx, by, wXYZ)
		rgb = {"r": (1.0, 0.0, 0.0),
			   "g": (0.0, 1.0, 0.0),
			   "b": (0.0, 0.0, 1.0)}
		XYZ = {}
		for color in "rgb":
			# Calculate XYZ for primaries
			XYZ[color] = mtx * rgb[color]
		profile = ICCProfile.from_XYZ(XYZ["r"], XYZ["g"], XYZ["b"], wXYZ,
									  gamma, description, copyright,
									  manufacturer, model_name, manufacturer_id,
									  model_id, iccv4, cat)
		return profile
	
	@staticmethod
	def from_XYZ(rXYZ, gXYZ, bXYZ, wXYZ, gamma, description, copyright,
				 manufacturer=None, model_name=None, manufacturer_id="\0\0",
				 model_id="\0\0", iccv4=False, cat="Bradford"):
		""" Create an ICC Profile from XYZ values and return it
		
		"""
		profile = ICCProfile()
		if iccv4:
			profile.version = 4.2
		profile.setDescription(description)
		profile.setCopyright(copyright)
		if manufacturer:
			profile.setDeviceManufacturerDescription(manufacturer)
		if model_name:
			profile.setDeviceModelDescription(model_name)
		profile.device["manufacturer"] = "\0\0" + manufacturer_id[1] + manufacturer_id[0]
		profile.device["model"] = "\0\0" + model_id[1] + model_id[0]
		# Add Apple-specific 'mmod' tag (TODO: need full spec)
		if manufacturer_id != "\0\0" or  model_id != "\0\0":
			mmod = ("mmod" + ("\x00" * 6) + manufacturer_id +
					("\x00" * 2) + model_id[1] + model_id[0] +
					("\x00" * 4) + ("\x00" * 20))
			profile.tags.mmod = ICCProfileTag(mmod, "mmod")
		profile.tags.wtpt = XYZType(profile=profile)
		D50 = colormath.get_whitepoint("D50")
		if iccv4:
			# Set wtpt to D50 and store actual white -> D50 transform in chad
			(profile.tags.wtpt.X, profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = D50
			profile.tags.chad = chromaticAdaptionTag()
			matrix = colormath.wp_adaption_matrix(wXYZ, D50, cat)
			profile.tags.chad.update(matrix)
		else:
			# Store actual white in wtpt
			(profile.tags.wtpt.X, profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = wXYZ
		profile.tags.chrm = ChromaticityType()
		profile.tags.chrm.type = 0
		for color in "rgb":
			X, Y, Z = locals()[color + "XYZ"]
			# Get chromaticity of primary
			x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
			profile.tags.chrm.channels.append((x, y))
			# Write XYZ and TRC tags (don't forget to adapt to D50)
			tagname = color + "XYZ"
			profile.tags[tagname] = XYZType(profile=profile)
			(profile.tags[tagname].X, profile.tags[tagname].Y,
			 profile.tags[tagname].Z) = colormath.adapt(X, Y, Z, wXYZ, D50, cat)
			tagname = color + "TRC"
			profile.tags[tagname] = CurveType(profile=profile)
			if isinstance(gamma, (list, tuple)):
				profile.tags[tagname].extend(gamma)
			else:
				profile.tags[tagname].set_trc(gamma, 1)
		profile.calculateID()
		return profile

	def set_blackpoint(self, XYZbp):
		self.tags.bkpt = XYZType(tagSignature="bkpt", profile=self)
		self.tags.bkpt.X, self.tags.bkpt.Y, self.tags.bkpt.Z = XYZbp

	def apply_black_offset(self, XYZbp, power=40.0, include_A2B=True,
						   set_blackpoint=True, logfiles=None,
						   thread_abort=None, abortmessage="Aborted"):
		# Apply only the black point blending portion of BT.1886 mapping
		if include_A2B:
			tables = []
			for i in xrange(3):
				a2b = self.tags.get("A2B%i" % i)
				if isinstance(a2b, LUT16Type) and not a2b in tables:
					a2b.apply_black_offset(XYZbp, logfiles, thread_abort,
										   abortmessage)
					tables.append(a2b)
		if set_blackpoint:
			self.set_blackpoint(XYZbp)
		if not self.tags.get("rTRC"):
			return
		rXYZ = self.tags.rXYZ.values()
		gXYZ = self.tags.gXYZ.values()
		bXYZ = self.tags.bXYZ.values()
		mtx = colormath.Matrix3x3([[rXYZ[0], gXYZ[0], bXYZ[0]],
								   [rXYZ[1], gXYZ[1], bXYZ[1]],
								   [rXYZ[2], gXYZ[2], bXYZ[2]]])
		imtx = mtx.inverted()
		for channel in "rgb":
			tag = CurveType(profile=self)
			if len(self.tags[channel + "TRC"]) == 1:
				gamma = self.tags[channel + "TRC"].get_gamma()
				tag.set_trc(gamma, 1024)
			else:
				tag.extend(self.tags[channel + "TRC"])
			self.tags[channel + "TRC"] = tag
		rgbbp_in = []
		for channel in "rgb":
			rgbbp_in.append(self.tags["%sTRC" % channel][0] / 65535.0)
		bp_in = mtx * rgbbp_in
		if tuple(bp_in) == tuple(XYZbp):
			return
		size = len(self.tags.rTRC)
		for i in xrange(size):
			rgb = []
			for channel in "rgb":
				rgb.append(self.tags["%sTRC" % channel][i] / 65535.0)
			X, Y, Z = mtx * rgb
			XYZ = colormath.blend_blackpoint(X, Y, Z, bp_in, XYZbp, power)
			rgb = imtx * XYZ
			for j in xrange(3):
				self.tags["%sTRC" % "rgb"[j]][i] = min(max(rgb[j], 0), 1) * 65535
	
	def set_bt1886_trc(self, XYZbp, outoffset=0.0, gamma=2.4, gamma_type="B",
					   size=None):
		if gamma_type in ("b", "g"):
			# Get technical gamma needed to achieve effective gamma
			gamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
		rXYZ = self.tags.rXYZ.values()
		gXYZ = self.tags.gXYZ.values()
		bXYZ = self.tags.bXYZ.values()
		mtx = colormath.Matrix3x3([[rXYZ[0], gXYZ[0], bXYZ[0]],
								   [rXYZ[1], gXYZ[1], bXYZ[1]],
								   [rXYZ[2], gXYZ[2], bXYZ[2]]])
		bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
		values = OrderedDict()
		for i, channel in enumerate(("r", "g", "b")):
			self.tags[channel + "TRC"] = CurveType(profile=self)
			self.tags[channel + "TRC"].set_trc(-709, size)
			for j, v in enumerate(self.tags[channel + "TRC"]):
				if not values.get(j):
					values[j] = []
				values[j].append(v / 65535.0)
		for i, (r, g, b) in values.iteritems():
			X, Y, Z = mtx * (r, g, b)
			values[i] = bt1886.apply(X, Y, Z)
		for i, XYZ in values.iteritems():
			rgb = mtx.inverted() * XYZ
			for j, channel in enumerate(("r", "g", "b")):
				self.tags[channel + "TRC"][i] = max(min(rgb[j] * 65535, 65535),
													0)
		self.set_blackpoint(XYZbp)
	
	def set_dicom_trc(self, XYZbp, white_cdm2=100, size=1024):
		"""
		Set the response to the DICOM Grayscale Standard Display Function
		
		This response is special in that it depends on the actual black
		and white level of the display.
		
		XYZbp   Black point in absolute XYZ, Y range 0.05..white_cdm2
		
		"""
		self.set_trc_tags()
		for channel in "rgb":
			self.tags["%sTRC" % channel].set_dicom_trc(XYZbp[1], white_cdm2,
													   size)
		self.apply_black_offset([v / white_cdm2 for v in XYZbp],
								40.0 * (white_cdm2 / 40.0))

	def set_hlg_trc(self, XYZbp=(0, 0, 0), white_cdm2=100, system_gamma=1.2,
					ambient_cdm2=5, maxsignal=1.0, size=1024,
					blend_blackpoint=True):
		"""
		Set the response to the Hybrid Log-Gamma (HLG) function
		
		This response is special in that it depends on the actual black
		and white level of the display, system gamma and ambient.
		
		XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
		maxsignal       Set clipping point (optional)
		size            Number of steps. Recommended >= 1024
		
		"""
		self.set_trc_tags()
		for channel in "rgb":
			self.tags["%sTRC" % channel].set_hlg_trc(XYZbp[1], white_cdm2,
													 system_gamma,
													 ambient_cdm2,
													 maxsignal, size)
		if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
			self.apply_black_offset([v / white_cdm2 for v in XYZbp],
									40.0 * (white_cdm2 / 100.0))

	def set_smpte2084_trc(self, XYZbp=(0, 0, 0), white_cdm2=100,
						  master_black_cdm2=0, master_white_cdm2=10000,
						  rolloff=False, size=1024, blend_blackpoint=True):
		"""
		Set the response to the SMPTE 2084 perceptual quantizer (PQ) function
		
		This response is special in that it depends on the actual black
		and white level of the display.
		
		XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
		master_black_cdm2  (Optional) Used to normalize PQ values
		master_white_cdm2  (Optional) Used to normalize PQ values
		rolloff         BT.2390
		size            Number of steps. Recommended >= 1024
		
		"""
		self.set_trc_tags()
		for channel in "rgb":
			self.tags["%sTRC" % channel].set_smpte2084_trc(XYZbp[1],
														   white_cdm2,
														   master_black_cdm2,
														   master_white_cdm2,
														   rolloff, size)
		if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
			self.apply_black_offset([v / white_cdm2 for v in XYZbp],
									40.0 * (white_cdm2 / 100.0))

	def set_trc_tags(self, identical=False):
		for channel in "rgb":
			if identical and channel != "r":
				tag = self.tags.rTRC
			else:
				tag = CurveType(profile=self)
			self.tags["%sTRC" % channel] = tag
	
	def set_localizable_desc(self, tagname, description, languagecode="en",
							 countrycode="US"):
		# Handle ICCv2 <> v4 differences and encoding
		if self.version < 4:
			self.tags[tagname] = TextDescriptionType()
			if isinstance(description, unicode):
				asciidesc = description.encode("ASCII", "asciize")
			else:
				asciidesc = description
			self.tags[tagname].ASCII = asciidesc
			if asciidesc != description:
				self.tags[tagname].Unicode = description
		else:
			self.set_localizable_text(self, tagname, description, languagecode,
									  countrycode)

	def set_localizable_text(self, tagname, text, languagecode="en",
							 countrycode="US"):
		# Handle ICCv2 <> v4 differences and encoding
		if self.version < 4:
			if isinstance(text, unicode):
				text = text.encode("ASCII", "asciize")
			self.tags[tagname] = TextType("text\0\0\0\0%s\0" % text, tagname)
		else:
			self.tags[tagname] = MultiLocalizedUnicodeType()
			self.tags[tagname].add_localized_string(languagecode,
													   countrycode, text)

	def setCopyright(self, copyright, languagecode="en", countrycode="US"):
		self.set_localizable_text("cprt", copyright, languagecode, countrycode)

	def setDescription(self, description, languagecode="en", countrycode="US"):
		self.set_localizable_desc("desc", description, languagecode, countrycode)

	def setDeviceManufacturerDescription(self, description, languagecode="en",
										 countrycode="US"):
		self.set_localizable_desc("dmnd", description, languagecode, countrycode)

	def setDeviceModelDescription(self, description, languagecode="en",
								  countrycode="US"):
		self.set_localizable_desc("dmdd", description, languagecode, countrycode)
		

	def getCopyright(self):
		"""
		Return profile copyright.
		"""
		return unicode(self.tags.get("cprt", ""))
	
	def getDescription(self):
		"""
		Return profile description.
		"""
		return unicode(self.tags.get("desc", ""))
	
	def getDeviceManufacturerDescription(self):
		"""
		Return device manufacturer description.
		"""
		return unicode(self.tags.get("dmnd", ""))
	
	def getDeviceModelDescription(self):
		"""
		Return device model description.
		"""
		return unicode(self.tags.get("dmdd", ""))
	
	def getViewingConditionsDescription(self):
		"""
		Return viewing conditions description.
		"""
		return unicode(self.tags.get("vued", ""))
	
	def guess_cat(self, matrix=True):
		"""
		Get or guess chromatic adaptation transform.
		
		If 'matrix' is True, and 'arts' tag is present, return actual matrix
		instead of name.
		
		"""
		illuminant = self.illuminant.values()
		if isinstance(self.tags.get("chad"), chromaticAdaptionTag):
			return colormath.guess_cat(self.tags.chad, 
									   self.tags.chad.inverted() * illuminant, 
									   illuminant)
		elif isinstance(self.tags.get("arts"), chromaticAdaptionTag):
			if matrix:
				return self.tags.arts
			return self.tags.arts.get_cat()
	
	def isSame(self, profile, force_calculation=False):
		"""
		Compare the ID of profiles.
		
		Returns a boolean indicating if the profiles have the same ID.
		
		profile can be a ICCProfile instance, a binary string
		containing profile data, a filename or a file object.
		
		"""
		if not isinstance(profile, self.__class__):
			profile = self.__class__(profile)
		if force_calculation or self.ID == "\0" * 16:
			id1 = self.calculateID(False)
		else:
			id1 = self.ID
		if force_calculation or profile.ID == "\0" * 16:
			id2 = profile.calculateID(False)
		else:
			id2 = profile.ID
		return id1 == id2
	
	def load(self):
		"""
		Loads the profile from the file object.

		Normally, you don't need to call this method, since the ICCProfile 
		class automatically loads the profile when necessary (load does 
		nothing if the profile was passed in as a binary string).
		
		"""
		if not self.is_loaded and self._file:
			if self._file.closed:
				self._file = open(self._file.name, "rb")
				self._file.seek(len(self._data))
			self._data += self._file.read(self.size - len(self._data))
			self._file.close()
			self.is_loaded = True
	
	def print_info(self):
		safe_print("=" * 80)
		safe_print("ICC profile information")
		safe_print("-" * 80)
		safe_print("File name:", os.path.basename(self.fileName or ""))
		for label, value in self.get_info():
			if not value:
				safe_print(label)
			else:
				safe_print(label + ":", value)
	
	def get_info(self):
		info = DictList()
		info["Size"] = "%i Bytes (%.2f KiB)" % (self.size, self.size / 1024.0)
		info["Preferred CMM"] = hexrepr(self.preferredCMM, cmms)
		info["ICC version"] = "%s" % self.version
		info["Profile class"] = profileclass.get(self.profileClass,
												 self.profileClass)
		info["Color model"] = self.colorSpace
		info["Profile connection space (PCS)"] = self.connectionColorSpace
		info["Created"] = strftime("%Y-%m-%d %H:%M:%S",
									self.dateTime.timetuple())
		info["Platform"] = platform.get(self.platform, hexrepr(self.platform))
		info["Is embedded"] = {True: "Yes"}.get(self.embedded, "No")
		info["Can be used independently"] = {True: "Yes"}.get(self.independent,
															  "No")
		info["Device"] = ""
		info["    Manufacturer"] = "0x%s" % binascii.hexlify(self.device["manufacturer"]).upper()
		if (self.device["manufacturer"][0:2] == "\0\0" and
			self.device["manufacturer"][2:4] != "\0\0"):
			mnft_id = self.device["manufacturer"][3] + self.device["manufacturer"][2]
			mnft_id = edid.parse_manufacturer_id(mnft_id)
			manufacturer = edid.get_manufacturer_name(mnft_id)
		else:
			manufacturer = safe_unicode(re.sub("[^\x20-\x7e]", "", self.device["manufacturer"])).encode("ASCII", "replace")
			if manufacturer != self.device["manufacturer"]:
				manufacturer = None
			else:
				manufacturer = "'%s'" % manufacturer
		if manufacturer is not None:
			info["    Manufacturer"] += " %s" % manufacturer
		info["    Model"] = hexrepr(self.device["model"])
		info["    Attributes"] = "\n".join([{True: "Reflective"}.get(self.device["attributes"]["reflective"], "Transparency"),
											{True: "Glossy"}.get(self.device["attributes"]["glossy"], "Matte"),
											{True: "Positive"}.get(self.device["attributes"]["positive"], "Negative"),
											{True: "Color"}.get(self.device["attributes"]["color"], "Black & white")])
		info["Default rendering intent"] = {0: "Perceptual",
											1: "Media-relative colorimetric",
											2: "Saturation",
											3: "ICC-absolute colorimetric"}.get(self.intent, "Unknown")
		info["PCS illuminant XYZ"] = " ".join([" ".join(["%6.2f" % (v * 100) for v in self.illuminant.values()]),
											   "(xy %s," % " ".join("%6.4f" % v for v in
																	self.illuminant.xyY[:2]),
											   "CCT %iK)" % (colormath.XYZ2CCT(*self.illuminant.values()) or 0)])
		info["Creator"] = hexrepr(self.creator, manufacturers)
		info["Checksum"] = "0x%s" % binascii.hexlify(self.ID).upper()
		calcID = self.calculateID(False)
		if self.ID != "\0" * 16:
			info["    Checksum OK"] = {True: "Yes"}.get(self.ID == calcID, "No")
		if self.ID != calcID:
			info["    Calculated checksum"] = "0x%s" % binascii.hexlify(calcID).upper()
		for sig, tag in self.tags.iteritems():
			name = tags.get(sig, "'%s'" % sig)
			if isinstance(tag, chromaticAdaptionTag):
				info[name] = self.guess_cat(False) or "Unknown"
				name = "    Matrix"
				for i, row in enumerate(tag):
					if i > 0:
						name = "    " * 2
					info[name] = " ".join("%6.4f" % v for v in row)
			elif isinstance(tag, ChromaticityType):
				info["Chromaticity (illuminant-relative)"] = ""
				for i, channel in enumerate(tag.channels):
					if self.colorSpace.endswith("CLR"):
						colorant_name = ""
					else:
						colorant_name = "(%s) " % self.colorSpace[i:i + 1]
					info["    Channel %i %sxy" % (i + 1, colorant_name)] = " ".join(
						"%6.4f" % v for v in channel)
			elif isinstance(tag, ColorantTableType):
				info["Colorants (PCS-relative)"] = ""
				maxlen = max(map(len, tag.keys()))
				for colorant_name, colorant in tag.iteritems():
					values = colorant.values()
					if "".join(colorant.keys()) == "Lab":
						values = colormath.Lab2XYZ(*values)
					else:
						values = [v / 100.0 for v in values]
					XYZxy = [" ".join("%6.2f" % v for v in colorant.values())]
					if values != [0, 0, 0]:
						XYZxy.append("(xy %s)" % " ".join("%6.4f" % v for v in
														  colormath.XYZ2xyY(*values)[:2]))
					info["    %s %s" % (colorant_name,
									    "".join(colorant.keys()))] = " ".join(XYZxy)
			elif isinstance(tag, CurveType):
				if len(tag) == 1:
					info[name] = "Gamma %3.2f" % tag[0]
				elif len(tag):
					info[name] = ""
					info["    Number of entries"] = "%i" % len(tag)
					#info["    Average gamma"] = "%3.2f" % tag.get_gamma()
					transfer_function = tag.get_transfer_function(slice=(0, 1.0),
																  outoffset=1.0)
					if round(transfer_function[1], 2) == 1.0:
						value = u"%s" % (
							transfer_function[0][0])
					else:
						if transfer_function[1] >= .95:
							value = u"≈ %s (Δ %.2f%%)" % (
								transfer_function[0][0], 100 - transfer_function[1] * 100)
						else:
							value = "Unknown"
					info["    Transfer function"] = value
					info["    Minimum Y"] = "%6.4f" % (tag[0] / 65535.0 * 100)
					info["    Maximum Y"] = "%6.2f" % (tag[-1] / 65535.0 * 100)
			elif isinstance(tag, DictType):
				if sig == "meta":
					name = "Metadata"
				else:
					name = "Generic name-value data"
				info[name] = ""
				for key in tag:
					key = tag.getname(key)
					value = tag.getvalue(key)
					if key == "prefix":
						value = "\n".join(value.split(","))
					info["    %s" % key] = value
			elif isinstance(tag, LUT16Type):
				info[name] = ""
				name = "    Matrix"
				for i, row in enumerate(tag.matrix):
					if i > 0:
						name = "    " * 2
					info[name] = " ".join("%6.4f" % v for v in row)
				info["    Input Table"] = ""
				info["        Channels"] = "%i" % tag.input_channels_count
				info["        Number of entries per channel"] = "%i" % tag.input_entries_count
				info["    Color Look Up Table"] = ""
				info["        Grid Steps"] = "%i" % tag.clut_grid_steps
				info["        Entries"] = "%i" % (tag.clut_grid_steps **
												  tag.input_channels_count)
				info["    Output Table"] = ""
				info["        Channels"] = "%i" % tag.output_channels_count
				info["        Number of entries per channel"] = "%i" % tag.output_entries_count
			elif isinstance(tag, MakeAndModelType):
				info[name] = ""
				info["    Manufacturer"] = "0x%s %s" % (
					binascii.hexlify(tag.manufacturer).upper(),
					edid.get_manufacturer_name(edid.parse_manufacturer_id(tag.manufacturer)) or "")
				info["    Model"] = "0x%s" % binascii.hexlify(tag.model).upper()
			elif isinstance(tag, MeasurementType):
				info[name] = ""
				info["    Observer"] = tag.observer.description
				info["    Backing XYZ"] = " ".join("%6.2f" % v for v in
												   tag.backing.values())
				info["    Geometry"] = tag.geometry.description
				info["    Flare"] = "%.2f%%" % (tag.flare * 100)
				info["    Illuminant"] = tag.illuminantType.description
			elif isinstance(tag, MultiLocalizedUnicodeType):
				info[name] = ""
				for language, countries in tag.iteritems():
					for country, value in countries.iteritems():
						if country.strip("\0 "):
							country = "/" + country
						info["    %s%s" % (language, country)] = value
			elif isinstance(tag, NamedColor2Type):
				info[name] = ""
				info["    Device color components"] = "%i" % (
			                tag.deviceCoordCount,)
				info["    Colors (PCS-relative)"] = "%i (%i Bytes) " % (
					tag.colorCount, len(tag.tagData))
				i = 1
				for k, v in tag.iteritems():
					pcsout = []
					devout = []
					for kk, vv in v.pcs.iteritems():
						pcsout.append("%03.2f" % vv)
					for vv in v.device:
						devout.append("%03.2f" % vv)
					formatstr = "        %%0%is %%s%%s%%s" % len(str(tag.colorCount))
					key = formatstr % (i, tag.prefix, k, tag.suffix)
					info[key] = "%s %s" % ("".join(v.pcs.keys()),
										   " ".join(pcsout))
					if (self.colorSpace != self.connectionColorSpace or
						" ".join(pcsout) != " ".join(devout)):
						info[key] += " (%s %s)" % (self.colorSpace,
												   " ".join(devout))
					i += 1
			elif isinstance(tag, Text):
				if sig == "cprt":
					info[name] = unicode(tag)
				elif sig == "ciis":
					info[name] = ciis.get(tag, "'%s'" % tag)
				elif sig == "tech":
					info[name] = tech.get(tag, "'%s'" % tag)
				elif tag.find("\n") > -1 or tag.find("\r") > -1:
					info[name] = "[%i Bytes]" % len(tag)
				else:
					info[name] = (unicode(tag)[:60 - len(name)] +
								  ("...[%i more Bytes]" % (len(tag) -
														   (60 - len(name)))
								   if len(tag) > 60 - len(name) else ""))
			elif isinstance(tag, TextDescriptionType):
				if not tag.get("Unicode") and not tag.get("Macintosh"):
					info["%s (ASCII)" % name] = safe_unicode(tag.ASCII)
				else:
					info[name] = ""
					info["    ASCII"] = safe_unicode(tag.ASCII)
					if tag.get("Unicode"):
						info["    Unicode"] = tag.Unicode
					if tag.get("Macintosh"):
						info["    Macintosh"] = tag.Macintosh
			elif isinstance(tag, VideoCardGammaFormulaType):
				info[name] = ""
				#linear = tag.is_linear()
				#info["    Is linear"] = {0: "No", 1: "Yes"}[linear]
				for key in ("red", "green", "blue"):
					info["    %s gamma" % key.capitalize()] = "%.2f" % tag[key + "Gamma"]
					info["    %s minimum" % key.capitalize()] = "%.2f" % tag[key + "Min"]
					info["    %s maximum" % key.capitalize()] = "%.2f" % tag[key + "Max"]
			elif isinstance(tag, VideoCardGammaTableType):
				info[name] = ""
				info["    Bitdepth"] = "%i" % (tag.entrySize * 8)
				info["    Channels"] = "%i" % tag.channels
				info["    Number of entries per channel"] = "%i" % tag.entryCount
				r_points, g_points, b_points, linear_points = tag.get_values()
				points = r_points, g_points, b_points
				#if r_points == g_points == b_points == linear_points:
					#info["    Is linear" % i] = {True: "Yes"}.get(points[i] == linear_points, "No")
				#else:
				if True:
					unique = tag.get_unique_values()
					for i, channel in enumerate(tag.data):
						scale = math.pow(2, tag.entrySize * 8) - 1
						vmin = 0
						vmax = scale
						gamma = colormath.get_gamma([((len(channel) / 2 - 1) /
													  (len(channel) - 1.0) * scale,
													  channel[len(channel) / 2 - 1])],
													scale, vmin, vmax, False,
													False)
						if gamma:
							info["    Channel %i gamma at 50%% input" %
								 (i + 1)] = "%.2f" % gamma[0]
						vmin = channel[0]
						vmax = channel[-1]
						info["    Channel %i minimum" % (i + 1)] = "%6.4f%%" % (vmin / scale * 100)
						info["    Channel %i maximum" % (i + 1)] = "%6.2f%%" % (vmax / scale * 100)
						info["    Channel %i unique values" % (i + 1)] = "%i @ 8 Bit" % len(unique[i])
						info["    Channel %i is linear" % (i + 1)] = {True: "Yes"}.get(points[i] == linear_points, "No")
			elif isinstance(tag, ViewingConditionsType):
				info[name] = ""
				info["    Illuminant"] = tag.illuminantType.description
				info["    Illuminant XYZ"] = "%s (xy %s)" % (
					" ".join("%6.2f" % v for v in tag.illuminant.values()),
					" ".join("%6.4f" % v for v in tag.illuminant.xyY[:2]))
				XYZxy = [" ".join("%6.2f" % v for v in tag.surround.values())]
				if tag.surround.values() != [0, 0, 0]:
					XYZxy.append("(xy %s)" % " ".join("%6.4f" % v for v in
													  tag.surround.xyY[:2]))
				info["    Surround XYZ"] = " ".join(XYZxy)
			elif isinstance(tag, XYZType):
				if sig == "lumi":
					info[name] = u"%.2f cd/m²" % self.tags.lumi.Y
				elif sig in ("bkpt", "wtpt"):
					format = {"bkpt": "%6.4f",
							  "wtpt": "%6.2f"}[sig]
					info[name] = ""
					if self.profileClass == "mntr" and sig == "wtpt":
						info["    Is illuminant"] = "Yes"
					if self.profileClass == "mntr" or "chad" in self.tags:
						label = "Illuminant-relative"
					else:
						label = "PCS-relative"
					#if (self.connectionColorSpace == "Lab" and
						#self.profileClass == "prtr"):
					if self.profileClass == "prtr":
						color = [" ".join([format % v for v in tag.ir.Lab])]
						info["    %s Lab" % label] = " ".join(color)
					else:
						color = [" ".join(format % (v * 100) for v in
										  tag.ir.values())]
						if tag.ir.values() != [0, 0, 0]:
							xy = " ".join("%6.4f" % v for v in tag.ir.xyY[:2])
							color.append("(xy %s)" % xy)
							cct, delta = colormath.xy_CCT_delta(*tag.ir.xyY[:2])
						else:
							cct = None
						info["    %s XYZ" % label] = " ".join(color)
						if cct:
							info["    %s CCT" % label] = "%iK" % cct
							if delta:
								info[u"        ΔE 2000 to daylight locus"] = "%.2f" % delta["E"]
							kwargs = {"daylight": False}
							cct, delta = colormath.xy_CCT_delta(*tag.ir.xyY[:2], **kwargs)
							if delta:
								info[u"        ΔE 2000 to blackbody locus"] = "%.2f" % delta["E"]
					if "chad" in self.tags:
						color = [" ".join(format % (v * 100) for v in
										  tag.pcs.values())]
						if tag.pcs.values() != [0, 0, 0]:
							xy = " ".join("%6.4f" % v for v in tag.pcs.xyY[:2])
							color.append("(xy %s)" % xy)
						info["    PCS-relative XYZ"] = " ".join(color)
						cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2])
						if cct:
							info["    PCS-relative CCT"] = "%iK" % cct
							#if delta:
								#info[u"        ΔE 2000 to daylight locus"] = "%.2f" % delta["E"]
							#kwargs = {"daylight": False}
							#cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2], **kwargs)
							#if delta:
								#info[u"        ΔE 2000 to blackbody locus"] = "%.2f" % delta["E"]
				else:
					info[name] = ""
					info["    Illuminant-relative XYZ"] = " ".join(
						[" ".join("%6.2f" % (v * 100) for v in
								  tag.ir.values()),
						 "(xy %s)" % " ".join("%6.4f" % v for v in
												tag.ir.xyY[:2])])
					info["    PCS-relative XYZ"] = " ".join(
						[" ".join("%6.2f" % (v * 100) for v in
								  tag.values()),
						 "(xy %s)" % " ".join("%6.4f" % v for v in
												tag.xyY[:2])])
			elif isinstance(tag, ICCProfileTag):
				info[name] = "'%s' [%i Bytes]" % (tag.tagData[:4],
												  len(tag.tagData))
		return info
	
	def get_rgb_space(self, relation="ir", gamma=None):
		tags = self.tags
		if not "wtpt" in tags:
			return False
		rgb_space = [gamma or [], getattr(tags.wtpt, relation).values()]
		for component in ("r", "g", "b"):
			if (not "%sXYZ" % component in tags or
				(not gamma and (not "%sTRC" % component in tags or
								not isinstance(tags["%sTRC" % component],
											   CurveType)))):
				return False
			rgb_space.append(getattr(tags["%sXYZ" % component], relation).xyY)
			if not gamma:
				if len(tags["%sTRC" % component]) > 1:
					rgb_space[0].append([v / 65535.0 for v in
										 tags["%sTRC" % component]])
				else:
					rgb_space[0].append(tags["%sTRC" % component][0])
		return rgb_space
	
	def read(self, profile):
		"""
		Read profile from binary string, filename or file object.
		Same as self.__init__(profile)
		"""
		self.__init__(profile)
	
	def set_edid_metadata(self, edid):
		"""
		Sets metadata from EDID
		
		Key names follow the ICC meta Tag for Monitor Profiles specification
		http://www.oyranos.org/wiki/index.php?title=ICC_meta_Tag_for_Monitor_Profiles_0.1
		and the GNOME Color Manager metadata specification
		http://gitorious.org/colord/master/blobs/master/doc/metadata-spec.txt
		
		"""
		if not "meta" in self.tags:
			self.tags.meta = DictType()
		spec_prefixes = "EDID_"
		prefixes = (self.tags.meta.getvalue("prefix", "", None) or spec_prefixes).split(",")
		for prefix in spec_prefixes.split(","):
			if not prefix in prefixes:
				prefixes.append(prefix)
		# OpenICC keys (some shared with GCM)
		self.tags.meta.update((("prefix", ",".join(prefixes)),
							   ("EDID_mnft", edid["manufacturer_id"]),
							   ("EDID_mnft_id", struct.unpack(">H",
															  edid["edid"][8:10])[0]),
							   ("EDID_model_id", edid["product_id"]),
							   ("EDID_date", "%0.4i-T%i" %
											 (edid["year_of_manufacture"],
											  edid["week_of_manufacture"])),
							   ("EDID_red_x", edid["red_x"]),
							   ("EDID_red_y", edid["red_y"]),
							   ("EDID_green_x", edid["green_x"]),
							   ("EDID_green_y", edid["green_y"]),
							   ("EDID_blue_x", edid["blue_x"]),
							   ("EDID_blue_y", edid["blue_y"]),
							   ("EDID_white_x", edid["white_x"]),
							   ("EDID_white_y", edid["white_y"])))
		manufacturer = edid.get("manufacturer")
		if manufacturer:
			self.tags.meta["EDID_manufacturer"] = colord.quirk_manufacturer(manufacturer)
		if "gamma" in edid:
			self.tags.meta["EDID_gamma"] = edid["gamma"]
		monitor_name = edid.get("monitor_name", edid.get("ascii"))
		if monitor_name:
			self.tags.meta["EDID_model"] = monitor_name
		if edid.get("serial_ascii"):
			self.tags.meta["EDID_serial"] = edid["serial_ascii"]
		elif edid.get("serial_32"):
			self.tags.meta["EDID_serial"] = str(edid["serial_32"])
		# GCM keys
		self.tags.meta["EDID_md5"] = edid["hash"]
	
	def set_gamut_metadata(self, gamut_volume=None, gamut_coverage=None):
		""" Sets gamut volume and coverage metadata keys """
		if gamut_volume or gamut_coverage:
			if not "meta" in self.tags:
				self.tags.meta = DictType()
			# Update meta prefix
			prefixes = (self.tags.meta.getvalue("prefix", "", None) or
						"GAMUT_").split(",")
			if not "GAMUT_" in prefixes:
				prefixes.append("GAMUT_")
				self.tags.meta["prefix"] = ",".join(prefixes)
			if gamut_volume:
				# Set gamut size
				self.tags.meta["GAMUT_volume"] = gamut_volume
			if gamut_coverage:
				# Set gamut coverage
				for key, factor in gamut_coverage.iteritems():
					self.tags.meta["GAMUT_coverage(%s)" % key] = factor
	
	def write(self, stream_or_filename=None):
		"""
		Write profile to stream.
		
		This will re-assemble the various profile parts (header, 
		tag table and data) on-the-fly.
		
		"""
		if not stream_or_filename:
			if self._file:
				if not self._file.closed:
					self.close()
			stream_or_filename = self.fileName
		if isinstance(stream_or_filename, basestring):
			stream = open(stream_or_filename, "wb")
			if not self.fileName:
				self.fileName = stream_or_filename
		else:
			stream = stream_or_filename
		stream.write(self.data)
		if isinstance(stream_or_filename, basestring):
			stream.close()
