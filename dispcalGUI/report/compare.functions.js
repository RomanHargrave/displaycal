var p;

// Array methods
p=Array.prototype;
p.indexof = function(v, ignore_case) {
	for (var i=0; i<this.length; i++) if (ignore_case?(this[i]+"").toUpperCase()==(v+"").toUpperCase():this[i]==v) return i;
	return -1
};
if (!p.indexOf) p.indexOf = p.indexof;

// Object methods
p=Object.prototype;
p.clone = function() {
	var o = new this.constructor();
	for (var i in this) {
		if (this[i] != null && (this[i].constructor == Array || this[i].constructor == Object)) o[i] = this[i].clone();
		else o[i] = this[i]
	};
	return o
};
p.toString=function(){
	var str = "{";
	for (var i in this) {
		if (this[i] != this.constructor.prototype[i]) {
			if (str.length > 1) str += ",";
			str += i + ":" + (typeof this[i] == "string" ? "\"" + this[i] + "\"" : this[i])
		}
	};
	return str += "}"
};

// Number methods
p=Number.prototype;
p.accuracy = function(ln) {
	var n = Math.pow(10, ln || 0);
	return Math.round(this * n) / n
};
p.fill=function(ipart, fpart) {
	var i, v=(fpart!=null?this.toFixed(fpart):this+"");
	if ((i = v.indexOf(".")) > -1) ipart+=v.substr(i).length;
	while (v.length<ipart) v=0+v;
	return v
};
p.lead=function(ln) {
	var v=this+"";
	while (v.length<ln+1) v=0+v;
	return v
};

// String methods
p=String.prototype;
p.accuracy = function() {
	return this
};
p.repeat = function(n) {
	var str="";
	for (var i=0; i<n; i++) str+=this;
	return str
};

// dataset Constructor
function dataset(src) {
	this.header = [];
	this.data_format = [];
	this.data = [];
	this.decimal = ".";
	this.id = "RGB";
	var e = document.forms['F_data'].elements;
	this.testchart = e['FF_testchart'].value;
	this.id = window.CRITERIA_GRAYSCALE ? 'VERIFY' : splitext(basename(this.testchart))[0].toUpperCase();
	if (src) {
		this.src = src;
		src=cr2lf(src);
		var _data_format_regexp = /(^|\s)BEGIN_DATA_FORMAT\s+(.*?)\s+END_DATA_FORMAT(?=\s|$)/i,
			_data_regexp1 = /(^|\s)BEGIN_DATA\s+/i,
			_data_regexp2 = /\sEND_DATA(?=\s|$)/i,
			_header_regexp1 = /(^|\s)BEGIN_(\w+)\s+([\s\S]*?)\s+END_\2(?=\s|$)/gi,
			_header_regexp2 = /(^|\s)BEGIN_(\w+)\s+([\s\S]*?)\s+END_\2(?=\s|$)/i,
			data_begin,
			data_end,
			data_format = src.match(_data_format_regexp),
			i,v;
		if (data_format && data_format[2]) {
			this.data_format = toarray(data_format[2], 1);
			while ((data_begin = src.search(_data_regexp1))>-1 && (data_end = src.search(_data_regexp2))>data_begin) {
				if (!this.data.length) { // 1st
					var header = lf2cr(src).substr(0, data_begin).replace(_data_format_regexp, "");
					if (v = header.match(_header_regexp1)) for (i=0; i<v.length; i++) {
						header = header.replace(_header_regexp2, "\r" + (v[i].replace(_header_regexp2, "$2 $3").replace(/\r/g, "\n")))
					};
					header=trim(header).split(/\r/);
					for (i=0; i<header.length; i++) {
						header[i] = trim(header[i]).replace(/\s+/, "\r").split("\r");
						this.header_set_field(header[i][0], header[i][1], "append")
					}
				};
				this.data = this.data.concat(toarray(src.substring(data_begin, data_end).replace(_data_regexp1, "").replace(_data_regexp2, "")));
				src = src.substr(data_end+9)
			}
		};
	};
	if (this.data_format.indexOf('CMYK_C') > -1 && this.data_format.indexOf('CMYK_M') > -1 && this.data_format.indexOf('CMYK_Y') > -1 && this.data_format.indexOf('CMYK_K') > -1)
		this.device = 'CMYK';
	else
		this.device = 'RGB';
	if (comparison_criteria[this.id]) this.id = comparison_criteria[this.id].id;
	else this.id = this.device;
	return src ? true : false
};

