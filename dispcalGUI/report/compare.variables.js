var comparison_criteria = { // values MUST pass these criteria
	'RGB': {
		fields_match: ['RGB_R', 'RGB_G', 'RGB_B'],
		fields_compare: ['XYZ_X', 'XYZ_Y', 'XYZ_Z'],
		strip_name: "RGB",
		name: "",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		warn_deviation: 3,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: [
			// description, R, G, B..., DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Average ΔE", [], DELTA_E_AVG, 3, 2, CIE76],
			["Maximum ΔE", [], DELTA_E_MAX, 6, 5, CIE76],
			["Median ΔE", [], DELTA_E_MED, null, null, CIE76],
			["Median absolute deviation ΔE", [], DELTA_E_MAD, null, null, CIE76],
			["Standard deviation ΔE", [], DELTA_E_STDDEV, null, null, CIE76],
			/* ["Average ΔE", [], DELTA_E_AVG, 1.5, 1, CIE94],
			["Maximum ΔE", [], DELTA_E_MAX, 4, 3, CIE94],
			["Median ΔE", [], DELTA_E_MED, null, null, CIE94],
			["Median absolute deviation ΔE", [], DELTA_E_MAD, null, null, CIE94],
			["Standard deviation ΔE", [], DELTA_E_STDDEV, null, null, CIE94], */
			["Average ΔE", [], DELTA_E_AVG, 1.5, 1, CIE00],
			["Maximum ΔE", [], DELTA_E_MAX, 4, 3, CIE00],
			["Median ΔE", [], DELTA_E_MED, null, null, CIE00],
			["Median absolute deviation ΔE", [], DELTA_E_MAD, null, null, CIE00],
			["Standard deviation ΔE", [], DELTA_E_STDDEV, null, null, CIE00]
		]
	}
};
