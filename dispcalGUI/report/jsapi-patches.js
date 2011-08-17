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
		sorted = a.sort(sortNumber);
	if (sorted.length % 2 == 0) median = (sorted[sorted.length / 2] + sorted[sorted.length / 2 + 1]) / 2;
	else median = sorted[(sorted.length + 1) / 2];
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
	// MA = adaption matrix or predefined choice ('bradford', 'vonkries' or 'xyzscaling'),
	// defaults to 'bradford'
	if (!MA) MA = 'bradford';
	if (typeof MA == 'string') {
		switch (MA.toLowerCase()) {
			case 'xyzscaling':
				MA = [[1, 0, 0],
					  [0, 1, 0],
					  [0, 0, 1]];
				break;
			case 'vonkries':
				MA = [[0.4002400,  0.7076000, -0.0808100],
					  [-0.2263000,  1.1653200,  0.0457000],
					  [0.0000000,  0.0000000,  0.9182200]];
				break;
			case 'bradford':
			default:
				MA = [[0.8951000,  0.2664000, -0.1614000],
					  [-0.7502000,  1.7135000,  0.0367000],
					  [0.0389000, -0.0685000,  1.0296000]];
		}
	};
	if (MA.constructor != jsapi.math.Matrix3x3) MA = new jsapi.math.Matrix3x3(MA);
	var XYZWS = jsapi.math.color.get_whitepoint(whitepoint_source),
		XWS = XYZWS[0], YWS = XYZWS[1], ZWS = XYZWS[2],
		ps = XWS * MA[0][0] + YWS * MA[0][1] + ZWS * MA[0][2],
		ys = XWS * MA[1][0] + YWS * MA[1][1] + ZWS * MA[1][2],
		bs = XWS * MA[2][0] + YWS * MA[2][1] + ZWS * MA[2][2],
		XYZWD = jsapi.math.color.get_whitepoint(whitepoint_destination),
		XWD = XYZWD[0], YWD = XYZWD[1], ZWD = XYZWD[2],
		pd = XWD * MA[0][0] + YWD * MA[0][1] + ZWD * MA[0][2],
		yd = XWD * MA[1][0] + YWD * MA[1][1] + ZWD * MA[1][2],
		bd = XWD * MA[2][0] + YWD * MA[2][1] + ZWD * MA[2][2],
		M = MA.invert().multiply([[pd/ps, 0, 0], [0, yd/ys, 0], [0, 0, bd/bs]]).multiply(MA),
		XD = XS * M[0][0] + YS * M[0][1] + ZS * M[0][2],
		YD = XS * M[1][0] + YS * M[1][1] + ZS * M[1][2],
		ZD = XS * M[2][0] + YS * M[2][1] + ZS * M[2][2];
	return [XD, YD, ZD];
};
jsapi.math.color.Lab2RGB = function (L, a, b, Lab_whitepoint, rgb_whitepoint, scale, round_) {
	var XYZ = jsapi.math.color.Lab2XYZ(L, a, b, Lab_whitepoint);
	return jsapi.math.color.XYZ2RGB(XYZ[0], XYZ[1], XYZ[2], rgb_whitepoint, scale, round_)
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
	
	var matrix = jsapi.math.color.matrix_rgb(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, whitepoint || "D65", 1.0, true), // sRGB
		R = X * matrix[0][0] + Y * matrix[1][0] + Z * matrix[2][0],
		G = X * matrix[0][1] + Y * matrix[1][1] + Z * matrix[2][1],
		B = X * matrix[0][2] + Y * matrix[1][2] + Z * matrix[2][2];
		
	if (R > 0.0031308) {
		R = 1.055 * Math.pow(R, 1 / 2.4) - 0.055;
	} else {
		R *= 12.92;
	}
	if (G > 0.0031308) {
		G = 1.055 * Math.pow(G, 1 / 2.4) - 0.055;
	} else {
		G *= 12.92;
	}
	if (B > 0.0031308) {
		B = 1.055 * Math.pow(B, 1 / 2.4) - 0.055;
	} else {
		B *= 12.92;
	}
	R = Math.min(1.0, Math.max(0, R)) * scale;
	G = Math.min(1.0, Math.max(0, G)) * scale;
	B = Math.min(1.0, Math.max(0, B)) * scale;
	if (round_) {
		R = Math.round(R);
		G = Math.round(G);
		B = Math.round(B);
	}
	return [R, G, B];
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
		return XYZ2xyY(illuminant[0], illuminant[1], illuminant[2]);
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
		var xyY = XYZ2xyY(whitepoint[0], whitepoint[1], whitepoint[2]);
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
jsapi.math.color.matrix_rgb = function (xr, yr, xg, yg, xb, yb, whitepoint, scale, invert) {
	// Create and return an RGB matrix
	if (!scale) scale = 1.0;
	cachehash = [xr, yr, xg, yg, xb, yb, whitepoint, scale, invert].join(",");
	if (jsapi.math.color.matrix_rgb.cache[cachehash])
		return jsapi.math.color.matrix_rgb.cache[cachehash];
	whitepoint = jsapi.math.color.get_whitepoint(whitepoint, scale);
	var XYZr = jsapi.math.color.xyY2XYZ(xr, yr, scale),
		XYZg = jsapi.math.color.xyY2XYZ(xg, yg, scale),
		XYZb = jsapi.math.color.xyY2XYZ(xb, yb, scale),
		Xr = XYZr[0], Yr = XYZr[1], Zr = XYZr[2],
		Xg = XYZg[0], Yg = XYZg[1], Zg = XYZg[2],
		Xb = XYZb[0], Yb = XYZb[1], Zb = XYZb[2],
		mtx = new jsapi.math.Matrix3x3([[Xr, Yr, Zr],
										 [Xg, Yg, Zg],
										 [Xb, Yb, Zb]]).invert(),
		Sr = whitepoint[0] * mtx[0][0] + whitepoint[1] * mtx[1][0] + whitepoint[2] * mtx[2][0],
		Sg = whitepoint[0] * mtx[0][1] + whitepoint[1] * mtx[1][1] + whitepoint[2] * mtx[2][1],
		Sb = whitepoint[0] * mtx[0][2] + whitepoint[1] * mtx[1][2] + whitepoint[2] * mtx[2][2];
	mtx = new jsapi.math.Matrix3x3([[Sr * Xr, Sr * Yr, Sr * Zr],
									[Sg * Xg, Sg * Yg, Sg * Zg],
									[Sb * Xb, Sb * Yb, Sb * Zb]]);
	if (invert) mtx = mtx.invert();
	return jsapi.math.color.matrix_rgb.cache[cachehash] = mtx;
};
jsapi.math.color.matrix_rgb.cache = {};
jsapi.math.color.standard_illuminants = {
	// 1st level is the standard name => illuminant definitions
	// 2nd level is the illuminant name => CIE XYZ coordinates
	// (Y should always assumed to be 1.0 and is not explicitly defined)
	null: {"E": {"X": 1.00000, "Z": 1.00000}},
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
	if (!priority) priority = [null, "ICC", "ASTM E308-01"];
	if (!scale) scale = 1.0;
	cachehash = [illuminant_name, priority, scale].join(",");
	if (jsapi.math.color.get_standard_illuminant.cache[cachehash])
		return jsapi.math.color.get_standard_illuminant.cache[cachehash];
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
	cachehash = [whitepoint, scale].join(",");
	if (jsapi.math.color.get_whitepoint.cache[cachehash])
		return jsapi.math.color.get_whitepoint.cache[cachehash];
	if (typeof whitepoint == "string")
		whitepoint = jsapi.math.color.get_standard_illuminant(whitepoint);
	else if (typeof whitepoint == "number")
		whitepoint = jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint);
	if (scale > 1.0 && whitepoint[1] == 100)
		scale = 1.0;
	if (whitepoint[1] * scale > 100)
		throw "Y value out of range after scaling: " + (whitepoint[1] * scale);
	return jsapi.math.color.get_whitepoint.cache[cachehash] =
		   [whitepoint[0] * scale, whitepoint[1] * scale, whitepoint[2] * scale];
};
jsapi.math.color.get_whitepoint.cache = {};
jsapi.math.Matrix3x3 = function (matrix) {
	for (var i=0; i<matrix.length; i++) {
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
