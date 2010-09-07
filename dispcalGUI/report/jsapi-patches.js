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
	var XYZWS = (whitepoint_source 
					? (whitepoint_source.constructor == Array 
						? whitepoint_source 
						: jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint_source)) 
					: [0.96422, 1, 0.82521]), // Observer= 2°, Illuminant= D50
		XWS = XYZWS[0], YWS = XYZWS[1], ZWS = XYZWS[2],
		ps = XWS * MA[0][0] + YWS * MA[0][1] + ZWS * MA[0][2],
		ys = XWS * MA[1][0] + YWS * MA[1][1] + ZWS * MA[1][2],
		bs = XWS * MA[2][0] + YWS * MA[2][1] + ZWS * MA[2][2],
		XYZWD = (whitepoint_destination 
					? (whitepoint_destination.constructor == Array 
						? whitepoint_destination 
						: jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint_destination)) 
					: [0.96422, 1, 0.82521]), // Observer= 2°, Illuminant= D50
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
jsapi.math.color.Lab2rgb = function (L, a, b, Lab_whitepoint, rgb_whitepoint) {
	var XYZ = jsapi.math.color.Lab2XYZ(L, a, b, Lab_whitepoint);
	return jsapi.math.color.XYZ2rgb(XYZ[0], XYZ[1], XYZ[2], rgb_whitepoint)
};
jsapi.math.color.Lab2XYZ = function(L, a, b, whitepoint) {
	// based on http://www.easyrgb.com/math.php?MATH=M8
	// whitepoint can be a color temperature in Kelvin or an array containing XYZ values
	var var_Y = ( L + 16 ) / 116;
	var var_X = a / 500 + var_Y;
	var var_Z = var_Y - b / 200;
	
	if ( Math.pow(var_Y, 3) > 0.008856 ) var_Y = Math.pow(var_Y, 3);
	else                      var_Y = ( var_Y - 16 / 116 ) / 7.787;
	if ( Math.pow(var_X, 3) > 0.008856 ) var_X = Math.pow(var_X, 3);
	else                      var_X = ( var_X - 16 / 116 ) / 7.787;
	if ( Math.pow(var_Z, 3) > 0.008856 ) var_Z = Math.pow(var_Z, 3);
	else                      var_Z = ( var_Z - 16 / 116 ) / 7.787;
	
	var ref_XYZ = (whitepoint 
					? (whitepoint.constructor == Array 
						? whitepoint 
						: jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint, true)) 
					: [96.422, 100, 82.521]), // Observer= 2°, Illuminant= D50
	X = ref_XYZ[0] * var_X,
	Y = ref_XYZ[1] * var_Y,
	Z = ref_XYZ[2] * var_Z;
	
	return [X, Y, Z]
};
jsapi.math.color.XYZ2rgb = function (X, Y, Z, whitepoint) {
	var var_X = X / 100;
	var var_Y = Y / 100;
	var var_Z = Z / 100;
	
	var xr = 0.6400, yr = 0.3300, // sRGB red primary
		xg = 0.3000, yg = 0.6000, // sRGB green primary
		xb = 0.1500, yb = 0.0600, // sRGB blue primary
		XYZw = (whitepoint 
					? (whitepoint.constructor == Array 
						? whitepoint 
						: jsapi.math.color.CIEDCorColorTemp2XYZ(whitepoint, true)) 
					: [95.047, 100, 108.883]), // Observer= 2°, Illuminant= D65
		Xw = XYZw[0] / 100, 
		Yw = XYZw[1] / 100, 
		Zw = XYZw[2] / 100,
		matrix = jsapi.math.color.matrix_rgb(xr, yr, xg, yg, xb, yb, Xw, Yw, Zw).invert();
	
	var var_R = var_X * matrix[0][0] + var_Y * matrix[1][0] + var_Z * matrix[2][0];
	var var_G = var_X * matrix[0][1] + var_Y * matrix[1][1] + var_Z * matrix[2][1];
	var var_B = var_X * matrix[0][2] + var_Y * matrix[1][2] + var_Z * matrix[2][2];
		
	if (var_R > 0.0031308) {
		var_R = 1.055 * Math.pow(var_R, 0.4166666666666667) - 0.055;
	} else {
		var_R = 12.92 * var_R;
	}
	if (var_G > 0.0031308) {
		var_G = 1.055 * Math.pow(var_G, 0.4166666666666667) - 0.055;
	} else {
		var_G = 12.92 * var_G;
	}
	if (var_B > 0.0031308) {
		var_B = 1.055 * Math.pow(var_B, 0.4166666666666667) - 0.055;
	} else {
		var_B = 12.92 * var_B;
	}
	var R, G, B;
	R = Math.max(0, Math.round(var_R * 255));
	G = Math.max(0, Math.round(var_G * 255));
	B = Math.max(0, Math.round(var_B * 255));
	return [R, G, B];
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
jsapi.math.color.matrix_rgb = function (xr, yr, xg, yg, xb, yb, Xw, Yw, Zw) {
	// Create and return an RGB matrix
	var XYZr = jsapi.math.color.xyY2XYZ(xr, yr, 1.0),
		XYZg = jsapi.math.color.xyY2XYZ(xg, yg, 1.0),
		XYZb = jsapi.math.color.xyY2XYZ(xb, yb, 1.0),
		Xr = XYZr[0], Yr = XYZr[1], Zr = XYZr[2],
		Xg = XYZg[0], Yg = XYZg[1], Zg = XYZg[2],
		Xb = XYZb[0], Yb = XYZb[1], Zb = XYZb[2],
		mtx = new jsapi.math.Matrix3x3([[Xr, Yr, Zr],
										 [Xg, Yg, Zg],
										 [Xb, Yb, Zb]]).invert(),
		Sr = Xw * mtx[0][0] + Yw * mtx[1][0] + Zw * mtx[2][0],
		Sg = Xw * mtx[0][1] + Yw * mtx[1][1] + Zw * mtx[2][1],
		Sb = Xw * mtx[0][2] + Yw * mtx[1][2] + Zw * mtx[2][2];
	return new jsapi.math.Matrix3x3([[Sr * Xr, Sr * Yr, Sr * Zr],
									  [Sg * Xg, Sg * Yg, Sg * Zg],
									  [Sb * Xb, Sb * Yb, Sb * Zb]]);
};
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