p=dataset.prototype;
p.header_get = function() {
	var header=[], i, j, v;
	for (i=0; i<this.header.length; i++) {
		if (this.header[i][1] && this.header[i][1].indexOf("\n")>-1) {
			header.push(["BEGIN_"+this.header[i][0]]);
			v=this.header[i][1].split("\n");
			for (j=0; j<v.length; j++) header.push([v[j]]);
			header.push(["END_"+this.header[i][0]])
		}
		else header.push(this.header[i])
	};
	return fromarray(header)
};
p.header_set = function(header, mode) {
	for (var i=0; i<header.length; i++) {
		this.header_set_field(header[i][0], header[i][1], mode)
	}
};
p.header_set_date = function(mode) {
	var now=new Date();
	this.header_set_field("CREATED", "\"" + (now.getMonth()+1) + "/" + now.getDate() + "/" + now.getFullYear() + "\" # Time: " + now.getHours().fill(2) + ":" + now.getMinutes().fill(2), mode)
};
p.header_set_defaults = function(mode) {
	this.header_set_date(mode);
};
p.header_set_field = function(name, value, mode) {
	if (!name) return false;
	if (value != null) value += "";
	if (name.toUpperCase() == "NUMBER_OF_FIELDS" || name.toUpperCase() == "NUMBER_OF_SETS") return false;
	if (!this.header[name.toUpperCase()] || mode=="append" || name.toUpperCase() == "KEYWORD") {
		var header=[name];
		if(value!=null && value!=="") header.push(value);
		this.header.push(header);
		if (!this.header[name.toUpperCase()]) this.header[name.toUpperCase()]=[];
		this.header[name.toUpperCase()].push(this.header[this.header.length-1])
	}
	else if (mode=="overwrite") {
		for (var i=0; i<this.header[name.toUpperCase()].length; i++) {
			if (value==null || value==="") this.header[name.toUpperCase()][i].splice(1, 1);
			else this.header[name.toUpperCase()][i][1] = value
		}
	}
};
p.toString = function() {
	return (this.header.length?this.header_get()+"\n":"") + "NUMBER_OF_FIELDS\t" + this.data_format.length + "\nBEGIN_DATA_FORMAT\n" + fromarray(this.data_format, 1) + "\nEND_DATA_FORMAT\nNUMBER_OF_SETS\t" + this.data.length + "\nBEGIN_DATA\n" + decimal(fromarray(this.data), this.decimal == "." ? "\\," : "\\." , this.decimal) + "\nEND_DATA"
};
p.generate_report = function(set_delta_calc_method) {
	var f = document.forms,
		e = f['F_data'].elements,
		criteria = comparison_criteria[f['F_out'].elements['FF_criteria'].value];
	if (set_delta_calc_method !== false) f['F_out'].elements['FF_delta_calc_method'].selectedIndex = ['CIE76', 'CIE94', 'CIE00'].indexOf(criteria.delta_calc_method);
	var rules = criteria.rules,
		result = [],
		delta,
		matched,
		target,
		target_Lab,
		target_rgb,
		target_rgb_html,
		actual,
		actual_Lab,
		actual_rgb,
		actual_rgb_html,
		D50 = [96.422, 100, 82.521],
		profile_wp = e['FF_profile_whitepoint'].value.split(/\s+/),
		profile_wp_round = [],
		wp = e['FF_whitepoint'].value.split(/\s+/),
		wp_round = [],
		wp_norm = e['FF_whitepoint_normalized'].value.split(/\s+/),
		wp_norm_round = [],
		colortemp,
		colortemp_assumed,
		wp_assumed,
		n = 0,
		o = fields_match.length - 1, // offset for CIE values
		devlen = fields_match.length > 4 ? 2 : o, // length for device values, if RGB + CMYK, just use RGB (TODO: it depends on the order of the comparison_criteria keys if RGB is first, but this is assumed - need to make sure it is really the case!)
		missing_data,
		delta_calc_method = f['F_out'].elements['FF_delta_calc_method'].value,
		patch_number_html,
		warn_deviation = criteria.warn_deviation,
		no_Lab = (this.data_format.indexof("LAB_L", true) < 0
				|| this.data_format.indexof("LAB_A", true) < 0
				|| this.data_format.indexof("LAB_B", true) < 0),
		no_XYZ = (this.data_format.indexof("XYZ_X", true) < 0
				|| this.data_format.indexof("XYZ_Y", true) < 0
				|| this.data_format.indexof("XYZ_Z", true) < 0),
		gray_balance_cal_only = f['F_out'].elements['FF_gray_balance_cal_only'].checked;
	
	for (var i=0; i<profile_wp.length; i++) {
		profile_wp[i] = parseFloat(profile_wp[i]);
		profile_wp_round[i] = profile_wp[i].accuracy(2)
	};
	for (var i=0; i<wp.length; i++) {
		wp[i] = parseFloat(wp[i]);
		wp_round[i] = wp[i].accuracy(2)
	};
	for (var i=0; i<wp_norm.length; i++) {
		wp_norm[i] = parseFloat(wp_norm[i]);
		wp_norm_round[i] = wp_norm[i].accuracy(2)
	};
	
	colortemp = Math.round(jsapi.math.color.XYZ2CorColorTemp(wp_norm[0], wp_norm[1], wp_norm[2]));
	colortemp_assumed = Math.round(colortemp / 100) * 100;
	wp_assumed = jsapi.math.color.CIEDCorColorTemp2XYZ(colortemp_assumed);
	for (var i=0; i<wp_assumed.length; i++) wp_assumed[i] = wp_assumed[i] * 100;
	
	this.report_html = [
		'	<h2>Profile Verification Report</h2>',
		'	<table class="info">',
		'		<tr>',
		'			<th>Device:</th>',
		'			<td>' + e['FF_display'].value + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Instrument:</th>',
		'			<td>' + e['FF_instrument'].value + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Measured luminance:</th>',
		'			<td>' + wp[1].accuracy(1) + ' cd/m²</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Measured whitepoint XYZ (normalized):</th>',
		'			<td>' + wp_round.join(' ') + ' (' + wp_norm_round.join(' ') + ')</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Correlated color temperature:</th>',
		'			<td>' + colortemp + '° K</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Assumed target whitepoint:</th>',
		'			<td>' + colortemp_assumed + '° K</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Profile:</th>',
		'			<td>' + e['FF_profile'].value + '</td>',
		'		</tr>',
		/* '		<tr>',
		'			<th>Profile whitepoint XYZ (normalized):</th>',
		'			<td>' + profile_wp_round.join(', ') + '</td>',
		'		</tr>', */
		'		<tr>',
		'			<th>Testchart:</th>',
		'			<td>' + this.testchart + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Chromatic adaption:</th>',
		'			<td>' + e['FF_adaption'].value + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Evaluation criteria:</th>',
		'			<td>' + criteria.name + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Date:</th>',
		'			<td>' + e['FF_datetime'].value + '</td>',
		'		</tr>',
		'	</table>'
	];
	var result_start = this.report_html.length;
	this.report_html = this.report_html.concat([
		'	<div class="summary">',
		'	<h3>Summary</h3>',
		'	<table>',
		'		<tr>',
		'			<th class="first-column">Criteria</th><th>Nominal</th><th>Recommended</th><th>#</th><th colspan="2">&#160;</th><th>Actual</th><th>&#160;</th><th>Result</th>',
		'		</tr>'
	]);
	var seen = [];
	for (var j=0; j<rules.length; j++) {
		this.report_html.push('		<tr>');
		this.report_html.push('			<td class="first-column' + (!rules[j][3] ? ' statonly' : '' ) + '">' + rules[j][0] + '</td><td>' + (rules[j][3] ? (rules[j][2] ? '&lt;= ' + rules[j][3] : '&gt;= ' + rules[j][3] + '%') : '') + '</td><td' + (!rules[j][3] ? ' class="statonly"' : '' ) + '>' + (rules[j][4] ? (rules[j][2] ? '&lt;= ' + rules[j][4] : '&gt;= ' + rules[j][4] + '%'): '') + '</td><td class="patch sample_id">');
		result[j] = {
			E: [],
			L: [],
			C: [],
			H: [],
			a: [],
			b: [],
			matches: [],
			sum: null
		};
		patch_number_html = [];
		actual_rgb_html = [];
		target_rgb_html = [];
		if (rules[j][2].indexOf("_MAX") < 0) {
			for (var k=0; k<rules[j][1].length; k++) if (rules[j][1].length > 1 && seen.indexOf(rules[j][1].join(',')) < 0) {
				patch_number_html.push('<div class="patch sample_id">&#160;</div>');
				if (rules[j][1][k].length == 4) // Assume CMYK
					target_rgb = jsapi.math.color.cmyk2rgb(rules[j][1][k][0] / 100, rules[j][1][k][1] / 100, rules[j][1][k][2] / 100, rules[j][1][k][3] / 100);
				else 
					target_rgb = [rules[j][1][k][0] * 2.55, rules[j][1][k][1] * 2.55, rules[j][1][k][2] * 2.55];
				target_rgb_html.push('<div class="patch" style="background-color: rgb(' + Math.round(target_rgb[0]) + ', ' + Math.round(target_rgb[1]) + ', ' + Math.round(target_rgb[2]) + ');">&#160;</div>');
				actual_rgb_html.push('<div class="patch" style="color: red; position: relative;"><span style="position: absolute;">\u2716</span>&#160;</div>');
			}
		};
		if (rules[j][1].length) {
			for (var k=0; k<rules[j][1].length; k++) {
				for (var l=0; l<rules[j][1][k].length; l++) if (!isNaN(rules[j][1][k][l])) rules[j][1][k][l] = rules[j][1][k][l].accuracy(2);
			}
		};
		var silent = false;
		for (var i=0, n=0; i<this.data.length; i++) {
				n++;
				target = data_ref.data[i];
				actual = this.data[i];
				matched = false;
				if (rules[j][1].length) {
					for (var k=0; k<rules[j][1].length; k++) {
						if (fields_match.join(',').indexOf('RGB') == 0) 
							var current_rgb = actual.slice(fields_extract_indexes_i[0], fields_extract_indexes_i[0] + 3),
								current_cmyk = actual.slice(fields_extract_indexes_i[3], fields_extract_indexes_i[7]);
						else 
							var current_rgb = actual.slice(fields_extract_indexes_i[4], fields_extract_indexes_i[7]),
								current_cmyk = actual.slice(fields_extract_indexes_i[0], fields_extract_indexes_i[4]);
						for (var l=0; l<current_rgb.length; l++) current_rgb[l] = current_rgb[l].accuracy(2);
						for (var l=0; l<current_cmyk.length; l++) current_cmyk[l] = current_cmyk[l].accuracy(2);
						if ((rules[j][1][k].length == 3 && current_rgb.join(',') == rules[j][1][k].join(',')) || (rules[j][1][k].length == 4 && current_cmyk.join(',') == rules[j][1][k].join(','))) {
							// if (silent || !confirm('rules[j]: ' + rules[j] + '\nrules[j][1][k]: ' + rules[j][1][k] + '\nthis.data[' + i + ']: ' + this.data[i] + '\ncurrent_rgb: ' + current_rgb + '\ncurrent_cmyk: ' + current_cmyk)) silent = true;
							if (rules[j][2].indexOf("_MAX") < 0 && seen.indexOf(rules[j][1].join(',')) < 0) {
								if (rules[j][1].length) patch_number_html[k] = ('<div class="patch sample_id">' + n.fill(String(number_of_sets).length) + '</div>');
								if (no_Lab && !no_XYZ) {
									target_rgb = jsapi.math.color.XYZ2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]);
									actual_rgb = jsapi.math.color.XYZ2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]);
								}
								else {
									target_rgb = jsapi.math.color.Lab2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]], null, D50);
									actual_rgb = jsapi.math.color.Lab2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]], null, D50);
								}
								target_rgb_html[k] = ('<div class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');">&#160;</div>');
								actual_rgb_html[k] = ('<div class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');">&#160;</div>');
							};
							matched = true
						}
					}
				}
				else matched = true;
				if (matched) {
					target_Lab = [target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]];
					actual_Lab = [actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]];
					if (no_Lab && !no_XYZ) {
						target_Lab = jsapi.math.color.XYZ2Lab(target_Lab[0], target_Lab[1], target_Lab[2]);
						actual_Lab = jsapi.math.color.XYZ2Lab(actual_Lab[0], actual_Lab[1], actual_Lab[2]);
					}
					if (gray_balance_cal_only) {
						if (fields_match.join(',').indexOf('RGB') == 0) 
							var current_rgb = actual.slice(fields_extract_indexes_i[0], fields_extract_indexes_i[0] + 3);
						else 
							var current_rgb = actual.slice(fields_extract_indexes_i[4], fields_extract_indexes_i[7]);
						for (var l=0; l<current_rgb.length; l++) current_rgb[l] = current_rgb[l].accuracy(2);
						if (current_rgb[0] == current_rgb[1] && current_rgb[1] == current_rgb[2]) {
							target_Lab[0] = actual_Lab[0]; // set L to measured value
							target_Lab[1] = target_Lab[2] = 0; // set a=b=0
						}
					};
					delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], rules[j][5]);
					result[j].E.push(delta.E);
					result[j].L.push(delta.L);
					result[j].C.push(delta.C);
					result[j].H.push(delta.H);
					result[j].a.push(delta.a);
					result[j].b.push(delta.b);
					if (rules[j][1].length || rules[j][2].indexOf('_MAX') > -1) result[j].matches.push([i, i, n])
				}
		};
		this.report_html = this.report_html.concat(patch_number_html);
		var number_of_sets = n;
		if (rules[j][1].length == 1) {
			switch (rules[j][1][0]) {
				case 'CAL_REDLEVELS':
					result[j].sum = (window.CAL_RGBLEVELS[0] / CAL_ENTRYCOUNT * 100).accuracy(1) + '%<br />(' + window.CAL_RGBLEVELS[0] + '/' + CAL_ENTRYCOUNT + ')';
					break;
				case 'CAL_GREENLEVELS':
					result[j].sum = (window.CAL_RGBLEVELS[1] / CAL_ENTRYCOUNT * 100).accuracy(1) + '%<br />(' + window.CAL_RGBLEVELS[1] + '/' + CAL_ENTRYCOUNT + ')';
					break;
				case 'CAL_BLUELEVELS':
					result[j].sum = (window.CAL_RGBLEVELS[2] / CAL_ENTRYCOUNT * 100).accuracy(1) + '%<br />(' + window.CAL_RGBLEVELS[2] + '/' + CAL_ENTRYCOUNT + ')';
					break;
				case 'CAL_GRAYLEVELS':
					var cal_graylevels = Math.min(CAL_RGBLEVELS[0], CAL_RGBLEVELS[1], CAL_RGBLEVELS[2]);
					result[j].sum = (cal_graylevels / CAL_ENTRYCOUNT * 100).accuracy(1) + '%<br />(' + cal_graylevels + '/' + CAL_ENTRYCOUNT + ')';
					break;
				case 'WHITEPOINT':
					target_Lab = jsapi.math.color.XYZ2Lab(wp_assumed[0], wp_assumed[1], wp_assumed[2]);
					actual_Lab = jsapi.math.color.XYZ2Lab(wp_norm[0], wp_norm[1], wp_norm[2]);
					// alert(rules[j] + '\ntarget_Lab: ' + target_Lab + '\nactual_Lab: ' + actual_Lab);
					delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], rules[j][5]);
					result[j].E.push(delta.E);
					result[j].L.push(delta.L);
					result[j].C.push(delta.C);
					result[j].H.push(delta.H);
					result[j].a.push(delta.a);
					result[j].b.push(delta.b);
					break;
			}
		};
		if (!rules[j][1].length || rules[j][1][0] == 'WHITEPOINT' || result[j].matches.length >= rules[j][1].length) switch (rules[j][2]) {
			case DELTA_A_MAX:
				result[j].sum = jsapi.math.absmax(result[j].a);
				break;
			case DELTA_A_AVG:
				result[j].sum = jsapi.math.avg(result[j].a);
				break;
			case DELTA_A_MED:
				result[j].sum = jsapi.math.median(result[j].a);
				break;
			case DELTA_A_MAD:
				result[j].sum = jsapi.math.mad(result[j].a);
				break;
			case DELTA_A_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].a) - jsapi.math.min(result[j].a));
				break;
			case DELTA_A_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].a);
				break;
				
			case DELTA_A_B_RANGE:
				result[j].sum = Math.abs(jsapi.math.absmax(result[j].a)) + Math.abs(jsapi.math.absmax(result[j].b));
				break;
				
			case DELTA_B_MAX:
				result[j].sum = jsapi.math.absmax(result[j].b);
				break;
			case DELTA_B_AVG:
				result[j].sum = jsapi.math.avg(result[j].b);
				break;
			case DELTA_B_MED:
				result[j].sum = jsapi.math.median(result[j].b);
				break;
			case DELTA_B_MAD:
				result[j].sum = jsapi.math.mad(result[j].b);
				break;
			case DELTA_B_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].b) - jsapi.math.min(result[j].b));
				break;
			case DELTA_B_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].b);
				break;
				
			case DELTA_E_MAX:
				result[j].sum = jsapi.math.absmax(result[j].E);
				break;
			case DELTA_E_AVG:
				result[j].sum = jsapi.math.avg(result[j].E);
				break;
			case DELTA_E_MED:
				result[j].sum = jsapi.math.median(result[j].E);
				break;
			case DELTA_E_MAD:
				result[j].sum = jsapi.math.mad(result[j].E);
				break;
			case DELTA_E_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].E) - jsapi.math.min(result[j].E));
				break;
			case DELTA_E_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].E);
				break;
				
			case DELTA_L_MAX:
				result[j].sum = jsapi.math.absmax(result[j].L);
				break;
			case DELTA_L_AVG:
				result[j].sum = jsapi.math.avg(result[j].L);
				break;
			case DELTA_L_MED:
				result[j].sum = jsapi.math.median(result[j].L);
				break;
			case DELTA_L_MAD:
				result[j].sum = jsapi.math.mad(result[j].L);
				break;
			case DELTA_L_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].L) - jsapi.math.min(result[j].L));
				break;
			case DELTA_L_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].L);
				break;
				
			case DELTA_C_MAX:
				result[j].sum = jsapi.math.absmax(result[j].C);
				break;
			case DELTA_C_AVG:
				result[j].sum = jsapi.math.avg(result[j].C);
				break;
			case DELTA_C_MED:
				result[j].sum = jsapi.math.median(result[j].C);
				break;
			case DELTA_C_MAD:
				result[j].sum = jsapi.math.mad(result[j].C);
				break;
			case DELTA_C_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].C) - jsapi.math.min(result[j].C));
				break;
			case DELTA_C_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].C);
				break;
				
			case DELTA_H_MAX:
				result[j].sum = jsapi.math.absmax(result[j].H);
				break;
			case DELTA_H_AVG:
				result[j].sum = jsapi.math.avg(result[j].H);
				break;
			case DELTA_H_MED:
				result[j].sum = jsapi.math.median(result[j].H);
				break;
			case DELTA_H_MAD:
				result[j].sum = jsapi.math.mad(result[j].H);
				break;
			case DELTA_H_RANGE:
				result[j].sum = Math.abs(jsapi.math.max(result[j].H) - jsapi.math.min(result[j].H));
				break;
			case DELTA_H_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].H);
				break;
		}
		else if (!rules[j][1].length || (rules[j][1][0] + '').indexOf('LEVELS') < 0) missing_data = true;
		if (result[j].matches.length) {
			matched = false;
			for (var k=0; k<result[j].matches.length; k++) {
				target = data_ref.data[result[j].matches[k][0]];
				actual = this.data[result[j].matches[k][1]];
				switch (rules[j][2]) {
					case DELTA_E_MAX:
						if (result[j].E[k] == result[j].sum) matched = true;
						break;
					case DELTA_L_MAX:
						if (result[j].L[k] == result[j].sum) matched = true;
						break;
					case DELTA_C_MAX:
						if (result[j].C[k] == result[j].sum) matched = true;
						break;
					case DELTA_H_MAX:
						if (result[j].H[k] == result[j].sum) matched = true;
						break;
				};
				if (matched) {
					result[j].finalmatch = result[j].matches[k];
					break;
				};
			};
			if (matched) {
				this.report_html.push('<div class="patch sample_id">' + result[j].finalmatch[2].fill(String(number_of_sets).length) + '</div>');
				if (no_Lab && !no_XYZ) {
					target_rgb = jsapi.math.color.XYZ2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]);
					actual_rgb = jsapi.math.color.XYZ2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]);
				}
				else {
					target_rgb = jsapi.math.color.Lab2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]], null, D50);
					actual_rgb = jsapi.math.color.Lab2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]], null, D50);
				}
				target_rgb_html.push('<div class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');">&#160;</div>');
				actual_rgb_html.push('<div class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');">&#160;</div>');
			};
		}
		if (!target_rgb_html.length) {
			target_rgb_html.push('<div class="patch">&#160;</div>');
			actual_rgb_html.push('<div class="patch">&#160;</div>');
		};
		this.report_html.push('			</td>');
		this.report_html.push('			<td class="patch">' + target_rgb_html.join('') + '</td>');
		this.report_html.push('			<td class="patch">' + actual_rgb_html.join('') + '</td>');
		var bar_html = [];
		if (result[j].sum != null && (!rules[j][1].length || (rules[j][1][0] + '').indexOf('LEVELS') < 0)) {
			if (!rules[j][3]) rgb = [204, 204, 204];
			else {
				var rgb = [0, 255, 0],
					step = 255 / (rules[j][3] + rules[j][3] / 2);
				if (Math.abs(result[j].sum) <= rules[j][3]) {
					rgb[0] += Math.min(step * Math.abs(result[j].sum), 255);
					rgb[1] -= Math.min(step * Math.abs(result[j].sum), 255);
					var maxrg = Math.max(rgb[0], rgb[1]);
					rgb[0] *= (255 / maxrg);
					rgb[1] *= (255 / maxrg);
					rgb[0] = Math.round(rgb[0]);
					rgb[1] = Math.round(rgb[1]);
				}
				else rgb = [255, 0, 0];
			};
			for (var l = 0; l < actual_rgb_html.length; l ++) {
				bar_html.push('<span style="display: block; width: ' + (10 * Math.abs(result[j].sum).accuracy(2)) + 'px; background-color: rgb(' + rgb.join(', ') + '); border: 1px solid silver; border-top: none; border-bottom: none; padding: .125em .25em .125em 0;">&#160;</span>');
			};
		};
		this.report_html.push('			<td><span class="' + (result[j].sum != null && rules[j][3] ? (Math.abs(result[j].sum).accuracy(2) < rules[j][3] ? 'ok' : (Math.abs(result[j].sum).accuracy(2) == rules[j][3] ? 'warn' : 'ko')) : 'statonly') + '">' + (result[j].sum != null ? result[j].sum.accuracy(2) : '') + '</span></td><td style="padding: 0;">' + bar_html.join('') + '</td><td class="' + (result[j].sum != null && (!rules[j][3] || Math.abs(result[j].sum) <= rules[j][3]) ? ((Math.abs(result[j].sum).accuracy(2) < rules[j][3] ? 'ok">OK <span class="checkmark">✔</span>' : (result[j].sum != null && rules[j][3] ? 'warn">OK \u26a0' : 'na">')) + '<span class="' + (rules[j][4] && Math.abs(result[j].sum) <= rules[j][4] ? 'checkmark' : 'hidden') + (rules[j][4] ? '">✔' : '">')) : 'ko">' + (result[j].sum != null ? 'NOT OK' : '') + ' <span class="checkmark">\u2716') + '</span></td>');
		this.report_html.push('		</tr>');
		if (rules[j][1] && rules[j][1].length > 1) seen.push(rules[j][1].join(','));
	};
	this.report_html.push('	</table>');
	
	var pass, overachieve;
	for (var j=0; j<result.length; j++) {
		if (!rules[j][3]) continue;
		if (missing_data || isNaN(result[j].sum) || Math.abs(result[j].sum) > rules[j][3]) pass = false;
		if (!rules[j][4]) continue;
		if (missing_data || isNaN(result[j].sum) || Math.abs(result[j].sum) > rules[j][4]) overachieve = false;
		if (rules[j][5] == delta_calc_method) for (var k=0; k<result[j].matches.length; k++) {
			if (rules[j][2].indexOf('_E_') > -1) {
				this.data[result[j].matches[k][1]].actual_DE = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].E[k]);
				this.data[result[j].matches[k][1]].tolerance_DE = rules[j][3];
			}
			else if (rules[j][2].indexOf('_L_') > -1) {
				this.data[result[j].matches[k][1]].actual_DL = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].L[k]);
				this.data[result[j].matches[k][1]].tolerance_DL = rules[j][3];
			}
			else if (rules[j][2].indexOf('_C_') > -1) {
				this.data[result[j].matches[k][1]].actual_DC = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].C[k]);
				this.data[result[j].matches[k][1]].tolerance_DC = rules[j][3];
			}
			else if (rules[j][2].indexOf('_H_') > -1) {
				this.data[result[j].matches[k][1]].actual_DH = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].H[k]);
				this.data[result[j].matches[k][1]].tolerance_DH = rules[j][3];
			}
		};
	};
	this.report_html.push('<div class="footer"><p><span class="' + (pass !== false ? 'ok"><span class="checkmark">✔</span> ' + criteria.passtext : 'ko"><span class="checkmark">\u2716</span> ' + (missing_data ? 'MISSING DATA' : criteria.failtext)) + '</span>' + ((overachieve !== false && criteria.passrecommendedtext) || (overachieve === false && criteria.failrecommendedtext) ? '<br /><span class="' + (overachieve !== false ? 'ok"><span class="checkmark">✔</span> ' + criteria.passrecommendedtext : 'info"><span class="checkmark">✘</span> ' + criteria.failrecommendedtext) + '</span>' : '') + '</p>');
	
	this.result_html = this.report_html.slice(result_start);
	this.report_html.push('	</div>');
	
	this.report_html.push('	<div class="overview">');
	this.report_html.push('	<h3>Overview</h3>');
	this.report_html.push('	<table>');
	this.report_html.push('		<tr>');
	this.report_html.push('			<th>#</th><th colspan="' + fields_match.slice(0, devlen + 1).length + '">Device Values</th><th colspan="3">Nominal Values</th><th colspan="2">&#160;</th><th colspan="3">Measured Values</th><th colspan="4">ΔE*' + delta_calc_method.substr(3) + '</th><th>&#160;</th>');
	this.report_html.push('		</tr>');
	this.report_html.push('		<tr>');
	this.report_html.push('			<th>&#160;</th><th>' + fields_match.slice(0, devlen + 1).join('</th><th>').replace(/\w+?_/g, '') + '</th><th>' + 'L*,a*,b*'.split(',').join('</th><th>') + '</th><th>&#160;</th><th>&#160;</th><th>' + 'L*,a*,b*'.split(',').join('</th><th>') + '</th><th>ΔL*</th><th>Δa*</th><th>Δb*</th><th>ΔC*</th><th>ΔH*</th><th>ΔE*</th><th>&#160;</th>');
	this.report_html.push('		</tr>');
	for (var i=0, n=0; i<this.data.length; i++) {
		n++;
		target = data_ref.data[i];
		actual = this.data[i];
		target_Lab = [target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]];
		actual_Lab = [actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]];
		if (no_Lab && !no_XYZ) {
			target_Lab = jsapi.math.color.XYZ2Lab(target_Lab[0], target_Lab[1], target_Lab[2]);
			actual_Lab = jsapi.math.color.XYZ2Lab(actual_Lab[0], actual_Lab[1], actual_Lab[2]);
			target_rgb = jsapi.math.color.XYZ2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]);
			actual_rgb = jsapi.math.color.XYZ2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]);
		}
		else {
			target_rgb = jsapi.math.color.Lab2rgb(target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]], null, D50);
			actual_rgb = jsapi.math.color.Lab2rgb(actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]], null, D50);
		}
		if (gray_balance_cal_only) {
			if (fields_match.join(',').indexOf('RGB') == 0) 
				var current_rgb = actual.slice(fields_extract_indexes_i[0], fields_extract_indexes_i[0] + 3);
			else 
				var current_rgb = actual.slice(fields_extract_indexes_i[4], fields_extract_indexes_i[7]);
			for (var l=0; l<current_rgb.length; l++) current_rgb[l] = current_rgb[l].accuracy(2);
			if (current_rgb[0] == current_rgb[1] && current_rgb[1] == current_rgb[2]) {
				target_Lab[0] = actual_Lab[0]; // set L to measured value
				target_Lab[1] = target_Lab[2] = 0; // set a=b=0
			}
		};
		delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], delta_calc_method);
		this.report_html.push('		<tr' + (i == this.data.length - 1 ? ' class="last-row"' : '') + '>');
		var bar_html = [],
			rgb = [0, 255, 0];
		if (actual.tolerance_DE == null)
			actual.tolerance_DE = 5;
		if (actual.actual_DE == null)
			actual.actual_DE = delta.E;
		var step = 255 / (actual.tolerance_DE + actual.tolerance_DE / 2);
		if (actual.actual_DE <= actual.tolerance_DE) {
			rgb[0] += Math.min(step * actual.actual_DE, 255);
			rgb[1] -= Math.min(step * actual.actual_DE, 255);
			var maxrg = Math.max(rgb[0], rgb[1]);
			rgb[0] *= (255 / maxrg);
			rgb[1] *= (255 / maxrg);
			rgb[0] = Math.round(rgb[0]);
			rgb[1] = Math.round(rgb[1]);
		}
		else rgb = [255, 0, 0];
		bar_html.push('<span style="display: block; width: ' + (10 * actual.actual_DE.accuracy(2)) + 'px; background-color: rgb(' + rgb.join(', ') + '); border: 1px solid silver; border-top: none; border-bottom: none; padding: .125em .25em .125em 0;">&#160;</span>');
		var device = target.slice(fields_extract_indexes_i[0], fields_extract_indexes_i[devlen] + 1);
		for (var j=0; j<device.length; j++) device[j] = Math.round(device[j] * 2.55);
		if (typeof actual_Lab[2] != 'number') alert(actual);
		this.report_html.push('			<td>' + n.fill(String(number_of_sets).length) + '</td><td>' + device.join('</td><td>') + '</td><td>' + target_Lab[0].accuracy(2) + '</td><td>' + target_Lab[1].accuracy(2) + '</td><td>' + target_Lab[2].accuracy(2) + '</td><td class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');"><div class="patch">&#160;</div></td><td class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');"><div class="patch">&#160;</div></td><td>' + actual_Lab[0].accuracy(2) + '</td><td>' + actual_Lab[1].accuracy(2) + '</td><td>' + actual_Lab[2].accuracy(2) + '</td><td class="' + (actual.actual_DL != null ? (actual.actual_DL.accuracy(2) < actual.tolerance_DL ? 'ok' : (actual.actual_DL.accuracy(2) == actual.tolerance_DL ? 'warn' : 'ko')) : 'info') + '">' + delta.L.accuracy(2) + '</td><td class="' + (actual.actual_Da != null ? (actual.actual_Da.accuracy(2) < actual.tolerance_Da ? 'ok' : (actual.actual_Da.accuracy(2) == actual.tolerance_Da ? 'warn' : 'ko')) : 'info') + '">' + delta.a.accuracy(2) + '</td><td class="' + (actual.actual_Db != null ? (actual.actual_Db.accuracy(2) < actual.tolerance_Db ? 'ok' : (actual.actual_Db.accuracy(2) == actual.tolerance_Db ? 'warn' : 'ko')) : 'info') + '">' + delta.b.accuracy(2) + '</td><td class="' + (actual.actual_DC != null ? (actual.actual_DC.accuracy(2) < actual.tolerance_DC ? 'ok' : (actual.actual_DC.accuracy(2) == actual.tolerance_DC ? 'warn' : 'ko')) : 'info') + '">' + delta.C.accuracy(2) + '</td><td class="' + (actual.actual_DH != null ? (actual.actual_DH.accuracy(2) < actual.tolerance_DH ? 'ok' : (actual.actual_DH.accuracy(2) == actual.tolerance_DH ? 'warn' : 'ko')) : 'info') + '">' + delta.H.accuracy(2) + '</td><td class="' + (actual.actual_DE != null ? (actual.actual_DE.accuracy(2) < actual.tolerance_DE ? 'ok' : (actual.actual_DE.accuracy(2) == actual.tolerance_DE ? 'warn' : 'ko')) : (delta.E < warn_deviation ? 'info' : 'warn')) + '">' + delta.E.accuracy(2) + '</td><td style="padding: 0;">' + bar_html.join('') + '</td>');
		this.report_html.push('		</tr>');
	};
	this.report_html.push('	</table>');
	this.report_html.push('	</div>');
	
	return this.report_html.join('\n')
};

