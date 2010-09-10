if (jsapi.useragent.opera && jsapi.useragent.opera < 7) alert("Your version of Opera is too old. Please upgrade to Opera 7 or newer.");
else if (jsapi.useragent.msie < 5) alert("Your version of Internet Explorer is too old. Please upgrade to MSIE 5 or newer.");
else {
var data_ref, data_in,
	fields_extract_indexes_i = [],
	fields_extract_indexes_r = [],
	fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
		
window.onload = function() {
	if ((jsapi.useragent.msie && !jsapi.useragent.mac) || (jsapi.useragent.opera && jsapi.useragent.opera < 7.52)) {
		labels = document.getElementsByTagName('label');
		for (var i = 0; i < labels.length; i ++) {
			labels[i].onmouseup = function () {
				setTimeout(compare, 50);  // needed to trigger onchange for IE Win / Opera < 7.52
			};
			document.getElementById(jsapi.dom.attribute(labels[i], 'for')).onchange = null;
			document.getElementById(jsapi.dom.attribute(labels[i], 'for')).onmouseup = function () {
				setTimeout(compare, 50);  // needed to trigger onchange for IE Win / Opera < 7.52
			};
		};
	};
	analyze()
};
};