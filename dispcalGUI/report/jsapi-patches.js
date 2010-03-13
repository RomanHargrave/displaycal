function sortNumber(a, b) {
	return a - b;
};
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
jsapi.math.color.XYZ2rgb = function (X, Y, Z) {
	var var_X = X / 100;
	var var_Y = Y / 100;
	var var_Z = Z / 100;
	// sRGB Bradford-adapted to D50, http://brucelindbloom.com/Eqn_RGB_XYZ_Matrix.html
	var var_R = var_X * 3.1338561 + var_Y * -1.6168667 + var_Z * -0.4906146;
	var var_G = var_X * -0.9787684 + var_Y * 1.9161415 + var_Z * 0.0334540;
	var var_B = var_X * 0.0719453 + var_Y * -0.2289914 + var_Z * 1.4052427;
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