function trim(txt) {
	return txt.replace(/^\s+|\s+$/g, "")
};

function lf2cr(txt) {
	return txt.replace(/\r\n/g, "\r").replace(/\n/g, "\r")
};

function cr2lf(txt) {
	// CR LF = Windows
	// CR = Mac OS 9
	// LF = Unix/Linux/Mac OS X
	return txt.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
};

function compact(txt, collapse_whitespace) {
	txt = trim(txt).replace(/\n\s+|\s+\n/g, "\n");
	return collapse_whitespace?txt.replace(/\s+/g, " "):txt
};

function comma2point(txt) {
	return decimal(txt)
};

function decimal(txt, sr, re) {
	if (!sr) sr = "\\,";
	if (!re) re = ".";
	return txt.replace(new RegExp("((^|\\s)\\-?\\d+)"+sr+"(\\d+(?=\\s|$))", "g"), "$1"+re+"$3")
};

function toarray(txt, level) {
	txt=comma2point(compact(cr2lf(txt)));
	if (!txt) return [];
	if (level) {
		txt=txt.split(/\s/)
	}
	else {
		txt=txt.split("\n");
		for (var i=0; i<txt.length; i++) {
			txt[i]=txt[i].split(/\s+/);
			for (var j=0; j<txt[i].length; j++) {
				parsed=parseFloat(txt[i][j]);
				if (!isNaN(parsed)) txt[i][j]=parsed;
			}
		}
	};
	return txt
};

