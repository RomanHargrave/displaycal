var CRITERIA_RULES_NEUTRAL = [
		// description, [[R, G, B],...], DELTA_[E|L|C|H]_[MAX|MED|MAD|AVG|STDDEV], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
		["Average ΔE*76", [], DELTA_E_AVG, 3, 2, CIE76],
		["Maximum ΔE*76", [], DELTA_E_MAX, 6, 5, CIE76],
		["Median ΔE*76", [], DELTA_E_MED, null, null, CIE76],
		["Median absolute deviation ΔE*76", [], DELTA_E_MAD, null, null, CIE76],
		["Standard deviation ΔE*76", [], DELTA_E_STDDEV, null, null, CIE76],
		["Average ΔE*00", [], DELTA_E_AVG, null, null, CIE00],
		["Maximum ΔE*00", [], DELTA_E_MAX, null, null, CIE00],
		["Median ΔE*00", [], DELTA_E_MED, null, null, CIE00],
		["Median absolute deviation ΔE*00", [], DELTA_E_MAD, null, null, CIE00],
		["Standard deviation ΔE*00", [], DELTA_E_STDDEV, null, null, CIE00]
	],
	CRITERIA_DEFAULT = {
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		name: "Default",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE76, // delta calculation method for overview
		warn_deviation: 3,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_NEUTRAL.clone()
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
		rules: CRITERIA_RULES_NEUTRAL.concat([
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
	};

CRITERIA_DEFAULT.rules[5][3] = 1.5;
CRITERIA_DEFAULT.rules[5][4] = 1;
CRITERIA_DEFAULT.rules[6][3] = 4;
CRITERIA_DEFAULT.rules[6][4] = 3;

var CRITERIA_FOGRA_MEDIAWEDGE_3 = CRITERIA_ISO12647_7,
	comparison_criteria = { // values MUST pass these criteria
		RGB: CRITERIA_DEFAULT.clone(),
		CMYK: CRITERIA_DEFAULT.clone(),
		FOGRA_MW3: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA28_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA29_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA30_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA31_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA32_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA39_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA40_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA41_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA42_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA43_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3,
		FOGRA44_MW3_SUBSET: CRITERIA_FOGRA_MEDIAWEDGE_3
	};
	
CRITERIA_FOGRA_MEDIAWEDGE_3.id = 'FOGRA_MW3';
CRITERIA_FOGRA_MEDIAWEDGE_3.name = "Fogra Media Wedge V3";
CRITERIA_FOGRA_MEDIAWEDGE_3.strip_name = "Ugra/Fogra Media Wedge CMYK V3.0";

comparison_criteria.CMYK.id = 'CMYK';
comparison_criteria.CMYK.fields_match = ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'];
comparison_criteria.CMYK.name = "CMYK default",
comparison_criteria.CMYK.strip_name = "CMYK";

comparison_criteria.RGB.id = 'RGB';
comparison_criteria.RGB.fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
comparison_criteria.RGB.name = "RGB default",
comparison_criteria.RGB.strip_name = "RGB";

comparison_criteria.VERIFY = comparison_criteria.RGB.clone();
comparison_criteria.VERIFY.id = 'VERIFY';
comparison_criteria.VERIFY.name = "RGB default + gray balance";
comparison_criteria.VERIFY.rules = CRITERIA_DEFAULT.rules.concat(
	[
		["RGB gray balance average ΔC*76", [
			[12.5, 12.5, 12.5],
			[25, 25, 25],
			[37.5, 37.5, 37.5],
			[50, 50, 50],
			[62.5, 62.5, 62.5],
			[75, 75, 75],
			[87.5, 87.5, 87.5],
			[100, 100, 100]
		], DELTA_C_AVG, 1.0, 0.5, CIE76],
		["RGB gray balance maximum ΔC*76", [
			[12.5, 12.5, 12.5],
			[25, 25, 25],
			[37.5, 37.5, 37.5],
			[50, 50, 50],
			[62.5, 62.5, 62.5],
			[75, 75, 75],
			[87.5, 87.5, 87.5],
			[100, 100, 100]
		], DELTA_C_MAX, 2.0, 1.0, CIE76]
	]
);

comparison_criteria.VERIFY_EXTENDED = comparison_criteria.RGB.clone();
comparison_criteria.VERIFY_EXTENDED.id = 'VERIFY_EXTENDED';
comparison_criteria.VERIFY_EXTENDED.name = "RGB default + gray balance (extended)";
comparison_criteria.VERIFY_EXTENDED.rules = CRITERIA_DEFAULT.rules.concat(
	[
		["RGB gray balance average ΔC*76", [
			[ 5,  5,  5],
			[10, 10, 10],
			[15, 15, 15],
			[20, 20, 20],
			[25, 25, 25],
			[30, 30, 30],
			[35, 35, 35],
			[40, 40, 40],
			[45, 45, 45],
			[50, 50, 50],
			[55, 55, 55],
			[60, 60, 60],
			[65, 65, 65],
			[70, 70, 70],
			[75, 75, 75],
			[80, 80, 80],
			[85, 85, 85],
			[90, 90, 90],
			[95, 95, 95],
			[100, 100, 100]
		], DELTA_C_AVG, 1.0, 0.5, CIE76],
		["RGB gray balance maximum ΔC*76", [
			[ 5,  5,  5],
			[10, 10, 10],
			[15, 15, 15],
			[20, 20, 20],
			[25, 25, 25],
			[30, 30, 30],
			[35, 35, 35],
			[40, 40, 40],
			[45, 45, 45],
			[50, 50, 50],
			[55, 55, 55],
			[60, 60, 60],
			[65, 65, 65],
			[70, 70, 70],
			[75, 75, 75],
			[80, 80, 80],
			[85, 85, 85],
			[90, 90, 90],
			[95, 95, 95],
			[100, 100, 100]
		], DELTA_C_MAX, 2.0, 1.0, CIE76]
	]
);
