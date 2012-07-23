#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math


def get_transfer_function_phi(alpha, gamma):
	return (math.pow(1 + alpha, gamma) * math.pow(gamma - 1, gamma - 1)) / (math.pow(alpha, gamma - 1) * math.pow(gamma, gamma))


LSTAR_E = 216.0 / 24389.0  # Intent of CIE standard, actual CIE standard = 0.008856
LSTAR_K = 24389.0 / 27.0  # Intent of CIE standard, actual CIE standard = 903.3
REC709_K0 = 0.081  ##0.099 / (1.0 / 0.45 - 1)
REC709_P = 4.5  ##get_transfer_function_phi(0.099, 1.0 / 0.45)
SMPTE240M_K0 = 0.0913  ##0.1115 / (1.0 / 0.45 - 1)
SMPTE240M_P = 4.0  ##get_transfer_function_phi(0.1115, 1.0 / 0.45)
SRGB_K0 = 0.04045  ##0.055 / (2.4 - 1)
SRGB_P = 12.92  ##get_transfer_function_phi(0.055, 2.4)

standard_illuminants = {
	# 1st level is the standard name => illuminant definitions
	# 2nd level is the illuminant name => CIE XYZ coordinates
	# (Y should always assumed to be 1.0 and is not explicitly defined)
	None: {"E": {"X": 1.00000, "Z": 1.00000}},
	"ASTM E308-01": {"A": {"X": 1.09850, "Z": 0.35585},
					 "C": {"X": 0.98074, "Z": 1.18232},
					 "D50": {"X": 0.96422, "Z": 0.82521},
					 "D55": {"X": 0.95682, "Z": 0.92149},
					 "D65": {"X": 0.95047, "Z": 1.08883},
					 "D75": {"X": 0.94972, "Z": 1.22638},
					 "F2": {"X": 0.99186, "Z": 0.67393},
					 "F7": {"X": 0.95041, "Z": 1.08747},
					 "F11": {"X": 1.00962, "Z": 0.64350}},
	"ICC": {"D50": {"X": 0.9642, "Z": 0.8249},
			"D65": {"X": 0.9505, "Z": 1.0890}},
	"Wyszecki & Stiles": {"A": {"X": 1.09828, "Z": 0.35547},
						  "B": {"X": 0.99072, "Z": 0.85223},
						  "C": {"X": 0.98041, "Z": 1.18103},
						  "D55": {"X": 0.95642, "Z": 0.92085},
						  "D65": {"X": 0.95017, "Z": 1.08813},
						  "D75": {"X": 0.94939, "Z": 1.22558}}
}


def specialpow(a, b):
	"""
	Wrapper for power, Rec. 601/709, SMPTE 240M, sRGB and L* functions
	
	Positive b = power, -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
	-601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
	identical)
	
	"""
	if b >= 0.0:
		# Power curve
		if a < 0.0:
			return -math.pow(-a, b)
		else:
			return math.pow(a, b)
	if a < 0.0:
		signScale = -1.0
		a = -a
	else:
		signScale = 1.0
	if b in (1.0 / -601, 1.0 / -709):
		# XYZ -> RGB, Rec. 601/709 TRC
		if a < REC709_K0 / REC709_P:
			v = a * REC709_P
		else:
			v = 1.099 * math.pow(a, 0.45) - 0.099
	elif b == 1.0 / -240:
		# XYZ -> RGB, SMPTE 240M TRC
		if a < SMPTE240M_K0 / SMPTE240M_P:
			v = a * SMPTE240M_P
		else:
			v = 1.1115 * math.pow(a, 0.45) - 0.1115
	elif b == 1.0 / -3.0:
		# XYZ -> RGB, L* TRC
		if a <= LSTAR_E:
			v = 0.01 * a * LSTAR_K
		else:
			v = 1.16 * math.pow(a, 1.0 / 3.0) - 0.16
	elif b == 1.0 / -2.4:
		# XYZ -> RGB, sRGB TRC
		if a <= SRGB_K0 / SRGB_P:
			v = a * SRGB_P
		else:
			v = 1.055 * math.pow(a, 1.0 / 2.4) - 0.055
	elif b == -2.4:
		# RGB -> XYZ, sRGB TRC
		if a <= SRGB_K0:
			v = a / SRGB_P
		else:
			v = math.pow((a + 0.055) / 1.055, 2.4)
	elif b == -3.0:
		# RGB -> XYZ, L* TRC
		if a <= 0.08:  # E * K * 0.01
			v = 100.0 * a / LSTAR_K
		else:
			v = math.pow((a + 0.16) / 1.16, 3.0)
	elif b == -240:
		# RGB -> XYZ, SMPTE 240M TRC
		if a < SMPTE240M_K0:
			v = a / SMPTE240M_P
		else:
			v = math.pow((0.1115 + a) / 1.1115, 1.0 / 0.45)
	elif b in (-601, -709):
		# RGB -> XYZ, Rec. 601/709 TRC
		if a < REC709_K0:
			v = a / REC709_P
		else:
			v = math.pow((a + .099) / 1.099, 1.0 / 0.45)
	else:
		raise ValueError("Invalid gamma %s" % b)
	return v * signScale


rgb_spaces = {
	# http://brucelindbloom.com/WorkingSpaceInfo.html
	# Adobe RGB: http://www.adobe.com/digitalimag/pdfs/AdobeRGB1998.pdf
	#
	# name              gamma             white  primaries
	#                                     point   Rx      Ry      RY          Gx      Gy      GY          Bx      By      BY
	"Adobe RGB (1998)": (2 + 51 / 256.0,  "D65", (0.6400, 0.3300, 0.297361), (0.2100, 0.7100, 0.627355), (0.1500, 0.0600, 0.075285)),
	"Apple RGB":        (1.8,             "D65", (0.6250, 0.3400, 0.244634), (0.2800, 0.5950, 0.672034), (0.1550, 0.0700, 0.083332)),
	"Best RGB":         (2.2,             "D50", (0.7347, 0.2653, 0.228457), (0.2150, 0.7750, 0.737352), (0.1300, 0.0350, 0.034191)),
	"Beta RGB":         (2.2,             "D50", (0.6888, 0.3112, 0.303273), (0.1986, 0.7551, 0.663786), (0.1265, 0.0352, 0.032941)),
	"Bruce RGB":        (2.2,             "D65", (0.6400, 0.3300, 0.240995), (0.2800, 0.6500, 0.683554), (0.1500, 0.0600, 0.075452)),
	"CIE RGB":          (2.2,             "E",   (0.7350, 0.2650, 0.176204), (0.2740, 0.7170, 0.812985), (0.1670, 0.0090, 0.010811)),
	"ColorMatch RGB":   (1.8,             "D50", (0.6300, 0.3400, 0.274884), (0.2950, 0.6050, 0.658132), (0.1500, 0.0750, 0.066985)),
	"Don RGB 4":        (2.2,             "D50", (0.6960, 0.3000, 0.278350), (0.2150, 0.7650, 0.687970), (0.1300, 0.0350, 0.033680)),
	"ECI RGB":          (1.8,             "D50", (0.6700, 0.3300, 0.320250), (0.2100, 0.7100, 0.602071), (0.1400, 0.0800, 0.077679)),
	"ECI RGB v2":       (-3.0,            "D50", (0.6700, 0.3300, 0.320250), (0.2100, 0.7100, 0.602071), (0.1400, 0.0800, 0.077679)),
	"Ekta Space PS5":   (2.2,             "D50", (0.6950, 0.3050, 0.260629), (0.2600, 0.7000, 0.734946), (0.1100, 0.0050, 0.004425)),
	"NTSC RGB":         (2.2,             "C",   (0.6700, 0.3300, 0.298839), (0.2100, 0.7100, 0.586811), (0.1400, 0.0800, 0.114350)),
	"PAL/SECAM RGB":    (2.2,             "D65", (0.6400, 0.3300, 0.222021), (0.2900, 0.6000, 0.706645), (0.1500, 0.0600, 0.071334)),
	"ProPhoto RGB":     (1.8,             "D50", (0.7347, 0.2653, 0.288040), (0.1596, 0.8404, 0.711874), (0.0366, 0.0001, 0.000086)),
	"Rec. 709 RGB":     (-709,            "D65", (0.6400, 0.3300, 0.212656), (0.3000, 0.6000, 0.715158), (0.1500, 0.0600, 0.072186)),
	"SMPTE-C RGB":      (2.2,             "D65", (0.6300, 0.3400, 0.212395), (0.3100, 0.5950, 0.701049), (0.1550, 0.0700, 0.086556)),
	"SMPTE 240M RGB":   (-240,            "D65", (0.6300, 0.3400, 0.212395), (0.3100, 0.5950, 0.701049), (0.1550, 0.0700, 0.086556)),
	"sRGB":             (-2.4,            "D65", (0.6400, 0.3300, 0.212656), (0.3000, 0.6000, 0.715158), (0.1500, 0.0600, 0.072186)),
	"Wide Gamut RGB":   (2.2,             "D50", (0.7350, 0.2650, 0.258187), (0.1150, 0.8260, 0.724938), (0.1570, 0.0180, 0.016875))
}