function fromarray(array, level) {
	array = array.clone();
	if (level) return array.join("\t");
	for (var i=0; i<array.length; i++) array[i]=array[i].join("\t");
	return array.join("\n")
};

function analyze(which) {
	var f=document.forms,
		e=f['F_out'].elements,fv,i,j,v,s;
	
	if (!trim(f["F_data"].elements["FF_data_in"].value) || !trim(f["F_data"].elements["FF_data_ref"].value)) return;
	
	if (!get_data(which)) {
		if (which == "r" || !which) {
			if (trim(f['F_data'].elements['FF_data_ref'].value)) {
				if (!data_ref.data_format.length) set_status("Reference data: No or invalid data format.");
				else if (!data_ref.data.length) set_status("Reference data: No or invalid values.")
			};
		};
		if (which == "i" || !which) {
			if (trim(f['F_data'].elements['FF_data_in'].value)) {
				if (!data_in.data_format.length) set_status("Measurement data: No or invalid data format.");
				else if (!data_in.data.length) set_status("Measurement data: No or invalid values.")
			};
		}
	};
	
	var _criteria = [];
	for (var id in comparison_criteria) {
		if (comparison_criteria[id] && comparison_criteria[id].name && _criteria.indexOf(comparison_criteria[id]) < 0) {
			for (var i=0; i<comparison_criteria[id].fields_match.length; i++) {
				if (data_ref.data_format.indexOf(comparison_criteria[id].fields_match[i]) < 0) 
					break;
				else if (fields_match.indexOf(comparison_criteria[id].fields_match[i]) < 0)
					fields_match.push(comparison_criteria[id].fields_match[i]);
			};
			if (i == comparison_criteria[id].fields_match.length) {
				_criteria.push(comparison_criteria[id])
			}
		}
	};
	for (var i=0; i<_criteria.length; i++) {
		e['FF_criteria'].options[i] = new Option(_criteria[i].name, _criteria[i].id, data_ref.id == _criteria[i].id, data_ref.id == _criteria[i].id)
	};
	
	var criteria = comparison_criteria[e['FF_criteria'].value],
		fields_extract_r = fields_match.slice().concat(criteria.fields_compare),
		fields_extract_i = fields_match.slice().concat(criteria.fields_compare);
	
	for (i=0; i<fields_extract_i.length; i++) {
		for (j=0; j<data_in.data_format.length; j++) {
			if (data_in.data_format[j]==fields_extract_i[i]) {
				fields_extract_indexes_i.push(j);
				break
			}
		}
	};
	for (i=0; i<fields_extract_r.length; i++) {
		for (j=0; j<data_ref.data_format.length; j++) {
			if (data_ref.data_format[j]==fields_extract_r[i]) {
				fields_extract_indexes_r.push(j);
				break
			}
		}
	};
	
	if (data_in.data.length && data_ref.data.length && data_in.data.length != data_ref.data.length) {
		alert("Different amount of sets in measurements and reference data.");
		return false
	};
	var data_in_format_missing_fields = [], data_ref_format_missing_fields = [], errortxt = "";
	for (i = 0; i < fields_extract_i.length; i ++) {
		if (data_in.data_format.indexOf(fields_extract_i[i]) < 0) data_in_format_missing_fields.push(fields_extract_i[i]);
		if (data_ref.data_format.indexOf(fields_extract_i[i]) < 0) data_ref_format_missing_fields.push(fields_extract_i[i]);
	};
	if (data_in_format_missing_fields.length) {
		errortxt += "Measurement data is missing the following fields: " + data_in_format_missing_fields.join(", ") + ".\n"
	}
	if (data_ref_format_missing_fields.length) {
		errortxt += "Reference data is missing the following fields: " + data_ref_format_missing_fields.join(", ") + ".\n"
	};
	if (errortxt) {
		alert(errortxt + "Measurements and reference data must contain atleast: " + fields_extract_i.join(", "));
		return
	};
	
	if (data_ref.data_format.length && data_ref.data.length && data_in.data_format.length && data_in.data.length) {
		compare();
	};
};

