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
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: [
			// description, R, G, B..., DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Avg. ΔE", [], DELTA_E_AVG, 3, 2, CIE76],
			["Max. ΔE", [], DELTA_E_MAX, 6, 5, CIE76],
			["Avg. ΔE", [], DELTA_E_AVG, 1.5, 1, CIE94],
			["Max. ΔE", [], DELTA_E_MAX, 4, 3, CIE94],
			["Avg. ΔE", [], DELTA_E_AVG, 1.5, 1, CIE00],
			["Max. ΔE", [], DELTA_E_MAX, 4, 3, CIE00]
		]
	}
};