def get_cat_matrix(cat="Bradford"):
	if isinstance(cat, basestring):
		cat = cat_matrices[cat]
	if not isinstance(cat, Matrix3x3):
		cat = Matrix3x3(cat)
	return cat


def cbrt(x):
	return math.pow(x, 1.0 / 3.0) if x >= 0 else -math.pow(-x, 1.0 / 3.0)


def XYZ2LMS(X, Y, Z, cat="Bradford"):
	""" Convert from XYZ to cone response domain """
	cat = get_cat_matrix(cat)
	p, y, b = cat * [X, Y, Z]
	return p, y, b


def LMS_wp_adaption_matrix(whitepoint_source=None, 
						   whitepoint_destination=None, 
						   cat="Bradford"):
	""" Prepare a matrix to match the whitepoints in cone response domain """
	# chromatic adaption
	# based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
	# cat = adaption matrix or predefined choice ('CAT02', 'Bradford', 
	# 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
	cat = get_cat_matrix(cat)
	XYZWS = get_whitepoint(whitepoint_source)
	XYZWD = get_whitepoint(whitepoint_destination)
	if XYZWS[1] <= 1.0 and XYZWD[1] > 1.0:
		# make sure the scaling is identical
		XYZWS = [v * 100 for v in XYZWS]
	if XYZWD[1] <= 1.0 and XYZWS[1] > 1.0:
		# make sure the scaling is identical
		XYZWD = [v * 100 for v in XYZWD]
	Ls, Ms, Ss = XYZ2LMS(XYZWS[0], XYZWS[1], XYZWS[2], cat)
	Ld, Md, Sd = XYZ2LMS(XYZWD[0], XYZWD[1], XYZWD[2], cat)
	return Matrix3x3([[Ld/Ls, 0, 0], [0, Md/Ms, 0], [0, 0, Sd/Ss]])


def wp_adaption_matrix(whitepoint_source=None, whitepoint_destination=None, 
					   cat="Bradford"):
	"""
	Prepare a matrix to match the whitepoints in cone response doamin and 
	transform back to XYZ
	
	"""
	# chromatic adaption
	# based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
	# cat = adaption matrix or predefined choice ('CAT02', 'Bradford', 
	# 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
	cat = get_cat_matrix(cat)
	return cat.inverted() * LMS_wp_adaption_matrix(whitepoint_source, 
												   whitepoint_destination, 
												   cat) * cat


def adapt(X, Y, Z, whitepoint_source=None, whitepoint_destination=None, 
		  cat="Bradford"):
	"""
	Transform XYZ under source illuminant to XYZ under destination illuminant
	
	"""
	# chromatic adaption
	# based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
	# cat = adaption matrix or predefined choice ('CAT02', 'Bradford', 
	# 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
	return wp_adaption_matrix(whitepoint_source, whitepoint_destination, 
							  cat) * (X, Y, Z)


def apply_bpc(X, Y, Z, bp_in, bp_out, wp_out="D50"):
	"""
	Apply black point compensation
	
	"""
	wp_out = get_whitepoint(wp_out)
	XYZ = [X, Y, Z]
	for i, v in enumerate(XYZ):
		XYZ[i] = ((wp_out[i] - bp_out[i]) * v - wp_out[i] * (bp_in[i] - bp_out[i])) / (wp_out[i] - bp_in[i])
	return XYZ


def avg(*args):
	return float(sum(args)) / len(args)


def compute_bpc(bp_in, bp_out):
	"""
	Black point compensation. Implemented as a linear scaling in XYZ. 

	Black points should come relative to the white point. Fills and
	returns a matrix/offset element.

	[matrix]*bp_in + offset = bp_out
	[matrix]*D50  + offset = D50

	"""
	# This is a linear scaling in the form ax+b, where
	# a = (bp_out - D50) / (bp_in - D50)
	# b = - D50* (bp_out - bp_in) / (bp_in - D50)
	
	D50 = get_standard_illuminant("D50")

	tx = bp_in[0] - D50[0]
	ty = bp_in[1] - D50[1]
	tz = bp_in[2] - D50[2]

	ax = (bp_out[0] - D50[0]) / tx
	ay = (bp_out[1] - D50[1]) / ty
	az = (bp_out[2] - D50[2]) / tz

	bx = - D50[0] * (bp_out[0] - bp_in[0]) / tx
	by = - D50[1] * (bp_out[1] - bp_in[1]) / ty
	bz = - D50[2] * (bp_out[2] - bp_in[2]) / tz

	matrix = Matrix3x3([[ax, 0,  0],
						[0, ay,  0]
						[0,  0, az]])
	offset = [bx, by, bz]
	return matrix, offset


