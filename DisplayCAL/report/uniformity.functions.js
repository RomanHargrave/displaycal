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

var selected_index = 0;

// Main
function generate_report() {
	var cells = [],
		reference_index = parseInt(Math.floor(rows * cols / 2.0)),
		reference = results[reference_index],
		Ymax = 0,
		delta_cycle = {'E': 'C',
					   'C': 'H',
					   'H': 'L',
					   'L': 'E'};
	// Find brightest point
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			if (results[i][j]['XYZ'][1] > Ymax) Ymax = results[i][j]['XYZ'][1];
		}
	}
	var scale = 100 / Ymax;
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			var XYZ = results[i][j]['XYZ'],
				XYZ_scaled = [scale * XYZ[0], scale * XYZ[1], scale * XYZ[2]];
			results[i][j]['XYZ_scaled'] = XYZ_scaled;
			results[i][j]['Lab'] = jsapi.math.color.XYZ2Lab(XYZ[0], XYZ[1], XYZ[2]);
			results[i][j]['Lab_scaled'] = jsapi.math.color.XYZ2Lab(XYZ_scaled[0], XYZ_scaled[1], XYZ_scaled[2]);
			results[i][j]['CCT'] = jsapi.math.color.XYZ2CorColorTemp(XYZ[0], XYZ[1], XYZ[2]);
		}
	}
	for (var i = 0; i < rows * cols; i ++) {
		var cellcontent = [],
			Y_diff = [],
			Y_diff_percent = [],
			rgb,
			deltas = [],
			CCT = [],
			CCT_diff = [],
			CCT_diff_percent = [],
			CT = [],
			CT_diff = [],
			CT_diff_percent = [];
		for (var j = 0; j < results[i].length; j ++) {
			var line = '<strong class="rgb_toggle" onclick="window.selected_index = ' + j + '; generate_report()">' + (100 - j * 25) + '% RGB:</strong> ' + results[i][j]['XYZ'][1].accuracy(2) + ' cd/m²',
				rLab = reference[j]['Lab_scaled'],
				Lab = results[i][j]['Lab_scaled'];
			CCT.push(results[i][j]['CCT']);
			CT.push(results[i][j]['C' + locus.substr(0, 1) + 'T']);
			if (results[i] == reference) {
				line += ' (' + (reference[j]['XYZ'][1] / reference[0]['XYZ'][1] * 100).accuracy(2) + '%)' + /*', D50 L*a*b* = ' + results[i][j]['Lab_scaled'][0].accuracy(2) + ' ' + results[i][j]['Lab_scaled'][1].accuracy(2) + ' ' + results[i][j]['Lab_scaled'][2].accuracy(2) +*/ '\n<br><abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(CCT[j]) + 'K, <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(CT[j]) + 'K';
			}
			else {
				var curdelta = jsapi.math.color.delta(rLab[0], rLab[1], rLab[2], Lab[0], Lab[1], Lab[2], "2k"),
					color = 'inherit', mark = '', Y_color = color, Y_mark = mark;
				deltas.push(curdelta[delta]);
				CCT_diff.push(-(reference[j]['CCT'] - results[i][j]['CCT']));
				CCT_diff_percent.push(100.0 / reference[j]['CCT'] * CCT_diff[j]);
				CT_diff.push(-(reference[j]['C' + locus.substr(0, 1) + 'T'] - CT[j]));
				CT_diff_percent.push(100.0 / reference[j]['C' + locus.substr(0, 1) + 'T'] * CT_diff[j]);
				Y_diff.push(-(reference[j]['XYZ'][1] - results[i][j]['XYZ'][1]));
				Y_diff_percent.push(100.0 / reference[0]['XYZ'][1] * Y_diff[j]);
				if (Math.abs(Y_diff_percent[j]) < 5) {
					Y_color = 'green';
					Y_mark = ' \u2713\u2713';
				}
				else if (Math.abs(Y_diff_percent[j]) < 10) {
					Y_color = 'green';
					Y_mark = ' \u2713';
				}
				else {
					Y_color = 'red';
					Y_mark = ' \u2716';
				}
				if (delta == 'E') {
					if (Math.abs(deltas[j]) <= 2) {
						color = 'green';
						mark = ' \u2713\u2713';
					}
					else if (Math.abs(deltas[j]) <= 4) {
						color = 'green';
						mark = ' \u2713';
					}
					else {
						color = 'red';
						mark = ' \u2716';
					}
				}
				line += ' <span style="color: ' + Y_color + '">(' + (Y_diff_percent[j] > 0 ? '+' : '') + Y_diff_percent[j].accuracy(2) + '%' + Y_mark + ')</span>, <span class="delta_toggle" style="color: ' + color + '" onclick="window.delta = &quot;' + delta_cycle[delta] + '&quot;; generate_report()">' + deltas[j].accuracy(2) + ' Δ' + delta + '*00' + mark + '</span><br>\n<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(CCT[j]) + 'K (' + (CCT_diff_percent[j] > 0 ? '+' : '') + CCT_diff_percent[j].accuracy(2) + '%), <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(CT[j]) + 'K (' + (CT_diff_percent[j] > 0 ? '+' : '') + CT_diff_percent[j].accuracy(2) + '%)';
			}
			if (j == selected_index) {
				rgb = jsapi.math.color.Lab2RGB(Lab[0], Lab[1] - rLab[1], Lab[2] - rLab[2], 'D50', 255, true);
				if (results[i] == reference && rgb[0] < 128 && rgb[1] < 128 && rgb[2] < 128)
					document.getElementsByTagName('body')[0].style.color = '#fff';
				else
					document.getElementsByTagName('body')[0].style.color = '#000';
			}
			cellcontent.push(line);
		}
		cellcontent.push('');
		cellcontent.push('<strong>Average:</strong>');
		if (results[i] == reference) {
			line = '<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K, <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K';
		}
		else {
			var delta_avg = jsapi.math.avgabs(deltas), Y_diff_percent_avg = jsapi.math.avg(Y_diff_percent),
				color = 'inherit', mark = '', Y_color = color, Y_mark = mark;
			if (Math.abs(Y_diff_percent_avg) < 5) {
				Y_color = 'green';
				Y_mark = ' \u2713\u2713';
			}
			else if (Math.abs(Y_diff_percent_avg) < 10) {
				Y_color = 'green';
				Y_mark = ' \u2713';
			}
			else {
				Y_color = 'red';
				Y_mark = ' \u2716';
			}
			if (delta == 'E') {
				if (Math.abs(delta_avg) <= 2) {
					color = 'green';
					mark = ' \u2713\u2713';
				}
				else if (Math.abs(delta_avg) <= 4) {
					color = 'green';
					mark = ' \u2713';
				}
				else {
					color = 'red';
					mark = ' \u2716';
				}
			}
			line = (Y_diff_percent_avg > 0 ? '+' : '') + jsapi.math.avg(Y_diff).accuracy(2) + ' cd/m² <span style="color: ' + Y_color + '">(' + (Y_diff_percent_avg > 0 ? '+' : '') + Y_diff_percent_avg.accuracy(2) + '%' + Y_mark + ')</span>, <span class="delta_toggle" style="color: ' + color + '" onclick="window.delta = &quot;' + delta_cycle[delta] + '&quot;; generate_report()">' + delta_avg.accuracy(2) + ' Δ' + delta + '*00' + mark + '</span><br>\n<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K (' + (jsapi.math.avg(CCT_diff_percent) > 0 ? '+' : '') + jsapi.math.avg(CCT_diff_percent).accuracy(2) + '%), <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K (' + (jsapi.math.avg(CT_diff_percent) > 0 ? '+' : '') + jsapi.math.avg(CT_diff_percent).accuracy(2) + '%)';
		}
		cellcontent.push(line);
		cells.push('<td id="cell-' + i + '" style="background-color: rgb(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + '); ' + (i == reference_index ? 'border: 1px dashed #666; ' : '') + 'height: ' + (100 / rows) + '%; width: ' + (100 / cols) + '%;">' + cellcontent.join('<br>\n') + '</td>');
		if ((i + 1) % self.cols == 0 && i + 1 < self.rows * self.cols) {
			cells[cells.length - 1] += '</tr>\n<tr>';
		}
	}
	document.getElementsByTagName('body')[0].innerHTML = '<table><tr>' + cells.join('') + '</tr></table>';
};
window.onload = generate_report;
