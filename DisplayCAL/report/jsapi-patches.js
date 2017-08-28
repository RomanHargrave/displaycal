function sortNumber(a, b) {
	return a - b;
};
jsapi.array.flat = function(a) {
	var r = [];
	for (var i = 0; i < a.length; i ++) {
		if (a[i] != null && a[i].constructor == Array) r = r.concat(jsapi.array.flat(a[i]));
		else r.push(a[i])
	};
	return r
};
jsapi.array.flat._args = [Array];
jsapi.math.median = function () {
	// http://en.wikipedia.org/wiki/Median
	var a = jsapi.array.flat(arguments), median,
		sorted = a.sort(sortNumber), half = sorted.length / 2;
	if (sorted.length % 2 == 0) median = (sorted[half - 1] + sorted[half]) / 2;
	else median = sorted[Math.floor(half)];
	return median
};
jsapi.math.mad = function () {
	// http://en.wikipedia.org/wiki/Median_absolute_deviation
	var a = jsapi.array.flat(arguments), median = jsapi.math.median(a),
		sorted = a.sort(sortNumber);
	for (var i = 0; i < sorted.length; i++) 
		sorted[i] = Math.abs(sorted[i] - median);
	return jsapi.math.median(sorted);
};
jsapi.math.stddev = function () {
	// http://en.wikipedia.org/wiki/Standard_deviation
	// http://jsfromhell.com/array/average
	return Math.sqrt(jsapi.math.variance(jsapi.array.flat(arguments)));
};
jsapi.math.variance = function () {
	// http://jsfromhell.com/array/average
	var a = jsapi.array.flat(arguments);
	for (var m, s = 0, l = a.length; l--; s += a[l]);
	for (m = s / a.length, l = a.length, s = 0; l--; s += Math.pow(a[l] - m, 2));
	return s / a.length;
};
jsapi.math.color.adapt = function (XS, YS, ZS, whitepoint_source, whitepoint_destination, MA) {
	// chromatic adaption
	// based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
	// MA = adaption matrix or predefined choice ('CAT02', 'Bradford', 'HPE D65', 'XYZ scaling'),
	// defaults to 'Bradford'
	if (!MA) MA = 'Bradford';
	if (typeof MA == 'string') {
		switch (MA) {
			case 'XYZ scaling':
				MA = [[1, 0, 0],
					  [0, 1, 0],
					  [0, 0, 1]];
				break;
			case 'HPE D65':
				MA = [[ 0.40024,  0.70760, -0.08081],
					  [-0.22630,  1.16532,  0.04570],
					  [ 0.00000,  0.00000,  0.91822]];
				break;
			case 'CAT02':
				MA = [[ 0.7328,  0.4296, -0.1624],
					  [-0.7036,  1.6975,  0.0061],
					  [ 0.0030,  0.0136,  0.9834]];
				break;
			case 'Bradford':
			default:
				MA = [[ 0.8951,  0.2664, -0.1614],
					  [-0.7502,  1.7135,  0.0367],
					  [ 0.0389, -0.0685,  1.0296]];
		}
	};
	if (MA.constructor != jsapi.math.Matrix3x3) MA = new jsapi.math.Matrix3x3(MA);
	var XYZWS = jsapi.math.color.get_whitepoint(whitepoint_source),
		pybs = MA.multiply(XYZWS),
		XYZWD = jsapi.math.color.get_whitepoint(whitepoint_destination),
		pybd = MA.multiply(XYZWD);
	return MA.invert().multiply([[pybd[0]/pybs[0], 0, 0], [0, pybd[1]/pybs[1], 0], [0, 0, pybd[2]/pybs[2]]]).multiply(MA).multiply([XS, YS, ZS]);
};
jsapi.math.color.Lab2RGB = function (L, a, b, whitepoint, scale, round_) {
	var XYZ = jsapi.math.color.Lab2XYZ(L, a, b, whitepoint || "D50");
	return jsapi.math.color.XYZ2RGB(XYZ[0], XYZ[1], XYZ[2], whitepoint || "D50", scale, round_)
};
jsapi.math.color.Lab2XYZ = function(L, a, b, whitepoint, scale) {
	// based on http://www.easyrgb.com/math.php?MATH=M8
	// whitepoint can be a color temperature in Kelvin or an array containing XYZ values
	if (!scale) scale = 1.0;
	
	var Y = ( L + 16 ) / 116,
		X = a / 500 + Y,
		Z = Y - b / 200;
	
	// Bruce Lindbloom's fix for the discontinuity of the CIE L* function
	// (http://brucelindbloom.com/LContinuity.html)
	var E = 216 / 24389,  // Intent of CIE standard, actual CIE standard = 0.008856
		K = 24389 / 27;  // Intent of CIE standard, actual CIE standard = 903.3
	// K / 116 is used instead of 7.787
	
	if ( Math.pow(Y, 3) > E ) Y = Math.pow(Y, 3);
	else                      Y = ( Y - 16 / 116 ) / (K / 116);
	if ( Math.pow(X, 3) > E ) X = Math.pow(X, 3);
	else                      X = ( X - 16 / 116 ) / (K / 116);
	if ( Math.pow(Z, 3) > E ) Z = Math.pow(Z, 3);
	else                      Z = ( Z - 16 / 116 ) / (K / 116);
	
	var ref_XYZ = jsapi.math.color.get_whitepoint(whitepoint, scale);
	X *= ref_XYZ[0];
	Y *= ref_XYZ[1];
	Z *= ref_XYZ[2];
	
	return [X, Y, Z]
};
jsapi.math.color.XYZ2RGB = function (X, Y, Z, whitepoint, scale, round_) {
	if (!scale) scale = 1.0;
	
	var RGB = jsapi.math.color.xyz_to_rgb_matrix(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, whitepoint || "D65", 1.0).multiply([X, Y, Z]); // sRGB
	
	for (var i = 0; i < 3; i ++) {
		if (RGB[i] > 0.0031308) {
			RGB[i] = 1.055 * Math.pow(RGB[i], 1 / 2.4) - 0.055;
		} else {
			RGB[i] *= 12.92;
		}
		RGB[i] = Math.min(1.0, Math.max(0, RGB[i])) * scale;
		if (round_) RGB[i] = Math.round(RGB[i]);
	}
	return RGB;
};
jsapi.math.color.CIEDCorColorTemp2XYZ = function(T, scale) {
	var xyY = jsapi.math.color.CIEDCorColorTemp2xyY(T, scale);
	return jsapi.math.color.xyY2XYZ(xyY[0], xyY[1], xyY[2]);
};
jsapi.math.color.CIEDCorColorTemp2xyY = function(T, scale) {
	// Based on formula from http://brucelindbloom.com/Eqn_T_to_xy.html
	if (!scale) scale = 1.0;
	if (typeof T == "string") {
		// Assume standard illuminant, e.g. "D50"
		var illuminant = jsapi.math.color.get_standard_illuminant(T, null, scale);
		return jsapi.math.color.XYZ2xyY(illuminant[0], illuminant[1], illuminant[2]);
	}
	var xD = 4000 <= T && T <= 7000
		? ((-4.607 * Math.pow(10, 9)) / Math.pow(T, 3))
			+ ((2.9678 * Math.pow(10, 6)) / Math.pow(T, 2))
			+ ((0.09911 * Math.pow(10, 3)) / T)
			+ 0.244063
		: (7000 < T && T <= 25000 
			? ((-2.0064 * Math.pow(10, 9)) / Math.pow(T, 3))
						+ ((1.9018 * Math.pow(10, 6)) / Math.pow(T, 2))
						+ ((0.24748 * Math.pow(10, 3)) / T)
						+ 0.237040
			: null),
		yD = xD != null ? -3 * Math.pow(xD, 2) + 2.87 * xD - 0.275 : null;
	return xD == null ? null : [xD, yD, scale];
};
jsapi.math.color.CMYK2RGB = function(C, M, Y, K, scale, round_) {
	// http://www.easyrgb.com/math.php?MATH=M14
	if (!scale) scale = 1.0;
	C = ( C * ( 1 - K ) + K );
	M = ( M * ( 1 - K ) + K );
	Y = ( Y * ( 1 - K ) + K );
	// http://www.easyrgb.com/math.php?MATH=M12
	var R, G, B;
	R = ( 1 - C ) * scale;
	G = ( 1 - M ) * scale;
	B = ( 1 - Y ) * scale;
	if (round_) {
		R = Math.round(R);
		G = Math.round(G);
		B = Math.round(B);
	}
	return [R, G, B];
};
jsapi.math.color.XYZ2Lab = function(X, Y, Z, whitepoint) {
	/*
	Convert from XYZ to Lab.
	
	The input Y value needs to be in the nominal range [0.0, 100.0] and 
	other input values scaled accordingly.
	The output L value is in the nominal range [0.0, 100.0].
	
	whitepoint can be string (e.g. "D50"), list/tuple of XYZ coordinates or 
	color temperature as float or int. Defaults to D50 if not set.
	
	Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_Lab.html
	
	*/
	whitepoint = jsapi.math.color.get_whitepoint(whitepoint, 100);

	var E = 216 / 24389,  // Intent of CIE standard, actual CIE standard = 0.008856
		K = 24389 / 27,  // Intent of CIE standard, actual CIE standard = 903.3
		xr = X / whitepoint[0],
		yr = Y / whitepoint[1],
		zr = Z / whitepoint[2],
		fx = xr > E ? jsapi.math.cbrt(xr) : (K * xr + 16) / 116,
		fy = yr > E ? jsapi.math.cbrt(yr) : (K * yr + 16) / 116,
		fz = zr > E ? jsapi.math.cbrt(zr) : (K * zr + 16) / 116,
		L = 116 * fy - 16,
		a = 500 * (fx - fy),
		b = 200 * (fy - fz);

	return [L, a, b];
};
jsapi.math.color.XYZ2Lu_v_ = function(X, Y, Z, whitepoint) {
	/* Convert from XYZ to CIE Lu'v' */

	if (X + Y + Z == 0) {
		// We can't check for X == Y == Z == 0 because they may actually add up
		// to 0, thus resulting in ZeroDivisionError later
		var XYZ = jsapi.math.color.get_whitepoint(whitepoint),
			Lu_v_ = jsapi.math.color.XYZ2Lu_v_(XYZ[0], XYZ[1], XYZ[2]);
		return [0, Lu_v_[1], Lu_v_[2]];
	}

	var XYZr = jsapi.math.color.get_whitepoint(whitepoint, 100),
		yr = Y / XYZr[1],
		L = yr > 216 / 24389 ? 116 * jsapi.math.cbrt(yr) - 16 : 24389 / 27 * yr,
		u_ = (4 * X) / (X + 15 * Y + 3 * Z),
		v_ = (9 * Y) / (X + 15 * Y + 3 * Z);
	
	return [L, u_, v_];
};
jsapi.math.color.xyY2XYZ = function(x, y, Y) {
	/*
	Convert from xyY to XYZ.
	
	Based on formula from http://brucelindbloom.com/Eqn_xyY_to_XYZ.html
	
	Implementation Notes:
	1. Watch out for the case where y = 0. In that case, X = Y = Z = 0 is 
	   returned.
	2. The output XYZ values are in the nominal range [0.0, Y[xyY]].
	
	*/
	if (y == 0) return [0, 0, 0];
	if (Y == null) Y = 1.0;
	var X = (x * Y) / y,
		Z = (1 - x - y) * Y / y;
	return [X, Y, Z];
};
jsapi.math.color.XYZ2xyY = function (X, Y, Z, whitepoint) {
	/*
	Convert from XYZ to xyY.
	
	Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_xyY.html
	
	Implementation Notes:
	1. Watch out for black, where X = Y = Z = 0. In that case, x and y are set 
	   to the chromaticity coordinates of the reference whitepoint.
	2. The output Y value is in the nominal range [0.0, Y[XYZ]].
	
	*/
	if (X == Y && Y == Z && Z == 0) {
		whitepoint = jsapi.math.color.get_whitepoint(whitepoint);
		var xyY = jsapi.math.color.XYZ2xyY(whitepoint[0], whitepoint[1], whitepoint[2]);
		return [xyY[0], xyY[1], 0.0];
	}
	var x = X / (X + Y + Z),
		y = Y / (X + Y + Z);
	return [x, y, Y];
};
jsapi.math.color.planckianCT2XYZ = function(T) {
	var xyY = jsapi.math.color.planckianCT2xyY(T);
	return jsapi.math.color.xyY2XYZ(xyY[0], xyY[1], xyY[2]);
};
jsapi.math.color.planckianCT2xyY = function (T) {
	/* Convert from planckian temperature to xyY.
	
	T = temperature in Kelvin.
	
	Formula from http://en.wikipedia.org/wiki/Planckian_locus
	
	*/
	var x, y;
	if      (1667 <= T && T <= 4000)
		x = (  -0.2661239 * (Math.pow(10, 9) / Math.pow(T, 3))
			 -  0.2343580 * (Math.pow(10, 6) / Math.pow(T, 2))
			 +  0.8776956 * (Math.pow(10, 3) / T)
			 +  0.179910);
	else if (4000 <= T && T <= 25000)
		x = (  -3.0258469 * (Math.pow(10, 9) / Math.pow(T, 3))
			 +  2.1070379 * (Math.pow(10, 6) / Math.pow(T, 2))
			 +  0.2226347 * (Math.pow(10, 3) / T)
			 +  0.24039);
	else return null;
	if      (1667 <= T && T <= 2222)
		y = (  -1.1063814  * Math.pow(x, 3)
			 -  1.34811020 * Math.pow(x, 2)
			 +  2.18555832 * x
			 -  0.20219683);
	else if (2222 <= T && T <= 4000)
		y = (  -0.9549476  * Math.pow(x, 3)
			 -  1.37418593 * Math.pow(x, 2)
			 +  2.09137015 * x
			 -  0.16748867);
	else if (4000 <= T && T <= 25000)
		y = (   3.0817580  * Math.pow(x, 3)
			 -  5.87338670 * Math.pow(x, 2)
			 +  3.75112997 * x
			 -  0.37001483);
	return [x, y, 1.0]
};
jsapi.math.color.xyz_to_rgb_matrix = function (xr, yr, xg, yg, xb, yb, whitepoint, scale) {
	// Create and return an XYZ to RGB matrix
	if (!scale) scale = 1.0;
	var cachehash = [xr, yr, xg, yg, xb, yb, whitepoint, scale].join(","),
		cache = jsapi.math.color.xyz_to_rgb_matrix.cache[cachehash];
	if (cache) return cache;
	whitepoint = jsapi.math.color.get_whitepoint(whitepoint, scale);
	var XYZr = jsapi.math.color.xyY2XYZ(xr, yr, scale),
		XYZg = jsapi.math.color.xyY2XYZ(xg, yg, scale),
		XYZb = jsapi.math.color.xyY2XYZ(xb, yb, scale),
		SrSgSb = new jsapi.math.Matrix3x3([[XYZr[0], XYZg[0], XYZb[0]],
										   [XYZr[1], XYZg[1], XYZb[1]],
										   [XYZr[2], XYZg[2], XYZb[2]]]).invert().multiply(whitepoint);
	return jsapi.math.color.xyz_to_rgb_matrix.cache[cachehash] = 
		   new jsapi.math.Matrix3x3([[SrSgSb[0] * XYZr[0], SrSgSb[1] * XYZg[0], SrSgSb[2] * XYZb[0]],
									 [SrSgSb[0] * XYZr[1], SrSgSb[1] * XYZg[1], SrSgSb[2] * XYZb[1]],
									 [SrSgSb[0] * XYZr[2], SrSgSb[1] * XYZg[2], SrSgSb[2] * XYZb[2]]]).invert();
};
jsapi.math.color.xyz_to_rgb_matrix.cache = {};
jsapi.math.color.standard_illuminants = {
	// 1st level is the standard name => illuminant definitions
	// 2nd level is the illuminant name => CIE XYZ coordinates
	// (Y should always assumed to be 1.0 and is not explicitly defined)
	"None": {"E": {"X": 1.00000, "Z": 1.00000}},
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
};
jsapi.math.color.get_standard_illuminant = function (illuminant_name, priority, scale) {
	if (!priority) priority = ["ICC", "ASTM E308-01", "Wyszecki & Stiles", "None"];
	if (!scale) scale = 1.0;
	var cachehash = [illuminant_name, priority, scale].join(","),
		cache = jsapi.math.color.get_standard_illuminant.cache[cachehash];
	if (cache) return cache;
	var illuminant = null;
	for (var i = 0; i < priority.length; i ++) {
		if (!jsapi.math.color.standard_illuminants[priority[i]])
			throw 'Unrecognized standard "' + priority[i] + '"';
		illuminant = jsapi.math.color.standard_illuminants[priority[i]][illuminant_name.toUpperCase()];
		if (illuminant)
			return jsapi.math.color.get_standard_illuminant.cache[cachehash] = [illuminant["X"] * scale, 1.0 * scale, illuminant["Z"] * scale];
	}
	throw 'Unrecognized illuminant "' + illuminant_name + '"';
};
jsapi.math.color.get_standard_illuminant.cache = {};
jsapi.math.color.get_whitepoint = function (whitepoint, scale) {
	// Return a whitepoint as XYZ coordinates
	if (whitepoint && whitepoint.constructor == Array)
		return whitepoint;
	if (!scale) scale = 1.0;
	if (!whitepoint)
		whitepoint = "D50";
	var cachehash = [whitepoint, scale].join(","),
		cache = jsapi.math.color.get_whitepoint.cache[cachehash];
	if (cache) return cache;
	if (typeof whitepoint == "string")
		whitepoint = jsapi.math.color.get_standard_illuminant(whitepoint);
	else if (typeof whitepoint == "number")
		whitepoint = jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint);
	if (scale > 1.0 && whitepoint[1] == 100)
		scale = 1.0;
	return jsapi.math.color.get_whitepoint.cache[cachehash] =
		   [whitepoint[0] * scale, whitepoint[1] * scale, whitepoint[2] * scale];
};
jsapi.math.color.get_whitepoint.cache = {};
jsapi.math.Matrix3x3 = function (matrix) {
	if (matrix.length != 3)
		throw 'Invalid number of rows for 3x3 matrix: ' + matrix.length;
	for (var i=0; i<matrix.length; i++) {
		if (matrix[i].length != 3)
			throw 'Invalid number of columns for 3x3 matrix: ' + matrix[i].length;
		this[i] = [];
		for (var j=0; j<matrix[i].length; j++) {
			this[i][j] = matrix[i][j];
		}
	};
	this.length = matrix.length;
};
jsapi.math.Matrix3x3.prototype = {
	add: function (matrix) {
		return new jsapi.math.Matrix3x3([[this[0][0] + matrix[0][0],
										   this[0][1] + matrix[0][1],
										   this[0][2] + matrix[0][2]],
										  [this[1][0] + matrix[1][0],
										   this[1][1] + matrix[1][1],
										   this[1][2] + matrix[1][2]],
										  [this[2][0] + matrix[2][0],
										   this[2][1] + matrix[2][1],
										   this[2][2] + matrix[2][2]]]);
	},
	adjoint: function () {
		return this.cofactors().transpose();
		
	},
	cofactors: function () {
		return new jsapi.math.Matrix3x3([
					[(this[1][1]*this[2][2] - this[1][2]*this[2][1]),
					 -1 * (this[1][0]*this[2][2] - this[1][2]*this[2][0]),
					 (this[1][0]*this[2][1] - this[1][1]*this[2][0])],
					[-1 * (this[0][1]*this[2][2] - this[0][2]*this[2][1]),
					 (this[0][0]*this[2][2] - this[0][2]*this[2][0]),
					 -1 * (this[0][0]*this[2][1] -this[0][1]*this[2][0])],
					[(this[0][1]*this[1][2] - this[0][2]*this[1][1]),
					 -1 * (this[0][0]*this[1][2] - this[1][0]*this[0][2]),
					 (this[0][0]*this[1][1] - this[0][1]*this[1][0])]]);
	},
	determinant: function () {
		return ((this[0][0]*this[1][1]*this[2][2] + 
				 this[1][0]*this[2][1]*this[0][2] + 
				 this[0][1]*this[1][2]*this[2][0]) - 
				(this[2][0]*this[1][1]*this[0][2] + 
				 this[1][0]*this[0][1]*this[2][2] + 
				 this[2][1]*this[1][2]*this[0][0]));
	},
	invert: function () {
		var determinant = this.determinant(),
			matrix = this.adjoint();
		return new jsapi.math.Matrix3x3([[matrix[0][0] / determinant,
										   matrix[0][1] / determinant,
										   matrix[0][2] / determinant],
										  [matrix[1][0] / determinant,
										   matrix[1][1] / determinant,
										   matrix[1][2] / determinant],
										  [matrix[2][0] / determinant,
										   matrix[2][1] / determinant,
										   matrix[2][2] / determinant]]);
	},
	multiply: function (matrix) {
		if (typeof matrix[0] == "number") {
			return [matrix[0] * this[0][0] + matrix[1] * this[0][1] + matrix[2] * this[0][2],
					matrix[0] * this[1][0] + matrix[1] * this[1][1] + matrix[2] * this[1][2],
					matrix[0] * this[2][0] + matrix[1] * this[2][1] + matrix[2] * this[2][2]];
		}
		return new jsapi.math.Matrix3x3([[this[0][0]*matrix[0][0] + this[0][1]*matrix[1][0] + this[0][2]*matrix[2][0],
										   this[0][0]*matrix[0][1] + this[0][1]*matrix[1][1] + this[0][2]*matrix[2][1],
										   this[0][0]*matrix[0][2] + this[0][1]*matrix[1][2] + this[0][2]*matrix[2][2]],
										 
										  [this[1][0]*matrix[0][0] + this[1][1]*matrix[1][0] + this[1][2]*matrix[2][0],
										   this[1][0]*matrix[0][1] + this[1][1]*matrix[1][1] + this[1][2]*matrix[2][1],
										   this[1][0]*matrix[0][2] + this[1][1]*matrix[1][2] + this[1][2]*matrix[2][2]],
										 
										  [this[2][0]*matrix[0][0] + this[2][1]*matrix[1][0] + this[2][2]*matrix[2][0],
										   this[2][0]*matrix[0][1] + this[2][1]*matrix[1][1] + this[2][2]*matrix[2][1],
										   this[2][0]*matrix[0][2] + this[2][1]*matrix[1][2] + this[2][2]*matrix[2][2]]]);
	},
	transpose: function () {
		return new jsapi.math.Matrix3x3([[this[0][0], this[1][0], this[2][0]],
										  [this[0][1], this[1][1], this[2][1]],
										  [this[0][2], this[1][2], this[2][2]]]);
	},
	toString: function () {
		var str = '[';
		for (var i=0; i<this.length; i++) {
			if (i > 0) str += ', ';
			str += '[' + this[i].join(', ') + ']';
		};
		return str + ']';
	}
};