def delta(L1, a1, b1, L2, a2, b2, method="1976", p1=None, p2=None, p3=None):
		"""
		Compute the delta of two samples

		CIE 1994 & CMC calculation code derived from formulas on
		 www.brucelindbloom.com
		CIE 1994 code uses some alterations seen on
		 www.farbmetrik-gall.de/cielab/korrcielab/cie94.html
		 (see notes in code below)
		CIE 2000 calculation code derived from Excel spreadsheet available at
		 www.ece.rochester.edu/~gsharma/ciede2000
		
		method: either "CIE94", "CMC", "CIE2K" or "CIE76"
		 (default if method is not set)
		
		p1, p2, p3 arguments have different meaning for each calculation method:
		
			CIE 1994: If p1 is not None, calculation will be adjusted for
					  textiles, otherwise graphics arts (default if p1 is not set)
			CMC(l:c): p1 equals l (lightness) weighting factor and p2 equals c
					  (chroma) weighting factor.
					  Commonly used values are CMC(1:1) for perceptability
					  (default if p1 and p2 are not set) and CMC(2:1) for
					  acceptability
			CIE 2000: p1 becomes kL (lightness) weighting factor, p2 becomes
					  kC (chroma) weighting factor and p3 becomes kH (hue)
					  weighting factor (all three default to 1 if not set)

		"""
		if isinstance(method, basestring):
			method = method.lower()
		else:
			method = str(int(method))
		if method in ("94", "1994", "cie94", "cie1994"):
			textiles = p1
			dL = L1 - L2
			C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
			C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
			dC = C1 - C2
			da = a1 - a2
			db = b1 - b2
			dH = math.sqrt(math.pow(da, 2) + math.pow(db, 2) - math.pow(dC, 2))
			SL = 1.0
			K1 = 0.048 if textiles else 0.045
			K2 = 0.014 if textiles else 0.015
			# brucelindbloom.com formula originally used C1 instead of C_,
			# but the results are different from ProfileMaker/MeasureTool 
			# implementation, so use this instead
			# (found on www.farbmetrik-gall.de/cielab/korrcielab/cie94.html)
			C_ = (math.sqrt((1 + (K1 * C1)) * (1 + (K1 * C2))) - 1) / K1
			SC = 1.0 + K1 * C_
			SH = 1.0 + K2 * C_
			KL = 2.0 if textiles else 1.0
			KC = 1.0
			KH = 1.0
			dE = math.sqrt(math.pow(dL / (KL * SL), 2) + math.pow(dC / (KC * SC), 2) + math.pow(dH / (KH * SH), 2))
		elif method in ("cmc(2:1)", "cmc21", "cmc(1:1)", "cmc11", "cmc"):
			if method in ("cmc(2:1)", "cmc21"):
				p1 = 2.0
			l = p1 if isinstance(p1, (float, int)) else 1.0
			c = p2 if isinstance(p2, (float, int)) else 1.0
			dL = L1 - L2
			C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
			C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
			dC = C1 - C2
			da = a1 - a2
			db = b1 - b2
			dH = math.sqrt(math.pow(da, 2) + math.pow(db, 2) - math.pow(dC, 2))
			SL = 0.511 if L1 < 16 else (0.040975 * L1) / (1 + 0.01765 * L1)
			SC = (0.0638 * C1) / (1 + 0.0131 * C1) + 0.638
			F = math.sqrt(math.pow(C1, 4) / (math.pow(C1, 4) + 1900.0))
			H1 = math.degrees(math.atan2(b1, a1)) + (0 if b1 >= 0 else 360.0)
			T = 0.56 + abs(0.2 * math.cos(math.radians(H1 + 168.0))) if 164 <= H1 and H1 <= 345 else 0.36 + abs(0.4 * math.cos(math.radians(H1 + 35)))
			SH = SC * (F * T + 1 - F)
			dE = math.sqrt(math.pow(dL / (l * SL), 2) + math.pow(dC / (c * SC), 2) + math.pow(dH / SH, 2))
		elif method in ("00", "2k", "2000", "cie00", "cie2k", "cie2000"):
			pow25_7 = math.pow(25, 7)
			k_L = p1 if isinstance(p1, (float, int)) else 1.0
			k_C = p2 if isinstance(p2, (float, int)) else 1.0
			k_H = p3 if isinstance(p3, (float, int)) else 1.0
			C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
			C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
			C_avg = avg(C1, C2)
			G = .5 * (1 - math.sqrt(math.pow(C_avg, 7) / (math.pow(C_avg, 7) + pow25_7)))
			L1_ = L1
			a1_ = (1 + G) * a1
			b1_ = b1
			L2_ = L2
			a2_ = (1 + G) * a2
			b2_ = b2
			C1_ = math.sqrt(math.pow(a1_, 2) + math.pow(b1_, 2))
			C2_ = math.sqrt(math.pow(a2_, 2) + math.pow(b2_, 2))
			h1_ = 0 if a1_ == 0 and b1_ == 0 else math.degrees(math.atan2(b1_, a1_)) + (0 if b1_ >= 0 else 360.0)
			h2_ = 0 if a2_ == 0 and b2_ == 0 else math.degrees(math.atan2(b2_, a2_)) + (0 if b2_ >= 0 else 360.0)
			dh_cond = 1.0 if h2_ - h1_ > 180 else (2.0 if h2_ - h1_ < -180 else 0)
			dh_ = h2_ - h1_ if dh_cond == 0 else (h2_ - h1_ - 360.0 if dh_cond == 1 else h2_ + 360.0 - h1_)
			dL_ = L2_ - L1_
			dL = dL_
			dC_ = C2_ - C1_
			dC = dC_
			dH_ = 2 * math.sqrt(C1_ * C2_) * math.sin(math.radians(dh_ / 2.0))
			dH = dH_
			L__avg = avg(L1_, L2_)
			C__avg = avg(C1_, C2_)
			h__avg_cond = 3.0 if C1_ * C2_ == 0 else (0 if abs(h2_ - h1_) <= 180 else (1.0 if h2_ + h1_ < 360 else 2.0))
			h__avg = h1_ + h2_ if h__avg_cond == 3 else (avg(h1_, h2_) if h__avg_cond == 0 else (avg(h1_, h2_) + 180.0 if h__avg_cond == 1 else avg(h1_, h2_) - 180.0))
			AB = math.pow(L__avg - 50.0, 2)  # (L'_ave-50)^2
			S_L = 1 + .015 * AB / math.sqrt(20.0 + AB)
			S_C = 1 + .045 * C__avg
			T = (1 - .17 * math.cos(math.radians(h__avg - 30.0)) + .24 * math.cos(math.radians(2.0 * h__avg)) + .32 * math.cos(math.radians(3.0 * h__avg + 6.0))
				 - .2 * math.cos(math.radians(4 * h__avg - 63.0)))
			S_H = 1 + .015 * C__avg * T
			dTheta = 30.0 * math.exp(-1 * math.pow((h__avg - 275.0) / 25.0, 2))
			R_C = 2.0 * math.sqrt(math.pow(C__avg, 7) / (math.pow(C__avg, 7) + pow25_7))
			R_T = -math.sin(math.radians(2.0 * dTheta)) * R_C
			AJ = dL_ / S_L / k_L  # dL' / k_L / S_L
			AK = dC_ / S_C / k_C  # dC' / k_C / S_C
			AL = dH_ / S_H / k_H  # dH' / k_H / S_H
			dE = math.sqrt(math.pow(AJ, 2) + math.pow(AK, 2) + math.pow(AL, 2) + R_T * AK * AL)
		else:
			# dE 1976
			dL = L1 - L2
			C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
			C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
			dC = C1 - C2
			dH = math.sqrt(math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dC, 2))
			dE = math.sqrt(math.pow(dL, 2) + math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2))
		
		return {"E": dE,
				"L": dL,
				"C": dC,
				"H": dH,
				"a": a1 - a2,
				"b": b1 - b2}