function get_data(which) {
	var f=document.forms;
	
	if (which == "r" || !which) {
		data_ref=new dataset(f["F_data"].elements["FF_data_ref"].value)
	};
	if (which == "i" || !which) {
		data_in=new dataset(f["F_data"].elements["FF_data_in"].value)
	};
	
	if (which == "r" || !which) {
		if (!data_ref.data_format.length) return false;
		if (!data_ref.data.length) return false
	};
	if (which == "i" || !which) {
		if (!data_in.data_format.length) return false;
		if (!data_in.data.length) return false
	};
	
	return true
};

function compare(set_delta_calc_method) {
	form_elements_set_disabled(null, true);
	var fe = document.forms["F_out"].elements, fe2 = document.forms["F_data"].elements;
	if (fe2["FF_variables"]) try {
		eval(fe2["FF_variables"].value);
		window.comparison_criteria = comparison_criteria;
		if (window.location.href.indexOf("?debug")>-1) alert("Comparsion criteria: " + (comparison_criteria.toSource ? comparison_criteria.toSource() : comparison_criteria))
	}
	catch (e) {
		alert("Error parsing variable:\n" + e + "\nUsing default values.")
	};
	var report = data_in.generate_report(set_delta_calc_method);
	document.getElementById('result').innerHTML = report;
	document.getElementById('report').style.display = "block";
	form_elements_set_disabled(null, false);
	return true
};

