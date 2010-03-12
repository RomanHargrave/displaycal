if (jsapi.useragent.opera && jsapi.useragent.opera < 8) alert("Your version of Opera is too old. Please upgrade to Opera 8 or newer.");
else if (jsapi.useragent.msie && jsapi.useragent.mac) alert("Internet Explorer is not supported under Mac OS. Please use a different browser like Mozilla Firefox or Safari.");
		
var data_ref, data_in,
	duplicates,
	fields_extract_indexes_i,
	fields_header = [];
		
window.onload = function() {
	analyze()
};