def is_similar_matrix(matrix1, matrix2, digits=3):
	""" Compare two matrices and check if they are the same
	up to n digits after the decimal point """
	return matrix1.rounded(digits) == matrix2.rounded(digits)


def get_gamma(values, scale=1.0, vmin=0.0, vmax=1.0, average=True, least_squares=False):
	""" Return average or least squares gamma or a list of gamma values """
	if least_squares:
		logxy = []
		logx2 = []
	else:
		gammas = []
	vmin /= scale
	vmax /= scale
	for x, y in values:
		x /= scale
		y = (y / scale - vmin) * (vmax + vmin)
		if x > 0 and x < 1 and y > 0:
			if least_squares:
				logxy.append(math.log(x) * math.log(y))
				logx2.append(math.pow(math.log(x), 2))
			else:
				gammas.append(math.log(y) / math.log(x))
	if average or least_squares:
		if least_squares:
			if not logxy or not logx2:
				return 0
			return sum(logxy) / sum(logx2)
		else:
			if not gammas:
				return 0
			return sum(gammas) / len(gammas)
	else:
		return gammas


def guess_cat(chad, whitepoint_source=None, whitepoint_destination=None):
	""" Try and guess the chromatic adaption transform used in a chromatic 
	adaption matrix as found in an ICC profile's 'chad' tag """
	if chad == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]:
		return "None"
	for cat in cat_matrices:
		if is_similar_matrix((chad * cat_matrices[cat].inverted() * 
							  LMS_wp_adaption_matrix(whitepoint_destination, 
													 whitepoint_source, 
													 cat)).inverted(), 
							 cat_matrices[cat], 2):
			return cat


def CIEDCCT2xyY(T, scale=1.0):
	"""
	Convert from CIE correlated daylight temperature to xyY.
	
	T = temperature in Kelvin.
	
	Based on formula from http://brucelindbloom.com/Eqn_T_to_xy.html
	
	"""
	if isinstance(T, basestring):
		# Assume standard illuminant, e.g. "D50"
		return XYZ2xyY(*get_standard_illuminant(T, scale=scale))
	if 4000 <= T and T <= 7000:
		xD = (((-4.607 * math.pow(10, 9)) / math.pow(T, 3))
			+ ((2.9678 * math.pow(10, 6)) / math.pow(T, 2))
			+ ((0.09911 * math.pow(10, 3)) / T)
			+ 0.244063)
	elif 7000 < T and T <= 25000:
		xD = (((-2.0064 * math.pow(10, 9)) / math.pow(T, 3))
			+ ((1.9018 * math.pow(10, 6)) / math.pow(T, 2))
			+ ((0.24748 * math.pow(10, 3)) / T)
			+ 0.237040)
	else:
		return None
	yD = -3 * math.pow(xD, 2) + 2.87 * xD - 0.275
	return xD, yD, scale


def CIEDCCT2XYZ(T, scale=1.0):
	"""
	Convert from CIE correlated daylight temperature to XYZ.
	
	T = temperature in Kelvin.
	
	"""
	return xyY2XYZ(*CIEDCCT2xyY(T, scale))


def get_DBL_MIN():
	t = "0.0"
	i = 10
	n = 0
	while True:
		if i > 1:
			i -= 1
		else:
			t += "0"
			i = 9
		if float(t + str(i)) == 0.0:
			if n > 1:
				break
			n += 1
			t += str(i)
			i = 10
		else:
			if n > 1:
				n -= 1
			DBL_MIN = float(t + str(i))
	return DBL_MIN


DBL_MIN = get_DBL_MIN()


def Lab2RGB(L, a, b, rgb_space=None, scale=1.0, round_=False, clamp=True):
	""" Convert from Lab to RGB """
	X, Y, Z = Lab2XYZ(L, a, b)
	return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def Lab2XYZ(L, a, b, whitepoint=None, scale=1.0):
	"""
	Convert from Lab to XYZ.
	
	The input L value needs to be in the nominal range [0.0, 100.0] and 
	other input values scaled accordingly.
	The output XYZ values are in the nominal range [0.0, scale].
	
	whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or 
	color temperature as float or int. Defaults to D50 if not set.
	
	Based on formula from http://brucelindbloom.com/Eqn_Lab_to_XYZ.html
	
	"""
	fy = (L + 16) / 116.0
	fx = a / 500.0 + fy
	fz = fy - b / 200.0
	
	if math.pow(fx, 3.0) > LSTAR_E:
		xr = math.pow(fx, 3.0)
	else:
		xr = (116.0 * fx - 16) / LSTAR_K
	
	if L > LSTAR_K * LSTAR_E:
		yr = math.pow((L + 16) / 116.0, 3.0)
	else:
		yr = L / LSTAR_K
	
	if math.pow(fz, 3.0) > LSTAR_E:
		zr = math.pow(fz, 3.0)
	else:
		zr = (116.0 * fz - 16) / LSTAR_K
	
	Xr, Yr, Zr = get_whitepoint(whitepoint, scale)
	
	X = xr * Xr
	Y = yr * Yr
	Z = zr * Zr
	
	return X, Y, Z


def Lab2xyY(L, a, b, whitepoint=None, scale=1.0):
	X, Y, Z = Lab2XYZ(L, a, b, whitepoint, scale)
	return XYZ2xyY(X, Y, Z, whitepoint)


def Luv2RGB(L, u, v, rgb_space=None, scale=1.0, round_=False, clamp=True):
	""" Convert from Luv to RGB """
	X, Y, Z = Luv2XYZ(L, u, v)
	return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def u_v_2xy(u, v):
	""" Convert from u'v' to xy """
	
	x = (9.0 * u) / (6 * u - 16 * v + 12)
	y = (4 * v) / (6 * u - 16 * v + 12)
	
	return x, y


def Luv2XYZ(L, u, v, whitepoint=None, scale=1.0):
	""" Convert from Luv to XYZ """
	
	Xr, Yr, Zr = get_whitepoint(whitepoint)
	
	Y = math.pow((L + 16.0) / 116.0, 3) if L > LSTAR_K * LSTAR_E else L / LSTAR_K
	
	uo = (4.0 * Xr) / (Xr + 15.0 * Yr + 3.0 * Zr)
	vo = (9.0 * Yr) / (Xr + 15.0 * Yr + 3.0 * Zr)
	
	a = (1.0 / 3.0) * (((52.0 * L) / (u + 13 * L * uo)) -1)
	b = -5.0 * Y
	c = -(1.0 / 3.0)
	d = Y * (((39.0 * L) / (v + 13 * L * vo)) - 5)
	
	X = (d - b) / (a - c)
	Z = X * a + b
	
	return tuple([v * scale for v in X, Y, Z])