function form_element_set_disabled(form_element, disabled) {
	if (!form_element || form_element.readOnly || form_element.type == "hidden" || form_element.type == "file" || jsapi.dom.attributeHasWord(form_element, "class", "fakefile") || jsapi.dom.attributeHasWord(form_element, "class", "save") || jsapi.dom.attributeHasWord(form_element, "class", "delete")) return;
	disabled = disabled ? "disabled" : "";
	form_element.disabled=disabled;
	if (disabled && !jsapi.dom.attributeHasWord(form_element, "class", "disabled")) jsapi.dom.attributeAddWord(form_element, "class", "disabled");
	else if (!disabled && jsapi.dom.attributeHasWord(form_element, "class", "disabled")) jsapi.dom.attributeRemoveWord(form_element, "class", "disabled");
	var labels = document.getElementsByTagName("LABEL");
	for (var i=0; i<labels.length; i++) if (labels[i].getAttribute("for") == form_element.id) {
		if (labels[i].getAttribute("for") == "FF_gray_balance_cal_only") labels[i].style.display = disabled || document.forms['F_out'].elements['FF_criteria'].value != 'VERIFY' ? "none" : "inline";
		labels[i].className=disabled;
	}
};

function form_elements_set_disabled(form, disabled) {
	disabled = disabled ? "disabled" : "";
	if (form) for (var j=0; j<form.elements.length; j++) form_element_set_disabled(form.elements[j], disabled);
	else {
		for (var i=0; i<document.forms.length; i++) {
			for (var j=0; j<document.forms[i].elements.length; j++) {
				if (document.forms[i].elements[j].name == "FF_gray_balance_cal_only") form_element_set_disabled(document.forms[i].elements[j], disabled || !window.CRITERIA_GRAYSCALE);
				else form_element_set_disabled(document.forms[i].elements[j], disabled);
			}
		}
	}
};

function set_status(str, append) {
	if (append) window.status += str;
	else window.status = str
};

function set_progress(str, cur_num, max_num) {
	var p = Math.ceil(100 / max_num * cur_num);
	set_status(str + p + "% " + "|".repeat(p / 2))
};

function basename(path) {
	return path.split(/[\/\\]/).pop()
};

function splitext(path) {
	return path.match(/(^.+?)(\.\w+)?$/).slice(1)
};

function plaintext(which) {
	var e = document.forms['F_data'].elements;
	if (which == 'ref') 
		var f = 'FF_data_ref';
	else
		var f = 'FF_data_in';
	var win = window.open();
	win.document.open('text/plain');
	win.document.write(e[f].value);
	win.document.close();
};
