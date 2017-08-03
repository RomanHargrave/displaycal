var CRITERIA_RULES_NEUTRAL = [
		// description, [[R, G, B],...], DELTA_[E|L|C|H]_[MAX|MED|MAD|AVG|STDDEV], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
		["Measured vs. assumed target whitepoint ΔE*76", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE76],
		["Measured vs. assumed target whitepoint ΔE*94", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE94],
		["Measured vs. assumed target whitepoint ΔE*00", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE00],
		["Measured vs. profile whitepoint ΔE*76", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE76],
		["Measured vs. profile whitepoint ΔE*94", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE94],
		["Measured vs. profile whitepoint ΔE*00", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE00],
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
		["Standard deviation ΔE*00", [], DELTA_E_STDDEV, null, null, CIE00],
		["Calibration red tone values", ['CAL_REDLEVELS'], '', null, 95],
		["Calibration green tone values", ['CAL_GREENLEVELS'], '', null, 95],
		["Calibration blue tone values", ['CAL_BLUELEVELS'], '', null, 95],
		["Calibration grayscale tone values", ['CAL_GRAYLEVELS'], '', null, 95]
	],
	CRITERIA_RULES_DEFAULT = CRITERIA_RULES_NEUTRAL.clone();

CRITERIA_RULES_DEFAULT[0][3] = 2; // Whitepoint ΔE*76 nominal
CRITERIA_RULES_DEFAULT[0][4] = 1; // Whitepoint ΔE*76 recommended

CRITERIA_RULES_DEFAULT[1][3] = 2; // Whitepoint ΔE*94 nominal
CRITERIA_RULES_DEFAULT[1][4] = 1; // Whitepoint ΔE*94 recommended

CRITERIA_RULES_DEFAULT[2][3] = 2; // Whitepoint ΔE*00 nominal
CRITERIA_RULES_DEFAULT[2][4] = 1; // Whitepoint ΔE*00 recommended

CRITERIA_RULES_DEFAULT[6][3] = 3; // Average ΔE*76 nominal
CRITERIA_RULES_DEFAULT[6][4] = 1.5; // Average ΔE*76 recommended

CRITERIA_RULES_DEFAULT[7][3] = 1.5; // Average ΔE*94 nominal
CRITERIA_RULES_DEFAULT[7][4] = 1; // Average ΔE*94 recommended

CRITERIA_RULES_DEFAULT[8][3] = 1.5; // Average ΔE*00 nominal
CRITERIA_RULES_DEFAULT[8][4] = 1; // Average ΔE*00 recommended

CRITERIA_RULES_DEFAULT[9][3] = 6; // Maximum ΔE*76 nominal
CRITERIA_RULES_DEFAULT[9][4] = 4; // Maximum ΔE*76 recommended

CRITERIA_RULES_DEFAULT[10][3] = 4; // Maximum ΔE*94 nominal
CRITERIA_RULES_DEFAULT[10][4] = 3; // Maximum ΔE*94 recommended

CRITERIA_RULES_DEFAULT[11][3] = 4; // Maximum ΔE*00 nominal
CRITERIA_RULES_DEFAULT[11][4] = 3; // Maximum ΔE*00 recommended