def RGB2XYZ(R, G, B, rgb_space=None, scale=1.0):
	"""
	Convert from RGB to XYZ.
	
	Use optional RGB colorspace definition, which can be a named colorspace 
	(e.g. "CIE RGB") or must be a tuple in the following format:
	
	(gamma, whitepoint, red, green, blue)
	
	whitepoint can be a string (e.g. "D50"), a tuple of XYZ coordinates,
	or a color temperatur in degrees K (float or int). Gamma should be a float.
	The RGB primaries red, green, blue should be lists or tuples of xyY 
	coordinates (only x and y will be used, so Y can be zero or None).
	
	If no colorspace is given, it defaults to sRGB.
	
	Based on formula from http://brucelindbloom.com/Eqn_RGB_to_XYZ.html
	
	Implementation Notes:
	1. The transformation matrix [M] is calculated from the RGB reference 
	   primaries as discussed here:
	   http://brucelindbloom.com/Eqn_RGB_XYZ_Matrix.html
	2. The gamma values for many common RGB color spaces may be found here:
	   http://brucelindbloom.com/WorkingSpaceInfo.html#Specifications
	3. Your input RGB values may need to be scaled before using the above. 
	   For example, if your values are in the range [0, 255], you must first 
	   divide each by 255.0.
	4. The output XYZ values are in the nominal range [0.0, scale].
	5. The XYZ values will be relative to the same reference white as the 
	   RGB system. If you want XYZ relative to a different reference white, 
	   you must apply a chromatic adaptation transform 
	   [http://brucelindbloom.com/Eqn_ChromAdapt.html] to the XYZ color to 
	   convert it from the reference white of the RGB system to the desired 
	   reference white.
	6. Sometimes the more complicated special case of sRGB shown above is 
	   replaced by a "simplified" version using a straight gamma function 
	   with gamma = 2.2.
	   
	"""
	gamma, whitepoint, rxyY, gxyY, bxyY, matrix = get_rgb_space(rgb_space)
	RGB = [R, G, B]
	for i, v in enumerate(RGB):
		RGB[i] = specialpow(v, gamma)
	XYZ = matrix * RGB
	return tuple(v * scale for v in XYZ)


def rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, whitepoint=None, scale=1.0):
	""" Create and return an RGB to XYZ matrix. """
	whitepoint = get_whitepoint(whitepoint, scale)
	Xr, Yr, Zr = xyY2XYZ(rx, ry, scale)
	Xg, Yg, Zg = xyY2XYZ(gx, gy, scale)
	Xb, Yb, Zb = xyY2XYZ(bx, by, scale)
	Sr, Sg, Sb = Matrix3x3(((Xr, Xg, Xb),
							(Yr, Yg, Yb),
							(Zr, Zg, Zb))).inverted() * whitepoint
	return Matrix3x3(((Sr * Xr, Sg * Xg, Sb * Xb),
					  (Sr * Yr, Sg * Yg, Sb * Yb),
					  (Sr * Zr, Sg * Zg, Sb * Zb)))


def get_rgb_space(rgb_space=None, scale=1.0):
	""" Return gamma, whitepoint, primaries and RGB -> XYZ matrix """
	if not rgb_space:
		rgb_space = "sRGB"
	if isinstance(rgb_space, basestring):
		rgb_space = rgb_spaces[rgb_space]
	cachehash = tuple(rgb_space), scale
	cache = get_rgb_space.cache.get(cachehash, None)
	if cache:
		return cache
	gamma = rgb_space[0] or rgb_spaces["sRGB"][0]
	whitepoint = get_whitepoint(rgb_space[1] or rgb_spaces["sRGB"][1], scale)
	rx, ry, rY = rgb_space[2] or rgb_spaces["sRGB"][2]
	gx, gy, gY = rgb_space[3] or rgb_spaces["sRGB"][3]
	bx, by, bY = rgb_space[4] or rgb_spaces["sRGB"][4]
	matrix = rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, whitepoint, scale)
	rgb_space = gamma, whitepoint, (rx, ry, rY), (gx, gy, gY), (bx, by, bY), matrix
	get_rgb_space.cache[cachehash] = rgb_space
	return rgb_space


get_rgb_space.cache = {}


def get_standard_illuminant(illuminant_name="D50",
							priority=("ICC", "ASTM E308-01", "Wyszecki & Stiles", None),
							scale=1.0):
	""" Return a standard illuminant as XYZ coordinates. """
	cachehash = illuminant_name, tuple(priority), scale
	cache = get_standard_illuminant.cache.get(cachehash, None)
	if cache:
		return cache
	illuminant = None
	for standard_name in priority:
		if not standard_name in standard_illuminants:
			raise ValueError('Unrecognized standard "%s"' % standard_name)
		illuminant = standard_illuminants.get(standard_name).get(illuminant_name.upper(), 
																 None)
		if illuminant:
			illuminant = illuminant["X"] * scale, 1.0 * scale, illuminant["Z"] * scale
			get_standard_illuminant.cache[cachehash] = illuminant
			return illuminant
	raise ValueError('Unrecognized illuminant "%s"' % illuminant_name)


get_standard_illuminant.cache = {}


def get_whitepoint(whitepoint=None, scale=1.0):
	""" Return a whitepoint as XYZ coordinates """
	if isinstance(whitepoint, (list, tuple)):
		return whitepoint
	if not whitepoint:
		whitepoint = "D50"
	cachehash = whitepoint, scale
	cache = get_whitepoint.cache.get(cachehash, None)
	if cache:
		return cache
	if isinstance(whitepoint, basestring):
		whitepoint = get_standard_illuminant(whitepoint)
	elif isinstance(whitepoint, (float, int)):
		whitepoint = CIEDCCT2XYZ(whitepoint)
	if scale > 1.0 and whitepoint[1] == 100:
		scale = 1.0
	if whitepoint[1] * scale > 100:
		ValueError("Y value out of range after scaling: %s" % (whitepoint[1] * scale))
	whitepoint = tuple(v * scale for v in whitepoint)
	get_whitepoint.cache[cachehash] = whitepoint
	return whitepoint


get_whitepoint.cache = {}


def planckianCT2XYZ(T, scale=1.0):
	""" Convert from planckian temperature to XYZ.
	
	T = temperature in Kelvin.
	
	"""
	return xyY2XYZ(*planckianCT2xyY(T, scale))


def planckianCT2xyY(T, scale=1.0):
	""" Convert from planckian temperature to xyY.
	
	T = temperature in Kelvin.
	
	Formula from http://en.wikipedia.org/wiki/Planckian_locus
	
	"""
	if   1667 <= T and T <= 4000:
		x = (  -0.2661239 * (math.pow(10, 9) / math.pow(T, 3))
			 -  0.2343580 * (math.pow(10, 6) / math.pow(T, 2))
			 +  0.8776956 * (math.pow(10, 3) / T)
			 +  0.179910)
	elif 4000 <= T and T <= 25000:
		x = (  -3.0258469 * (math.pow(10, 9) / math.pow(T, 3))
			 +  2.1070379 * (math.pow(10, 6) / math.pow(T, 2))
			 +  0.2226347 * (math.pow(10, 3) / T)
			 +  0.24039)
	else:
		return None
	if   1667 <= T and T <= 2222:
		y = (  -1.1063814  * math.pow(x, 3)
			 -  1.34811020 * math.pow(x, 2)
			 +  2.18555832 * x
			 -  0.20219683)
	elif 2222 <= T and T <= 4000:
		y = (  -0.9549476  * math.pow(x, 3)
			 -  1.37418593 * math.pow(x, 2)
			 +  2.09137015 * x
			 -  0.16748867)
	elif 4000 <= T and T <= 25000:
		y = (   3.0817580  * math.pow(x, 3)
			 -  5.87338670 * math.pow(x, 2)
			 +  3.75112997 * x
			 -  0.37001483)
	return x, y, scale


