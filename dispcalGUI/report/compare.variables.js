var CRITERIA_RULES_NEUTRAL = [
		// description, [[R, G, B],...], DELTA_[E|L|C|H]_[MAX|MED|MAD|AVG|STDDEV], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
		["Whitepoint ΔE*76", ['WHITEPOINT'], DELTA_E_MAX, null, null, CIE76],
		["Whitepoint ΔE*94", ['WHITEPOINT'], DELTA_E_MAX, null, null, CIE94],
		["Whitepoint ΔE*00", ['WHITEPOINT'], DELTA_E_MAX, null, null, CIE00],
		["Average ΔE*76", [], DELTA_E_AVG, null, null, CIE76],
		["Average ΔE*94", [], DELTA_E_AVG, null, null, CIE94],
		["Average ΔE*00", [], DELTA_E_AVG, null, null, CIE00],
		["Maximum ΔE*76", [], DELTA_E_MAX, null, null, CIE76],
		["Maximum ΔE*94", [], DELTA_E_MAX, null, null, CIE94],
		["Maximum ΔE*00", [], DELTA_E_MAX, null, null, CIE00],
		["Median ΔE*76", [], DELTA_E_MED, null, null, CIE76],
		["Median ΔE*94", [], DELTA_E_MED, null, null, CIE94],
		["Median ΔE*00", [], DELTA_E_MED, null, null, CIE00],
		["Median absolute deviation ΔE*76", [], DELTA_E_MAD, null, null, CIE76],
		["Median absolute deviation ΔE*94", [], DELTA_E_MAD, null, null, CIE94],
		["Median absolute deviation ΔE*00", [], DELTA_E_MAD, null, null, CIE00],
		["Standard deviation ΔE*76", [], DELTA_E_STDDEV, null, null, CIE76],
		["Standard deviation ΔE*94", [], DELTA_E_STDDEV, null, null, CIE94],
		["Standard deviation ΔE*00", [], DELTA_E_STDDEV, null, null, CIE00]
	],
	CRITERIA_RULES_DEFAULT = CRITERIA_RULES_NEUTRAL.clone();

CRITERIA_RULES_DEFAULT[0][3] = 2; // Whitepoint ΔE*76 nominal
CRITERIA_RULES_DEFAULT[0][4] = 1; // Whitepoint ΔE*76 recommended
CRITERIA_RULES_DEFAULT[3][3] = 3; // Average ΔE*76 nominal
CRITERIA_RULES_DEFAULT[3][4] = 1.5; // Average ΔE*76 recommended
CRITERIA_RULES_DEFAULT[6][3] = 6; // Maximum ΔE*76 nominal
CRITERIA_RULES_DEFAULT[6][4] = 4; // Maximum ΔE*76 recommended

var CRITERIA_RULES_VERIFY = CRITERIA_RULES_DEFAULT.clone(),
	CRITERIA_RULES_CMYK = CRITERIA_RULES_DEFAULT.clone(),
	CRITERIA_DEFAULT = {
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		name: "Default",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_DEFAULT
	},
	CRITERIA_CMYK = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "CMYK",
		name: "CMYK",
		strip_name: "CMYK",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK
	},
	CRITERIA_ISO12647_7 = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK.concat([
			// description, [[C, M, Y, K],...], DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Paper white ΔE*76", [[0, 0, 0, 0]], DELTA_E_MAX, 3, 1, CIE76],
			/* ["Average ΔE*", [], DELTA_E_AVG, 3, 2, CIE76],
			["Maximum ΔE*", [], DELTA_E_MAX, 6, 5, CIE76], */
			["CMYK solids maximum ΔE*76", [
				[100, 0, 0, 0],
				[0, 100, 0, 0],
				[0, 0, 100, 0],
				[0, 0, 0, 100]
			], DELTA_E_MAX, 5, 3, CIE76],
			["CMYK solids maximum ΔH*76", [
				[100, 0, 0, 0],
				[0, 100, 0, 0],
				[0, 0, 100, 0],
				[0, 0, 0, 100]
			], DELTA_H_MAX, 2.5, 1.5, CIE76],
			["CMY grey average ΔH*76", [
				[100, 85, 85, 0],
				[80, 65, 65, 0],
				[60, 45, 45, 0],
				[40, 27, 27, 0],
				[20, 12, 12, 0],
				[10, 6, 6, 0]
			], DELTA_H_AVG, 1.5, 0.5, CIE76]
		])
	},
	CRITERIA_FOGRA_MEDIAWEDGE_3 = CRITERIA_ISO12647_7,
	comparison_criteria = { // values MUST pass these criteria
		RGB: CRITERIA_DEFAULT.clone(),
		CMYK: CRITERIA_CMYK,
		FOGRA_MW3: CRITERIA_FOGRA_MEDIAWEDGE_3,
	};

for (var i=27; i<=47; i++) {
	comparison_criteria['1x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['2x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW2_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW3_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
};
	
CRITERIA_FOGRA_MEDIAWEDGE_3.id = 'FOGRA_MW3';
CRITERIA_FOGRA_MEDIAWEDGE_3.name = "Fogra Media Wedge V3";
CRITERIA_FOGRA_MEDIAWEDGE_3.strip_name = "Ugra/Fogra Media Wedge CMYK V3.0";

comparison_criteria.RGB.id = 'RGB';
comparison_criteria.RGB.fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
comparison_criteria.RGB.name = "RGB",
comparison_criteria.RGB.strip_name = "RGB";

if (window.CRITERIA_GRAYSCALE) {
	comparison_criteria.VERIFY = comparison_criteria.RGB.clone();
	comparison_criteria.VERIFY.id = 'VERIFY';
	comparison_criteria.VERIFY.name = "RGB + gray balance";
	comparison_criteria.VERIFY.rules = CRITERIA_RULES_VERIFY.concat(
		[
			["RGB gray balance (>= 1% luminance) average ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE76],
			["RGB gray balance (>= 1% luminance) combined Δa*76 and Δb*76 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE76],
			["RGB gray balance (>= 1% luminance) maximum ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE76]
		]
	);
};
