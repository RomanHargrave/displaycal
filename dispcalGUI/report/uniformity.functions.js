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

// Main
window.onload = function () {
	var cells = [],
		reference_index = parseInt(Math.floor(rows * cols / 2.0)),
		reference = results[reference_index],
		factor = 100 / reference[0]['XYZ'][1];  // item[0] is the 100% RGB reading
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			var XYZ = results[i][j]['XYZ'],
				XYZ_Y100 = [factor * XYZ[0], factor * XYZ[1], factor * XYZ[2]];
			results[i][j]['XYZ_Y100'] = XYZ_Y100;
			results[i][j]['Lab'] = jsapi.math.color.XYZ2Lab(XYZ[0], XYZ[1], XYZ[2]);
			results[i][j]['Lab_L100'] = jsapi.math.color.XYZ2Lab(XYZ_Y100[0], XYZ_Y100[1], XYZ_Y100[2]);
			results[i][j]['CCT'] = jsapi.math.color.XYZ2CorColorTemp(XYZ[0], XYZ[1], XYZ[2]);
		}
	}
	for (var i = 0; i < rows * cols; i ++) {
		var cellcontent = [],
			Y_diff = [],
			Y_diff_percent = [],
			rgb,
			delta_C = [],
			CCT = [],
			CCT_diff = [],
			CCT_diff_percent = [],
			CT = [],
			CT_diff = [],
			CT_diff_percent = [];
		for (var j = 0; j < results[i].length; j ++) {
			var line = '<strong>' + (100 - j * 25) + '% RGB:</strong> Y = ' + results[i][j]['XYZ'][1].accuracy(2) + ' cd/m²',
				rLab = reference[j]['Lab_L100'],
				Lab = results[i][j]['Lab_L100'];
			if (results[i] == reference) {
				CCT.push(reference[j]['CCT']);
				CT.push(reference[j]['CT']);
				line += ' (' + (reference[j]['XYZ'][1] / reference[0]['XYZ'][1] * 100).accuracy(2) + '%)' + /*', D50 L*a*b* = ' + results[i][j]['Lab_L100'][0].accuracy(2) + ' ' + results[i][j]['Lab_L100'][1].accuracy(2) + ' ' + results[i][j]['Lab_L100'][2].accuracy(2) +*/ '\n<br><abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(CCT[j]) + 'K, <abbr title="Closest ' + locus + ' Temperature">C' + locus[0] + 'T</abbr> ' + Math.round(CT[j]) + 'K';
			}
			else {
				var delta = jsapi.math.color.delta(rLab[0], rLab[1], rLab[2], Lab[0], Lab[1], Lab[2], "2k");
				delta_C.push(delta["C"]);
				CCT.push(results[i][j]['CCT']);
				CCT_diff.push(-(reference[j]['CCT'] - results[i][j]['CCT']));
				CCT_diff_percent.push(100.0 / reference[j]['CCT'] * CCT_diff[j]);
				CT.push(results[i][j]['CT']);
				CT_diff.push(-(reference[j]['CT'] - results[i][j]['CT']));
				CT_diff_percent.push(100.0 / reference[j]['CT'] * CT_diff[j]);
				Y_diff.push(-(reference[j]['XYZ'][1] - results[i][j]['XYZ'][1]));
				Y_diff_percent.push(100.0 / reference[0]['XYZ'][1] * Y_diff[j]);
				line += ' (' + (Y_diff_percent[j] > 0 ? '+' : '') + Y_diff_percent[j].accuracy(2) + '%), ' + delta_C[j].accuracy(2) + ' ΔC*00<br>\n<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(CCT[j]) + 'K (' + (CCT_diff_percent[j] > 0 ? '+' : '') + CCT_diff_percent[j].accuracy(2) + '%), <abbr title="Closest ' + locus + ' Temperature">C' + locus[0] + 'T</abbr> ' + Math.round(CT[j]) + 'K (' + (CT_diff_percent[j] > 0 ? '+' : '') + CT_diff_percent[j].accuracy(2) + '%)';
			}
			if (j == 0) {
				// 100% RGB
				rgb = jsapi.math.color.Lab2RGB(Lab[0], Lab[1] - rLab[1], Lab[2] - rLab[2], 'D50', 255, true);
			}
			cellcontent.push(line);
		}
		cellcontent.push('');
		cellcontent.push('<strong>Average:</strong>');
		if (results[i] == reference) {
			line = '<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K, <abbr title="Closest ' + locus + ' Temperature">C' + locus[0] + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K';
		}
		else {
			line = jsapi.math.avg(Y_diff).accuracy(2) + ' ΔY (' + (jsapi.math.avg(Y_diff_percent) > 0 ? '+' : '') + jsapi.math.avg(Y_diff_percent).accuracy(2) + '%), ' + jsapi.math.avg(delta_C).accuracy(2) + ' ΔC*00<br>\n<abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K (' + jsapi.math.avg(CCT_diff_percent).accuracy(2) + '%), <abbr title="Closest ' + locus + ' Temperature">C' + locus[0] + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K (' + jsapi.math.avg(CT_diff_percent).accuracy(2) + '%)';
		}
		cellcontent.push(line);
		cells.push('<td id="cell-' + i + '" style="background-color: rgb(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + '); ' + (i == reference_index ? 'border: 1px dashed #666; ' : '') + 'height: ' + (100 / cols) + '%; width: ' + (100 / rows) + '%;">' + cellcontent.join('<br>\n') + '</td>');
		if ((i + 1) % self.cols == 0 && i + 1 < self.rows * self.cols) {
			cells[cells.length - 1] += '</tr>\n<tr>';
		}
	}
	document.getElementsByTagName('body')[0].innerHTML = '<table><tr>' + cells.join('') + '</tr></table>';
};