def xyY2CCT(x, y, Y=1.0):
	""" Convert from xyY to correlated color temperature. """
	return XYZ2CCT(*xyY2XYZ(x, y, Y))


def xyY2Lab(x, y, Y=1.0, whitepoint=None):
	X, Y, Z = xyY2XYZ(x, y, Y)
	return XYZ2Lab(X, Y, Z, whitepoint)


def xyY2RGB(x, y, Y, rgb_space=None, scale=1.0, round_=False, clamp=True):
	""" Convert from xyY to RGB """
	X, Y, Z = xyY2XYZ(x, y, Y)
	return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def xyY2XYZ(x, y, Y=1.0):
	"""
	Convert from xyY to XYZ.
	
	Based on formula from http://brucelindbloom.com/Eqn_xyY_to_XYZ.html
	
	Implementation Notes:
	1. Watch out for the case where y = 0. In that case, X = Y = Z = 0 is 
	   returned.
	2. The output XYZ values are in the nominal range [0.0, Y[xyY]].
	
	"""
	if y == 0:
		return 0, 0, 0
	X = (x * Y) / y
	Z = ((1 - x - y) * Y) / y
	return X, Y, Z


def LERP(a,b,c):
	"""
	LERP(a,b,c) = linear interpolation macro.
	
	Is 'a' when c == 0.0 and 'b' when c == 1.0
	
	"""
	return (b - a) * c + a


def XYZ2CCT(X, Y, Z):
	"""
	Convert from XYZ to correlated color temperature.
	
	Derived from ANSI C implementation by Bruce Lindbloom
	http://brucelindbloom.com/Eqn_XYZ_to_T.html
	
	Return: correlated color temperature if successful, else None.
	
	Description:
	This is an implementation of Robertson's method of computing the 
	correlated color temperature of an XYZ color. It can compute correlated 
	color temperatures in the range [1666.7K, infinity].
	
	Reference:
	"Color Science: Concepts and Methods, Quantitative Data and Formulae", 
	Second Edition, Gunter Wyszecki and W. S. Stiles, John Wiley & Sons, 
	1982, pp. 227, 228.
	
	"""
	rt = [       # reciprocal temperature (K)
		 DBL_MIN,  10.0e-6,  20.0e-6,  30.0e-6,  40.0e-6,  50.0e-6,
		 60.0e-6,  70.0e-6,  80.0e-6,  90.0e-6, 100.0e-6, 125.0e-6,
		150.0e-6, 175.0e-6, 200.0e-6, 225.0e-6, 250.0e-6, 275.0e-6,
		300.0e-6, 325.0e-6, 350.0e-6, 375.0e-6, 400.0e-6, 425.0e-6,
		450.0e-6, 475.0e-6, 500.0e-6, 525.0e-6, 550.0e-6, 575.0e-6,
		600.0e-6
	]
	uvt = [
		[0.18006, 0.26352, -0.24341],
		[0.18066, 0.26589, -0.25479],
		[0.18133, 0.26846, -0.26876],
		[0.18208, 0.27119, -0.28539],
		[0.18293, 0.27407, -0.30470],
		[0.18388, 0.27709, -0.32675],
		[0.18494, 0.28021, -0.35156],
		[0.18611, 0.28342, -0.37915],
		[0.18740, 0.28668, -0.40955],
		[0.18880, 0.28997, -0.44278],
		[0.19032, 0.29326, -0.47888],
		[0.19462, 0.30141, -0.58204],
		[0.19962, 0.30921, -0.70471],
		[0.20525, 0.31647, -0.84901],
		[0.21142, 0.32312, -1.0182],
		[0.21807, 0.32909, -1.2168],
		[0.22511, 0.33439, -1.4512],
		[0.23247, 0.33904, -1.7298],
		[0.24010, 0.34308, -2.0637],
		[0.24792, 0.34655, -2.4681],	# Note: 0.24792 is a corrected value 
										# for the error found in W&S as 0.24702
		[0.25591, 0.34951, -2.9641],
		[0.26400, 0.35200, -3.5814],
		[0.27218, 0.35407, -4.3633],
		[0.28039, 0.35577, -5.3762],
		[0.28863, 0.35714, -6.7262],
		[0.29685, 0.35823, -8.5955],
		[0.30505, 0.35907, -11.324],
		[0.31320, 0.35968, -15.628],
		[0.32129, 0.36011, -23.325],
		[0.32931, 0.36038, -40.770],
		[0.33724, 0.36051, -116.45]
	]
	if ((X < 1.0e-20) and (Y < 1.0e-20) and (Z < 1.0e-20)):
		return None	# protect against possible divide-by-zero failure
	us = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
	vs = (6.0 * Y) / (X + 15.0 * Y + 3.0 * Z)
	dm = 0.0
	i = 0
	while i < 31:
		di = (vs - uvt[i][1]) - uvt[i][2] * (us - uvt[i][0])
		if i > 0 and ((di < 0.0 and dm >= 0.0) or (di >= 0.0 and dm < 0.0)):
			break	# found lines bounding (us, vs) : i-1 and i
		dm = di
		i += 1
	if (i == 31):
		# bad XYZ input, color temp would be less than minimum of 1666.7 
		# degrees, or too far towards blue
		return None
	di = di / math.sqrt(1.0 + uvt[i    ][2] * uvt[i    ][2])
	dm = dm / math.sqrt(1.0 + uvt[i - 1][2] * uvt[i - 1][2])
	p = dm / (dm - di)	# p = interpolation parameter, 0.0 : i-1, 1.0 : i
	p = 1.0 / (LERP(rt[i - 1], rt[i], p))
	return p


def XYZ2Lab(X, Y, Z, whitepoint=None):
	"""
	Convert from XYZ to Lab.
	
	The input Y value needs to be in the nominal range [0.0, 100.0] and 
	other input values scaled accordingly.
	The output L value is in the nominal range [0.0, 100.0].
	
	whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or 
	color temperature as float or int. Defaults to D50 if not set.
	
	Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_Lab.html
	
	"""
	Xr, Yr, Zr = get_whitepoint(whitepoint, 100)

	xr = X / Xr
	yr = Y / Yr
	zr = Z / Zr
	fx = cbrt(xr) if xr > LSTAR_E else (LSTAR_K * xr + 16) / 116.0
	fy = cbrt(yr) if yr > LSTAR_E else (LSTAR_K * yr + 16) / 116.0
	fz = cbrt(zr) if zr > LSTAR_E else (LSTAR_K * zr + 16) / 116.0
	L = 116 * fy - 16
	a = 500 * (fx - fy)
	b = 200 * (fy - fz)
	
	return L, a, b


def XYZ2Lu_v_(X, Y, Z, whitepoint=None):
	""" Convert from XYZ to CIE Lu'v' """
	
	Xn, Yn, Zn = get_whitepoint(whitepoint, 100)
	
	if Y / Yn <= math.pow(6.0 / 29.0, 3):
		L = math.pow(29.0 / 3.0, 3)
	else:
		L = 116.0 * math.pow(Y / Yn, 1.0 / 3.0) - 16.0
	
	u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
	v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)
	
	return L, u_, v_