var CRITERIA_RULES_RGB = CRITERIA_RULES_DEFAULT.concat(
		[
			["Gamma maximum", [], GAMMA_MAX],
			["Gamma minimum", [], GAMMA_MIN],
			["Gamma range", [], GAMMA_RANGE],
			["Gamma average", [], GAMMA_AVG],
			["Gamma median", [], GAMMA_MED],
			["Gamma median absolute deviation", [], GAMMA_MAD],
			["Gamma standard deviation", [], GAMMA_STDDEV]
		]
	),
	CRITERIA_RULES_VERIFY = CRITERIA_RULES_RGB.concat(
		[
			["RGB gray balance (>= 1% luminance) average absolute ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE76],
			["RGB gray balance (>= 1% luminance) combined Δa*76 and Δb*76 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE76],
			["RGB gray balance (>= 1% luminance) maximum ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE76],
			["RGB gray balance (>= 1% luminance) average absolute ΔC*94", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE94],
			["RGB gray balance (>= 1% luminance) combined Δa*94 and Δb*94 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE94],
			["RGB gray balance (>= 1% luminance) maximum ΔC*94", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE94],
			["RGB gray balance (>= 1% luminance) average absolute ΔC*00", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE00],
			["RGB gray balance (>= 1% luminance) combined Δa*00 and Δb*00 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE00],
			["RGB gray balance (>= 1% luminance) maximum ΔC*00", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE00]
		]
	),
	CRITERIA_RULES_CMYK = CRITERIA_RULES_DEFAULT.clone(),
	CRITERIA_DEFAULT = {
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		name: "Default",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: false,
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
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: false,
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK
	},
	CRITERIA_IDEALLIANCE = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "IDEALLIANCE",
		name: "IDEAlliance Control Strip 2009",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: true,
		warn_deviation: 3,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK.concat([
			// description, [[C, M, Y, K],...], DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Paper white ΔL*00", [[0, 0, 0, 0]], DELTA_L_MAX, 2, 1, CIE00],
			["Paper white Δa*00", [[0, 0, 0, 0]], DELTA_A_MAX, 1, .5, CIE00],
			["Paper white Δb*00", [[0, 0, 0, 0]], DELTA_B_MAX, 2, 1, CIE00],
			/* ["Average ΔE*00", [], DELTA_E_AVG, 2, 1, CIE00],
			["Maximum ΔE*00", [], DELTA_E_MAX, 6, 3, CIE00], */
			["CMYK solids maximum ΔE*00", [
				[100, 0, 0, 0],
				[0, 100, 0, 0],
				[0, 0, 100, 0],
				[0, 0, 0, 100]
			], DELTA_E_MAX, 7, 3, CIE00],
			["CMY 50% grey ΔE*00", [[50, 40, 40, 0]], DELTA_E_MAX, 1.5, 0.75, CIE00], 
			["CMY grey maximum ΔL*00", [
				[3.1, 2.2, 2.2, 0],
				[10.2, 7.4, 7.4, 0],
				[25, 19, 19, 0],
				[50, 40, 40, 0],
				[75, 66, 66, 0]
			], DELTA_L_MAX, 2, 1, CIE00], 
			["CMY grey maximum Δa*00", [
				[3.1, 2.2, 2.2, 0],
				[10.2, 7.4, 7.4, 0],
				[25, 19, 19, 0],
				[50, 40, 40, 0],
				[75, 66, 66, 0]
			], DELTA_A_MAX, 1, .5, CIE00], 
			["CMY grey maximum Δb*00", [
				[3.1, 2.2, 2.2, 0],
				[10.2, 7.4, 7.4, 0],
				[25, 19, 19, 0],
				[50, 40, 40, 0],
				[75, 66, 66, 0]
			], DELTA_B_MAX, 1, .5, CIE00], 
			["CMY grey maximum ΔE*00", [
				[3.1, 2.2, 2.2, 0],
				[10.2, 7.4, 7.4, 0],
				[25, 19, 19, 0],
				[50, 40, 40, 0],
				[75, 66, 66, 0]
			], DELTA_E_MAX, 2, 1, CIE00]
		])
	},
	CRITERIA_ISO12647_7 = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		lock_delta_calc_method: true,
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
			["CMY grey average absolute ΔH*76", [
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
		IDEALLIANCE: CRITERIA_IDEALLIANCE
	};

comparison_criteria['CMYK_FOGRA_MEDIAWEDGE_V3'] = CRITERIA_FOGRA_MEDIAWEDGE_3;

for (var i=27; i<=47; i++) {
	comparison_criteria['1x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['2x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW2_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW3_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
};

comparison_criteria['CMYK_IDEALLIANCE_CONTROLSTRIP_2009'] = CRITERIA_IDEALLIANCE;
comparison_criteria['GRACOLCOATED1_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE;
comparison_criteria['SWOPCOATED3_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE;
comparison_criteria['SWOPCOATED5_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE;
	
CRITERIA_FOGRA_MEDIAWEDGE_3.id = 'FOGRA_MW3';
CRITERIA_FOGRA_MEDIAWEDGE_3.name = "Fogra Media Wedge V3";
CRITERIA_FOGRA_MEDIAWEDGE_3.strip_name = "Ugra/Fogra Media Wedge CMYK V3.0";

CRITERIA_IDEALLIANCE.rules[8][3] = 2; // Average ΔE*00 nominal
CRITERIA_IDEALLIANCE.rules[11][3] = 6; // Maximum ΔE*00 nominal

comparison_criteria.RGB.id = 'RGB';
comparison_criteria.RGB.fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
comparison_criteria.RGB.name = "RGB";
comparison_criteria.RGB.strip_name = "RGB";
comparison_criteria.RGB.rules = CRITERIA_RULES_RGB;

if (window.CRITERIA_GRAYSCALE) {
	comparison_criteria.RGB_GRAY = comparison_criteria.RGB.clone();
	comparison_criteria.RGB_GRAY.delta_calc_method = CIE00;
	comparison_criteria.RGB_GRAY.id = 'RGB_GRAY';
	comparison_criteria.RGB_GRAY.name = "RGB + gray balance";
	comparison_criteria.RGB_GRAY.rules = CRITERIA_RULES_VERIFY;
};