def XYZ2Luv(X, Y, Z, whitepoint=None):
	""" Convert from XYZ to Luv """
	Xr, Yr, Zr = get_whitepoint(whitepoint, 100)
	
	yr = Y / Yr
	
	L = 116.0 * cbrt(yr) - 16.0 if yr > LSTAR_E else LSTAR_K * yr
	
	u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
	v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)
	
	u_r = (4.0 * Xr) / (Xr + 15.0 * Yr + 3.0 * Zr)
	v_r = (9.0 * Yr) / (Xr + 15.0 * Yr + 3.0 * Zr)
	
	u = 13.0 * L * (u_ - u_r)
	v = 13.0 * L * (v_ - v_r)
	
	return L, u, v


def XYZ2RGB(X, Y, Z, rgb_space=None, scale=1.0, round_=False, clamp=True):
	"""
	Convert from XYZ to RGB.
	
	Use optional RGB colorspace definition, which can be a named colorspace 
	(e.g. "CIE RGB") or must be a tuple in the following format:
	
	(gamma, whitepoint, red, green, blue)
	
	whitepoint can be a string (e.g. "D50"), a tuple of XYZ coordinates,
	or a color temperatur in degrees K (float or int). Gamma should be a float.
	The RGB primaries red, green, blue should be lists or tuples of xyY 
	coordinates (only x and y will be used, so Y can be zero or None).
	
	If no colorspace is given, it defaults to sRGB.
	
	Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_RGB.html
	
	Implementation Notes:
	1. The transformation matrix [M] is calculated from the RGB reference 
	   primaries as discussed here:
	   http://brucelindbloom.com/Eqn_RGB_XYZ_Matrix.html
	2. gamma is the gamma value of the RGB color system used. Many common ones 
	   may be found here:
	   http://brucelindbloom.com/WorkingSpaceInfo.html#Specifications
	3. The output RGB values are in the nominal range [0.0, scale].
	4. If the input XYZ color is not relative to the same reference white as 
	   the RGB system, you must first apply a chromatic adaptation transform 
	   [http://brucelindbloom.com/Eqn_ChromAdapt.html] to the XYZ color to 
	   convert it from its own reference white to the reference white of the 
	   RGB system.
	5. Sometimes the more complicated special case of sRGB shown above is 
	   replaced by a "simplified" version using a straight gamma function with 
	   gamma = 2.2.
	
	"""
	gamma, whitepoint, rxyY, gxyY, bxyY, matrix = get_rgb_space(rgb_space)
	RGB = matrix.inverted() * [X, Y, Z]
	for i, v in enumerate(RGB):
		RGB[i] = specialpow(v, 1.0 / gamma)
		if clamp:
			RGB[i] = min(1.0, max(0.0, RGB[i]))
		RGB[i] *= scale
		if round_ is not False:
			RGB[i] = round(RGB[i], round_)
	return RGB


def XYZ2xyY(X, Y, Z, whitepoint=None):
	"""
	Convert from XYZ to xyY.
	
	Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_xyY.html
	
	Implementation Notes:
	1. Watch out for black, where X = Y = Z = 0. In that case, x and y are set 
	   to the chromaticity coordinates of the reference whitepoint.
	2. The output Y value is in the nominal range [0.0, Y[XYZ]].
	
	"""
	if X + Y + Z == 0:
		# We can't check for X == Y == Z == 0 because they may actually add up
		# to 0, thus resulting in ZeroDivisionError later
		x, y, Y = XYZ2xyY(*get_whitepoint(whitepoint))
		return x, y, 0.0
	x = X / (X + Y + Z)
	y = Y / (X + Y + Z)
	return x, y, Y


def xy_CCT_delta(x, y, daylight=True, method=2000):
	""" Return CCT and delta to locus """
	cct = xyY2CCT(x, y)
	d = None
	if cct:
		locus = None
		if daylight:
			# Daylight locus
			if 4000 <= cct <= 25000:
				locus = CIEDCCT2XYZ(cct, 100.0)
		else:
			# Planckian locus
			if 1667 <= cct <= 25000:
				locus = planckianCT2XYZ(cct, 100.0)
		if locus:
			L1, a1, b1 = xyY2Lab(x, y, 100.0)
			L2, a2, b2 = XYZ2Lab(*locus)
			d = delta(L1, a1, b1, L2, a2, b2, method)
	return cct, d


class Matrix3x3(list):
	
	""" Simple 3x3 matrix """
	
	def __init__(self, matrix=None):
		if matrix:
			self.update(matrix)
	
	def update(self, matrix):
		if len(matrix) != 3:
			raise ValueError('Invalid number of rows for 3x3 matrix: %i' % len(matrix))
		while len(self):
			self.pop()
		for row in matrix:
			if len(row) != 3:
				raise ValueError('Invalid number of columns for 3x3 matrix: %i' % len(row))
			self.append([])
			for column in row:
				self[-1].append(column)
	
	def __add__(self, matrix):
		instance = self.__class__()
		instance.update([[self[0][0] + matrix[0][0],
								self[0][1] + matrix[0][1],
								self[0][2] + matrix[0][2]],
							   [self[1][0] + matrix[1][0],
								self[1][1] + matrix[1][1],
								self[1][2] + matrix[1][2]],
							   [self[2][0] + matrix[2][0],
								self[2][1] + matrix[2][1],
								self[2][2] + matrix[2][2]]])
		return instance
	
	def __iadd__(self, matrix):
		# inplace
		self.update(self.__add__(matrix))
		return self
	
	def __imul__(self, matrix):
		# inplace
		self.update(self.__mul__(matrix))
		return self
	
	def __mul__(self, matrix):
		if not isinstance(matrix[0], (list, tuple)):
			return [matrix[0] * self[0][0] + matrix[1] * self[0][1] + matrix[2] * self[0][2],
					matrix[0] * self[1][0] + matrix[1] * self[1][1] + matrix[2] * self[1][2],
					matrix[0] * self[2][0] + matrix[1] * self[2][1] + matrix[2] * self[2][2]]
		instance = self.__class__()
		instance.update([[self[0][0]*matrix[0][0] + self[0][1]*matrix[1][0] + self[0][2]*matrix[2][0],
								self[0][0]*matrix[0][1] + self[0][1]*matrix[1][1] + self[0][2]*matrix[2][1],
								self[0][0]*matrix[0][2] + self[0][1]*matrix[1][2] + self[0][2]*matrix[2][2]],
							   [self[1][0]*matrix[0][0] + self[1][1]*matrix[1][0] + self[1][2]*matrix[2][0],
								self[1][0]*matrix[0][1] + self[1][1]*matrix[1][1] + self[1][2]*matrix[2][1],
								self[1][0]*matrix[0][2] + self[1][1]*matrix[1][2] + self[1][2]*matrix[2][2]],
							   [self[2][0]*matrix[0][0] + self[2][1]*matrix[1][0] + self[2][2]*matrix[2][0],
								self[2][0]*matrix[0][1] + self[2][1]*matrix[1][1] + self[2][2]*matrix[2][1],
								self[2][0]*matrix[0][2] + self[2][1]*matrix[1][2] + self[2][2]*matrix[2][2]]])
		return instance
	
	def adjoint(self):
		return self.cofactors().transposed()
	
	def cofactors(self):
		instance = self.__class__()
		instance.update([[(self[1][1]*self[2][2] - self[1][2]*self[2][1]),
								-1 * (self[1][0]*self[2][2] - self[1][2]*self[2][0]),
								(self[1][0]*self[2][1] - self[1][1]*self[2][0])],
							   [-1 * (self[0][1]*self[2][2] - self[0][2]*self[2][1]),
								(self[0][0]*self[2][2] - self[0][2]*self[2][0]),
								-1 * (self[0][0]*self[2][1] -self[0][1]*self[2][0])],
							   [(self[0][1]*self[1][2] - self[0][2]*self[1][1]),
								-1 * (self[0][0]*self[1][2] - self[1][0]*self[0][2]),
								(self[0][0]*self[1][1] - self[0][1]*self[1][0])]])
		return instance
	
	def determinant(self):
		return ((self[0][0]*self[1][1]*self[2][2] + 
				 self[1][0]*self[2][1]*self[0][2] + 
				 self[0][1]*self[1][2]*self[2][0]) - 
				(self[2][0]*self[1][1]*self[0][2] + 
				 self[1][0]*self[0][1]*self[2][2] + 
				 self[2][1]*self[1][2]*self[0][0]))
	
	def invert(self):
		# inplace
		self.update(self.inverted())
	
	def inverted(self):
		determinant = self.determinant()
		matrix = self.adjoint()
		instance = self.__class__()
		instance.update([[matrix[0][0] / determinant,
								matrix[0][1] / determinant,
								matrix[0][2] / determinant],
							   [matrix[1][0] / determinant,
								matrix[1][1] / determinant,
								matrix[1][2] / determinant],
							   [matrix[2][0] / determinant,
								matrix[2][1] / determinant,
								matrix[2][2] / determinant]])
		return instance
	
	def rounded(self, digits=3):
		matrix = self.__class__()
		for row in self:
			matrix.append([])
			for column in row:
				matrix[-1].append(round(column, digits))
		return matrix
								
	def transpose(self):
		self.update(self.transposed())
	
	def transposed(self):
		instance = self.__class__()
		instance.update([[self[0][0], self[1][0], self[2][0]],
							   [self[0][1], self[1][1], self[2][1]],
							   [self[0][2], self[1][2], self[2][2]]])
		return instance


class NumberTuple(tuple):
	
	def __repr__(self):
		return "(%s)" % ", ".join(str(value) for value in self)
	
	def round(self, digits=4):
		return self.__class__(round(value, digits) for value in self)


# Chromatic adaption transform matrices
# Bradford, von Kries (= HPE normalized to D65) from http://brucelindbloom.com/Eqn_ChromAdapt.html
# CAT02 from http://en.wikipedia.org/wiki/CIECAM02#CAT02
# HPE normalized to illuminant E, CAT97s from http://en.wikipedia.org/wiki/LMS_color_space#CAT97s
# CMCCAT97 from 'Performance Of Five Chromatic Adaptation Transforms Using 
# Large Number Of Color Patches', http://hrcak.srce.hr/file/95370
# CMCCAT2000, Sharp from 'Computational colour science using MATLAB'
# ISBN 0470845627, http://books.google.com/books?isbn=0470845627
# Cross-verification of the matrix numbers has been done using various sources,
# most notably 'Chromatic Adaptation Performance of Different RGB Sensors'
# http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.14.918&rep=rep1&type=pdf
cat_matrices = {"Bradford": Matrix3x3([[ 0.89510,  0.26640, -0.16140],
									   [-0.75020,  1.71350,  0.03670],
									   [ 0.03890, -0.06850,  1.02960]]),
				"CAT02": Matrix3x3([[ 0.7328,  0.4296, -0.1624],
									[-0.7036,  1.6975,  0.0061],
									[ 0.0030,  0.0136,  0.9834]]),
				"CAT97s": Matrix3x3([[ 0.8562,  0.3372, -0.1934],
									 [-0.8360,  1.8327,  0.0033],
									 [ 0.0357, -0.0469,  1.0112]]),
				"CMCCAT97": Matrix3x3([[ 0.8951, -0.7502,  0.0389],
									   [ 0.2664,  1.7135,  0.0685],
									   [-0.1614,  0.0367,  1.0296]]),
				"CMCCAT2000": Matrix3x3([[ 0.7982,  0.3389, -0.1371],
										 [-0.5918,  1.5512,  0.0406],
										 [ 0.0008,  0.0239,  0.9753]]),
				# Hunt-Pointer-Estevez, equal-energy illuminant 
				"HPE normalized to illuminant E": Matrix3x3([[ 0.38971, 0.68898, -0.07868],
								  [-0.22981, 1.18340,  0.04641],
								  [ 0.00000, 0.00000,  1.00000]]),
				# Süsstrunk et al.15 optimized spectrally sharpened matrix
				"Sharp": Matrix3x3([[ 1.2694, -0.0988, -0.1706],
									[-0.8364,  1.8006,  0.0357],
									[ 0.0297, -0.0315,  1.0018]]),
				# 'Von Kries' as found on Bruce Lindbloom's site: 
				# Hunt-Pointer-Estevez normalized to D65
				# (maybe I should call it that instead of 'Von Kries'
				# to avoid ambiguity?)
				"HPE normalized to illuminant D65": Matrix3x3([[ 0.40024,  0.70760, -0.08081],
										[-0.22630,  1.16532,  0.04570],
										[ 0.00000,  0.00000,  0.91822]]),
				"XYZ scaling": Matrix3x3([[1, 0, 0],
										  [0, 1, 0],
										  [0, 0, 1]])}


def test():
	for i in range(4):
		if i == 0:
			wp = "native"
		elif i == 1:
			wp = "D50"
			XYZ = get_standard_illuminant(wp)
		elif i == 2:
			wp = "D65"
			XYZ = get_standard_illuminant(wp)
		elif i == 3:
			XYZ = get_standard_illuminant("D65", ("ASTM E308-01", ))
			wp = " ".join([str(v) for v in XYZ])
		print ("RGB and corresponding XYZ (nominal range 0.0 - 1.0) with "
			   "whitepoint %s" % wp)
		for name in rgb_spaces:
			spc = rgb_spaces[name]
			if i == 0:
				XYZ = CIEDCCT2XYZ(spc[1])
			spc = spc[0], XYZ, spc[2], spc[3], spc[4]
			print "%s 1.0, 1.0, 1.0 = XYZ" % name, \
				[str(round(v, 4)) for v in RGB2XYZ(1.0, 1.0, 1.0, spc)]
			print "%s 1.0, 0.0, 0.0 = XYZ" % name, \
				[str(round(v, 4)) for v in RGB2XYZ(1.0, 0.0, 0.0, spc)]
			print "%s 0.0, 1.0, 0.0 = XYZ" % name, \
				[str(round(v, 4)) for v in RGB2XYZ(0.0, 1.0, 0.0, spc)]
			print "%s 0.0, 0.0, 1.0 = XYZ" % name, \
				[str(round(v, 4)) for v in RGB2XYZ(0.0, 0.0, 1.0, spc)]
		print ""

if __name__ == '__main__':
	test()